from collections import Counter
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.utils import timezone

from .cash_shifts import CASH_ENTRIES, RECEIPTS, REFUNDS, locked_shift_for_entry
from .custody import rental_handovers
from .errors import RentalError
from .models import (
    Equipment, FinanceCharge, FinanceEntry, MaintenanceCase, Rental, RentalFinanceSnapshot
)
from .roles import can_manage_finance, can_record_finance

Kind = FinanceEntry.Kind
CHARGE_ENTRIES = (Kind.DEPOSIT_APPLIED, Kind.WAIVER)
REVERSIBLE_ENTRIES = CASH_ENTRIES + CHARGE_ENTRIES
MAX_ENTRY_VND = 10**26 - 1
MAX_UNIT_DEPOSIT_VND = 2_147_483_647


class Ledger:
    """Balances from approved obligations and the journal's effective entries."""

    def __init__(self, rental, entries, charges):
        self.rental = rental
        self.charges = charges
        self.reversed_ids = {
            entry.reverses_id for entry in entries if entry.reverses_id
        }
        self.totals = Counter()
        self.waived = Counter()
        self.applied = Counter()
        for entry in entries:
            if entry.pk in self.reversed_ids or entry.kind == Kind.REVERSAL:
                continue
            self.totals[entry.kind] += int(entry.amount_vnd)
            if entry.kind == Kind.WAIVER:
                self.waived[entry.charge_id] += int(entry.amount_vnd)
            if entry.kind == Kind.DEPOSIT_APPLIED:
                self.applied[entry.charge_id] += int(entry.amount_vnd)
        self.legacy_pending = (
            not rental.finance_enabled and Kind.RECONCILIATION not in self.totals
        )
        self.rent_due = (
            0 if rental.status == Rental.Status.CANCELLED else int(rental.total_vnd)
        )
        self.deposit_required = sum(
            line.deposit_vnd * line.quantity for line in rental.lines.all()
        )
        self.fees = sum(
            int(charge.amount_vnd) - self.waived[charge.pk]
            for charge in charges
            if charge.status == FinanceCharge.Status.APPROVED
        )
        self.rent_cash = self.totals[Kind.RENT_RECEIPT] - self.totals[Kind.RENT_REFUND]
        self.deposit_held = (
            self.totals[Kind.DEPOSIT_RECEIPT]
            - self.totals[Kind.DEPOSIT_REFUND]
            - self.totals[Kind.DEPOSIT_APPLIED]
        )
        self.balance = (
            self.rent_due
            + self.fees
            - self.rent_cash
            - self.totals[Kind.DEPOSIT_APPLIED]
        )

    def charge_remaining(self, charge):
        return int(charge.amount_vnd) - self.waived[charge.pk] - self.applied[charge.pk]

    def can_settle(self):
        if self.legacy_pending:
            return False
        if self.rental.status == Rental.Status.CANCELLED:
            return True
        if self.rental.status not in (Rental.Status.RETURNED, Rental.Status.CLOSED):
            return False
        if any(
            charge.status == FinanceCharge.Status.PENDING for charge in self.charges
        ):
            return False
        if (
            rental_handovers(self.rental)
            .filter(returned_at__isnull=False, inspected_at__isnull=True)
            .exists()
        ):
            return False
        return (
            not MaintenanceCase.objects.filter(
                handover__reservation__line__rental=self.rental
            )
            .exclude(state=MaintenanceCase.State.RESOLVED)
            .exists()
        )

    def summary(self):
        can_settle = self.can_settle()
        deposit_due = (
            max(0, self.deposit_required - self.deposit_held)
            if self.rental.finance_enabled
            and self.rental.status in (Rental.Status.CONFIRMED, Rental.Status.PICKED_UP)
            else 0
        )
        return {
            "legacy_pending": self.legacy_pending,
            "can_settle": can_settle,
            "rent_vnd": self.rent_due,
            "fees_vnd": self.fees,
            "rent_received_vnd": self.totals[Kind.RENT_RECEIPT],
            "rent_refunded_vnd": self.totals[Kind.RENT_REFUND],
            "deposit_required_vnd": self.deposit_required,
            "deposit_received_vnd": self.totals[Kind.DEPOSIT_RECEIPT],
            "deposit_refunded_vnd": self.totals[Kind.DEPOSIT_REFUND],
            "deposit_applied_vnd": self.totals[Kind.DEPOSIT_APPLIED],
            "deposit_held_vnd": self.deposit_held,
            "balance_due_vnd": max(0, self.balance),
            "deposit_due_vnd": deposit_due,
            "rent_to_refund_vnd": max(0, -self.balance),
            "deposit_to_refund_vnd": self.deposit_held if can_settle else 0,
        }


