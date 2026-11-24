from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.utils import timezone

from .errors import RentalError
from .models import CashShift, FinanceEntry
from .roles import can_manage_finance, can_record_finance

Kind = FinanceEntry.Kind
RECEIPTS = (Kind.RENT_RECEIPT, Kind.DEPOSIT_RECEIPT)
REFUNDS = (Kind.RENT_REFUND, Kind.DEPOSIT_REFUND)
CASH_ENTRIES = RECEIPTS + REFUNDS


def _require_clerk(actor):
    if not can_record_finance(actor):
        raise RentalError("Cần quyền quyết toán tại quầy.", 403)


def _whole(value, *, signed=False):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise InvalidOperation
        if amount.copy_abs() >= Decimal("1e32") or (not signed and amount < 0):
            raise InvalidOperation
    except InvalidOperation as error:
        raise RentalError("Nhập số tiền VND nguyên hợp lệ.") from error
    return int(amount)


def _note(value, *, required):
    cleaned = value.strip() if isinstance(value, str) else ""
    if len(cleaned) > 2000 or (required and not cleaned):
        raise RentalError("Nhập lý do hoặc cách xử lý tối đa 2.000 ký tự.")
    return cleaned


def locked_shift_for_entry(kind, target):
    if kind not in CASH_ENTRIES and (target is None or target.kind not in CASH_ENTRIES):
        return None
    shift = CashShift.objects.select_for_update().filter(status=CashShift.Status.OPEN).first()
    if shift is None and settings.CASH_SHIFT_REQUIRED:
        raise RentalError("Cần mở ca trước khi ghi nhận giao dịch tiền.", 409)
    return shift


def shift_history(actor):
    _require_clerk(actor)
    return CashShift.objects.select_related("opened_by", "submitted_by", "closed_by")


def cash_shift_detail(actor, shift_id):
    shift = shift_history(actor).get(pk=shift_id)
    amounts = expected_shift(shift) if shift.status == CashShift.Status.OPEN else {
        "cash": shift.expected_cash_vnd, "transfer": shift.expected_transfer_vnd,
    }
    return shift, amounts


def open_shift(actor, opening_cash_vnd):
    _require_clerk(actor)
    amount = _whole(opening_cash_vnd)
    try:
        with transaction.atomic():
            return CashShift.objects.create(opened_by=actor, opening_cash_vnd=amount)
    except IntegrityError as error:
        if CashShift.objects.filter(status=CashShift.Status.OPEN).exists():
            raise RentalError("Đã có ca mở cho quỹ chung.", 409) from error
        raise


def expected_shift(shift):
    def movement(method):
        return Case(
            When(kind__in=RECEIPTS, method=method, then=F("amount_vnd")),
            When(kind__in=REFUNDS, method=method, then=-F("amount_vnd")),
            When(kind=Kind.REVERSAL, reverses__kind__in=RECEIPTS,
                 reverses__method=method, then=-F("amount_vnd")),
            When(kind=Kind.REVERSAL, reverses__kind__in=REFUNDS,
                 reverses__method=method, then=F("amount_vnd")),
            default=0, output_field=DecimalField(max_digits=32, decimal_places=0),
        )

    totals = shift.entries.aggregate(
        cash=Sum(movement(FinanceEntry.Method.CASH), default=0),
        transfer=Sum(movement(FinanceEntry.Method.TRANSFER), default=0),
    )
    return {
        "cash": int(totals["cash"]) + int(shift.opening_cash_vnd),
        "transfer": int(totals["transfer"]),
    }


@transaction.atomic
def submit_shift(actor, shift_id, counted_cash_vnd, confirmed_transfer_vnd, discrepancy_note=""):
    _require_clerk(actor)
    cash = _whole(counted_cash_vnd)
    transfer = _whole(confirmed_transfer_vnd, signed=True)
    shift = CashShift.objects.select_for_update().get(pk=shift_id)
    if shift.status != CashShift.Status.OPEN:
        raise RentalError("Ca này đã được nộp.", 409)
    expected = expected_shift(shift)
    note = _note(discrepancy_note, required=(cash != expected["cash"] or transfer != expected["transfer"]))
    shift.status = CashShift.Status.SUBMITTED
    shift.expected_cash_vnd = expected["cash"]
    shift.expected_transfer_vnd = expected["transfer"]
    shift.counted_cash_vnd = cash
    shift.confirmed_transfer_vnd = transfer
    shift.discrepancy_note = note
    shift.submitted_by = actor
    shift.submitted_at = timezone.now()
    shift.save(update_fields=[
        "status", "expected_cash_vnd", "expected_transfer_vnd", "counted_cash_vnd",
        "confirmed_transfer_vnd", "discrepancy_note", "submitted_by", "submitted_at",
    ])
    return shift


@transaction.atomic
def close_shift(actor, shift_id, resolution=""):
    if not can_manage_finance(actor):
        raise RentalError("Cần quyền quản lý để chốt ca.", 403)
    shift = CashShift.objects.select_for_update().get(pk=shift_id)
    if shift.status != CashShift.Status.SUBMITTED:
        raise RentalError("Ca phải đã nộp và đang chờ duyệt.", 409)
    shift.resolution = _note(
        resolution, required=bool(shift.cash_difference_vnd or shift.transfer_difference_vnd)
    )
    shift.status = CashShift.Status.CLOSED
    shift.closed_by = actor
    shift.closed_at = timezone.now()
    shift.save(update_fields=["status", "resolution", "closed_by", "closed_at"])
    return shift