def finance_summary(rental):
    return Ledger(
        rental, list(rental.finance_entries.all()), list(rental.finance_charges.all())
    ).summary()


def snapshot_values(ledger):
    return {
        "balance_due_vnd": 0 if ledger.legacy_pending else max(0, ledger.balance),
        "deposit_held_vnd": ledger.deposit_held,
        "legacy_pending": ledger.legacy_pending,
    }


def refresh_snapshot(rental):
    ledger = Ledger(rental, list(rental.finance_entries.all()), list(rental.finance_charges.all()))
    RentalFinanceSnapshot.objects.update_or_create(
        rental=rental, defaults=snapshot_values(ledger)
    )


def receivables(rentals):
    totals = rentals.aggregate(
        balance_due_vnd=Sum("finance_snapshot__balance_due_vnd", default=0),
        deposit_held_vnd=Sum("finance_snapshot__deposit_held_vnd", default=0),
        legacy_pending=Count("finance_snapshot", filter=Q(finance_snapshot__legacy_pending=True)),
    )
    for key, amount in _uncached_receivables(
        rentals.filter(finance_snapshot__isnull=True)
    ).items():
        totals[key] += amount
    return totals


def _uncached_receivables(rentals):
    totals = {"balance_due_vnd": 0, "deposit_held_vnd": 0, "legacy_pending": 0}
    for rental in rentals.prefetch_related(
        "lines", "finance_entries", "finance_charges"
    ).iterator(chunk_size=100):
        ledger = Ledger(
            rental,
            list(rental.finance_entries.all()),
            list(rental.finance_charges.all()),
        )
        for key, value in snapshot_values(ledger).items():
            totals[key] += value
    return totals


def period_movements(start, end):
    def movement(increases, decreases=()):
        return Case(
            When(kind__in=increases, then=F("amount_vnd")),
            When(kind__in=decreases, then=-F("amount_vnd")),
            When(
                kind=Kind.REVERSAL, reverses__kind__in=increases, then=-F("amount_vnd")
            ),
            When(
                kind=Kind.REVERSAL, reverses__kind__in=decreases, then=F("amount_vnd")
            ),
            default=Value(0),
            output_field=DecimalField(max_digits=26, decimal_places=0),
        )

    return (
        FinanceEntry.objects.filter(recorded_at__gte=start, recorded_at__lt=end)
        .annotate(
            rent_net_vnd=movement(
                (Kind.RENT_RECEIPT, Kind.DEPOSIT_APPLIED), (Kind.RENT_REFUND,)
            ),
            deposit_received_vnd=movement((Kind.DEPOSIT_RECEIPT,)),
            deposit_refunded_vnd=movement((Kind.DEPOSIT_REFUND,)),
        )
        .select_related("recorded_by", "reverses")
        .order_by("-recorded_at", "-pk")
    )


def finance_workspace(actor, rental_id):
    _require_clerk(actor)
    rental = Rental.objects.select_related("customer").get(pk=rental_id)
    entries = list(rental.finance_entries.select_related("recorded_by"))
    charges = list(
        rental.finance_charges.select_related(
            "handover__asset", "proposed_by", "reviewed_by"
        )
    )
    ledger = Ledger(rental, entries, charges)
    return {
        "rental": rental,
        "summary": ledger.summary(),
        "entries": entries,
        "charges": charges,
        "reversible": [
            entry
            for entry in entries
            if entry.kind in REVERSIBLE_ENTRIES and entry.pk not in ledger.reversed_ids
        ],
        "handovers": rental_handovers(rental).filter(picked_up_at__isnull=False),
    }


def require_payment_before_pickup(rental):
    if not rental.finance_enabled:
        return
    ledger = Ledger(rental, list(rental.finance_entries.all()), [])
    if ledger.balance > 0 or ledger.deposit_required > ledger.deposit_held:
        raise RentalError(
            "Cần ghi nhận đủ tiền thuê và cọc tại màn Quyết toán trước khi bàn giao.",
            409,
        )


def _require_clerk(actor):
    if not can_record_finance(actor):
        raise RentalError("Cần quyền ghi nhận giao dịch tại quầy.", 403)


def _require_manager(actor):
    if not can_manage_finance(actor):
        raise RentalError("Cần quyền quản lý quyết toán.", 403)


def _whole_vnd(value, *, minimum=1, maximum=MAX_ENTRY_VND):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise RentalError("Nhập số tiền VND nguyên hợp lệ.") from None
    if (
        not amount.is_finite()
        or not minimum <= amount <= maximum
        or amount != amount.to_integral_value()
    ):
        raise RentalError("Nhập số tiền VND nguyên trong giới hạn cho phép.")
    return int(amount)


def _notes(value, *, required=True):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or (required and not value.strip())
    ):
        raise RentalError("Ghi lý do hoặc chứng từ từ 1 đến 2.000 ký tự.")
    return value.strip()


def _command_id(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise RentalError("Mã giao dịch không hợp lệ.") from None


def _retry(existing, values):
    if existing and any(
        getattr(existing, field) != value for field, value in values.items()
    ):
        raise RentalError("Mã giao dịch đã được dùng cho nội dung khác.", 409)
    return existing


@transaction.atomic
def set_equipment_deposit(actor, equipment_id, amount_vnd):
    _require_manager(actor)
    amount = _whole_vnd(amount_vnd, minimum=0, maximum=MAX_UNIT_DEPOSIT_VND)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    equipment.deposit_vnd = amount
    equipment.save(update_fields=["deposit_vnd"])
    return equipment


def _check_entry(ledger, entry, target):
    kind = entry.kind
    amount = entry.amount_vnd
    if kind in RECEIPTS:
        if not ledger.rental.finance_enabled:
            return
        if ledger.rental.status == Rental.Status.CANCELLED:
            raise RentalError("Đơn đã hủy chỉ còn xử lý hoàn tiền.", 409)
        limit = (
            ledger.balance
            if kind == Kind.RENT_RECEIPT
            else ledger.deposit_required - ledger.deposit_held
        )
        if kind == Kind.DEPOSIT_RECEIPT and ledger.rental.status not in (
            Rental.Status.CONFIRMED,
            Rental.Status.PICKED_UP,
        ):
            raise RentalError("Đơn đã nhận trả không phát sinh khoản thu cọc.", 409)
        if amount > limit:
            raise RentalError("Số thu vượt khoản còn phải thu.", 409)
    elif kind in REFUNDS:
        limit = -ledger.balance if kind == Kind.RENT_REFUND else ledger.deposit_held
        if not ledger.can_settle() or amount > limit:
            raise RentalError(
                "Đơn chưa đủ điều kiện hoàn hoặc số hoàn vượt số dư.", 409
            )
    elif kind in CHARGE_ENTRIES:
        charge = entry.charge
        limit = ledger.charge_remaining(charge)
        if kind == Kind.DEPOSIT_APPLIED:
            if not ledger.can_settle():
                raise RentalError("Đơn chưa đủ điều kiện khấu trừ cọc.", 409)
            limit = min(limit, ledger.deposit_held, ledger.balance)
        if charge.status != FinanceCharge.Status.APPROVED or amount > limit:
            raise RentalError(
                "Khoản thu chưa duyệt hoặc số tiền vượt phần còn lại.", 409
            )
    elif kind == Kind.REVERSAL:
        if target.kind not in REVERSIBLE_ENTRIES or target.pk in ledger.reversed_ids:
            raise RentalError("Giao dịch này không thể đảo.", 409)
    elif kind == Kind.RECONCILIATION and not ledger.legacy_pending:
        raise RentalError("Đơn này đã đối soát hoặc thuộc quy trình mới.", 409)


@transaction.atomic
def post_finance_entry(
    actor,
    rental_id,
    *,
    kind,
    command_id,
    amount_vnd=None,
    method="",
    notes="",
    charge_id=None,
    entry_id=None,
):
    _require_clerk(actor)
    if kind not in Kind.values:
        raise RentalError("Chọn loại giao dịch hợp lệ.")
    # Finance-only writes lock the rental and never acquire an Equipment lock.
    rental = Rental.objects.select_for_update().get(pk=rental_id)
    legacy_receipt = not rental.finance_enabled and kind in RECEIPTS
    if kind not in CASH_ENTRIES or legacy_receipt:
        _require_manager(actor)
    command = _command_id(command_id)
    notes = _notes(notes, required=kind not in CASH_ENTRIES or legacy_receipt)
    if (kind in CASH_ENTRIES and method not in FinanceEntry.Method.values) or (
        kind not in CASH_ENTRIES and method
    ):
        raise RentalError("Chọn phương thức giao dịch hợp lệ.")
    if (charge_id is not None) != (kind in CHARGE_ENTRIES) or (
        entry_id is not None
    ) != (kind == Kind.REVERSAL):
        raise RentalError("Chọn đúng hồ sơ hoặc giao dịch gốc.")

    charge = (
        rental.finance_charges.get(pk=charge_id) if kind in CHARGE_ENTRIES else None
    )
    target = rental.finance_entries.get(pk=entry_id) if kind == Kind.REVERSAL else None
    if kind in (Kind.REVERSAL, Kind.RECONCILIATION):
        if amount_vnd is not None:
            raise RentalError("Số tiền được xác định từ giao dịch gốc.")
        amount = int(target.amount_vnd) if target else 0
    else:
        amount = _whole_vnd(amount_vnd)
    values = {
        "kind": kind,
        "amount_vnd": amount,
        "method": method,
        "notes": notes,
        "charge_id": charge_id,
        "reverses_id": entry_id,
        "recorded_by_id": actor.pk,
    }
    existing = _retry(rental.finance_entries.filter(command_id=command).first(), values)
    if existing:
        return existing

    entries = list(rental.finance_entries.all())
    charges = list(rental.finance_charges.all())
    ledger = Ledger(rental, entries, charges)
    entry = FinanceEntry(rental=rental, command_id=command, **values)
    if charge:
        entry.charge = charge
    _check_entry(ledger, entry, target)
    if target:
        revised = Ledger(rental, [*entries, entry], charges)
        if revised.rent_cash < 0 or revised.deposit_held < 0:
            raise RentalError(
                "Cần điều chỉnh các giao dịch sử dụng khoản tiền này trước.", 409
            )
    entry.shift = locked_shift_for_entry(kind, target)
    entry.save()
    refresh_snapshot(rental)
    return entry


def _source_incident(rental, reason, handover_id):
    if handover_id is None:
        if (
            reason == FinanceCharge.Reason.LATE
            and rental.was_returned_late
            and not rental_handovers(rental).filter(picked_up_at__isnull=False).exists()
        ):
            return None
        raise RentalError("Chọn lượt giao nhận có dữ liệu chứng minh khoản thu.", 409)
    handover = rental_handovers(rental).get(pk=handover_id, picked_up_at__isnull=False)
    if reason == FinanceCharge.Reason.LATE:
        if (
            not handover.returned_at
            or timezone.localdate(handover.returned_at) <= rental.return_date
        ):
            raise RentalError("Lượt giao nhận này chưa ghi nhận trả trễ.", 409)
        return None
    incident = handover.incidents.filter(kind=reason).first()
    if reason == FinanceCharge.Reason.LOST and not handover.lost_at:
        raise RentalError("Cần có xác nhận mất trước khi đề xuất khoản thu.", 409)
    if not incident and handover.inspection_result != reason:
        raise RentalError(
            "Lượt giao nhận không có kết quả kiểm tra hoặc sự cố tương ứng.", 409
        )
    return incident


@transaction.atomic
def propose_finance_charge(
    actor, rental_id, *, command_id, reason, amount_vnd, notes, handover_id=None
):
    _require_clerk(actor)
    rental = Rental.objects.select_for_update().get(pk=rental_id)
    if reason not in FinanceCharge.Reason.values:
        raise RentalError("Chọn nguyên nhân khoản thu hợp lệ.")
    command = _command_id(command_id)
    values = {
        "reason": reason,
        "amount_vnd": _whole_vnd(amount_vnd),
        "notes": _notes(notes),
        "handover_id": handover_id,
        "proposed_by_id": actor.pk,
    }
    existing = _retry(rental.finance_charges.filter(command_id=command).first(), values)
    if existing:
        return existing
    incident = _source_incident(rental, reason, handover_id)
    if (
        rental.finance_charges.filter(reason=reason, handover_id=handover_id)
        .exclude(status=FinanceCharge.Status.REJECTED)
        .exists()
    ):
        raise RentalError("Lượt giao nhận này đã có khoản thu cùng lý do.", 409)
    return FinanceCharge.objects.create(
        rental=rental, incident=incident, command_id=command, **values
    )


@transaction.atomic
def review_finance_charge(actor, rental_id, charge_id, *, approve, notes):
    _require_manager(actor)
    rental = Rental.objects.select_for_update().get(pk=rental_id)
    charge = rental.finance_charges.get(pk=charge_id)
    if type(approve) is not bool:
        raise RentalError("Chọn quyết định hợp lệ.")
    notes = _notes(notes)
    decision = (
        FinanceCharge.Status.APPROVED if approve else FinanceCharge.Status.REJECTED
    )
    if charge.status != FinanceCharge.Status.PENDING:
        if (
            charge.status == decision
            and charge.reviewed_by_id == actor.pk
            and charge.review_note == notes
        ):
            return charge
        raise RentalError("Khoản thu đã được xử lý.", 409)
    charge.status = decision
    charge.reviewed_by = actor
    charge.reviewed_at = timezone.now()
    charge.review_note = notes
    charge.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    refresh_snapshot(rental)
    return charge
