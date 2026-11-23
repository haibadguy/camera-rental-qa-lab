from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .custody import lock_rental
from .errors import RentalError
from .inventory import MAX_RENTAL_DAYS, free_assets, validate_period
from .models import (
    AssetHandover,
    AssetReservation,
    Rental,
    RentalChangeRequest,
    RentalLine,
)
from .rentals import customer_rentals
from .roles import can_operate


def _owned_rentals(customer):
    if not customer.is_authenticated:
        raise RentalError("Cần đăng nhập để gửi yêu cầu đổi kỳ.", 403)
    return customer_rentals(customer)


def _validate_dates(rental, kind, pickup_date, return_date):
    if type(pickup_date) is not date or type(return_date) is not date:
        raise RentalError("Ngày nhận và ngày trả không hợp lệ.")

    if kind == RentalChangeRequest.Kind.RESCHEDULE:
        if rental.status != Rental.Status.CONFIRMED:
            raise RentalError("Chỉ đổi lịch cho đơn chưa bàn giao.", 409)
        validate_period(pickup_date, return_date)
        if (pickup_date, return_date) == (rental.pickup_date, rental.return_date):
            raise RentalError("Kỳ mới phải khác kỳ đang thuê.")
        return

    if kind != RentalChangeRequest.Kind.EXTEND:
        raise RentalError("Loại yêu cầu không hợp lệ.")
    if (
        rental.status != Rental.Status.PICKED_UP
        or rental.return_date < timezone.localdate()
    ):
        raise RentalError("Chỉ gia hạn đơn đã bàn giao và chưa quá hạn.", 409)
    if pickup_date != rental.pickup_date or return_date <= rental.return_date:
        raise RentalError("Gia hạn giữ nguyên ngày nhận và cần ngày trả muộn hơn.")
    if (return_date - pickup_date).days > MAX_RENTAL_DAYS:
        raise RentalError(f"Tổng kỳ thuê tối đa {MAX_RENTAL_DAYS} ngày.")


def _assignments(rental, lines):
    if not lines or any(not line.equipment.tracks_assets for line in lines):
        raise RentalError("Đơn chưa đủ dữ liệu mã kho để đổi lịch hoặc gia hạn.", 409)

    by_line = defaultdict(list)
    reservations = (
        AssetReservation.objects.filter(line__rental=rental, released_at__isnull=True)
        .select_related("asset")
        .order_by("pk")
    )
    for hold in reservations:
        by_line[hold.line_id].append(hold)

    for line in lines:
        holds = by_line[line.pk]
        if len(holds) != line.quantity or any(
            hold.asset.equipment_id != line.equipment_id
            or hold.period.lower != rental.pickup_date
            or hold.period.upper != rental.return_date
            for hold in holds
        ):
            raise RentalError(
                "Lịch giữ của đơn cần được đối soát trước khi đổi kỳ.", 409
            )
    return by_line


def _validate_custody(rental, assignments):
    handovers = list(
        AssetHandover.objects.filter(
            reservation__line__rental=rental, picked_up_at__isnull=False
        ).values("reservation_id", "returned_at", "lost_at")
    )
    if any(row["returned_at"] or row["lost_at"] for row in handovers):
        raise RentalError(
            "Không gia hạn sau khi đã trả hoặc đóng ngoại lệ một món.", 409
        )
    required = {hold.pk for holds in assignments.values() for hold in holds}
    if {row["reservation_id"] for row in handovers} != required:
        raise RentalError(
            "Thiếu ghi nhận bàn giao theo mã kho để gia hạn đơn này.", 409
        )


def change_kind(rental):
    if rental.status == Rental.Status.CONFIRMED:
        kind = RentalChangeRequest.Kind.RESCHEDULE
    elif (
        rental.status == Rental.Status.PICKED_UP
        and rental.return_date >= timezone.localdate()
    ):
        kind = RentalChangeRequest.Kind.EXTEND
    else:
        return None
    try:
        holds = _assignments(rental, rental.lines.select_related("equipment"))
        if kind == RentalChangeRequest.Kind.EXTEND:
            _validate_custody(rental, holds)
    except RentalError:
        return None
    return kind


def _proposal(rental, kind, pickup_date, return_date):
    _validate_dates(rental, kind, pickup_date, return_date)
    lines = list(rental.lines.select_related("equipment"))
    holds = _assignments(rental, lines)
    if kind == RentalChangeRequest.Kind.EXTEND:
        _validate_custody(rental, holds)
    days = (return_date - pickup_date).days
    for line in lines:
        line.total_vnd = Decimal(line.quantity * line.daily_rate_vnd * days)
    new_total = sum(line.total_vnd for line in lines)
    quote = {
        "kind": kind,
        "pickup_date": pickup_date,
        "return_date": return_date,
        "old_total_vnd": rental.total_vnd,
        "total_vnd": new_total,
        "consent_required": rental.total_vnd != new_total,
    }
    return lines, holds, quote


def preview_rental_change(customer, rental_id, kind, pickup_date, return_date):
    rental = _owned_rentals(customer).get(pk=rental_id)
    _, _, quote = _proposal(rental, kind, pickup_date, return_date)
    return quote


@transaction.atomic
def request_rental_change(
    customer, rental_id, kind, pickup_date, return_date, accepted_total_vnd=None
):
    rental, _ = lock_rental(_owned_rentals(customer), rental_id)
    _, _, quote = _proposal(rental, kind, pickup_date, return_date)
    if accepted_total_vnd is not None or quote["consent_required"]:
        try:
            accepted = Decimal(str(accepted_total_vnd))
        except (InvalidOperation, ValueError):
            raise RentalError("Cần xác nhận tổng tiền của kỳ mới.") from None
        if not accepted.is_finite() or accepted != quote["total_vnd"]:
            raise RentalError("Tổng tiền đã thay đổi. Tính lại giá rồi xác nhận.", 409)
    return RentalChangeRequest.objects.create(
        rental=rental,
        kind=kind,
        pickup_date=pickup_date,
        return_date=return_date,
        old_pickup_date=rental.pickup_date,
        old_return_date=rental.return_date,
        old_total_vnd=rental.total_vnd,
        quoted_total_vnd=quote["total_vnd"],
        requested_by=customer,
    )


def _reschedule_holds(rental, change, lines, assignments, staff, now):
    replacements = []
    for line in lines:
        if not line.equipment.is_active:
            raise RentalError("Mẫu thiết bị đã ngừng nhận lịch mới.", 409)
        available = set(
            free_assets(
                [line.equipment_id],
                change.pickup_date,
                change.return_date,
                exclude_rental_id=rental.pk,
            ).values_list("pk", flat=True)
        )
        if len(available) < line.quantity:
            raise RentalError(
                f"Không đủ thiết bị cho kỳ mới. Mẫu: {line.equipment.code}.", 409
            )
        holds = assignments[line.pk]
        kept = {hold.asset_id for hold in holds} & available
        other_assets = iter(sorted(available - kept))
        for hold in holds:
            replacements.append(
                AssetReservation(
                    asset_id=hold.asset_id
                    if hold.asset_id in kept
                    else next(other_assets),
                    line=line,
                    period=(change.pickup_date, change.return_date),
                    replaces=hold,
                    changed_by=staff,
                )
            )
    AssetReservation.objects.filter(
        pk__in=[replacement.replaces_id for replacement in replacements]
    ).update(released_at=now)
    AssetReservation.objects.bulk_create(replacements)


def _extend_holds(rental, change, lines, assignments):
    reservation_ids = []
    for line in lines:
        holds = assignments[line.pk]
        asset_ids = {hold.asset_id for hold in holds}
        available = (
            free_assets(
                [line.equipment_id],
                rental.return_date,
                change.return_date,
                exclude_rental_id=rental.pk,
            )
            .filter(pk__in=asset_ids)
            .count()
        )
        if available != len(asset_ids):
            raise RentalError(
                f"Thiết bị đang giao có lịch xung đột hoặc không khả dụng. Mẫu: {line.equipment.code}.",
                409,
            )
        reservation_ids.extend(hold.pk for hold in holds)
    AssetReservation.objects.filter(pk__in=reservation_ids).update(
        period=(rental.pickup_date, change.return_date)
    )


@transaction.atomic
def review_rental_change(staff, change_id, approve, review_note=""):
    if not can_operate(staff):
        raise RentalError("Chỉ nhân viên có quyền vận hành được duyệt đổi kỳ.", 403)
    if type(approve) is not bool:
        raise RentalError("Kết quả duyệt không hợp lệ.")
    if not isinstance(review_note, str):
        raise RentalError("Ghi chú duyệt không hợp lệ.")
    review_note = review_note.strip()
    limit = RentalChangeRequest._meta.get_field("review_note").max_length
    if limit is not None and len(review_note) > limit:
        raise RentalError(f"Ghi chú duyệt không được quá {limit} ký tự.")
    rental_id = RentalChangeRequest.objects.values_list("rental_id", flat=True).get(
        pk=change_id
    )
    rental, _ = lock_rental(Rental.objects.all(), rental_id)
    change = RentalChangeRequest.objects.select_for_update().get(pk=change_id)
    if change.status != RentalChangeRequest.Status.PENDING:
        raise RentalError("Yêu cầu đã được xử lý.", 409)

    now = timezone.now()
    if approve:
        if (rental.pickup_date, rental.return_date, rental.total_vnd) != (
            change.old_pickup_date,
            change.old_return_date,
            change.old_total_vnd,
        ):
            raise RentalError("Kỳ thuê hoặc giá đã thay đổi. Cần yêu cầu mới.", 409)
        lines, assignments, quote = _proposal(
            rental, change.kind, change.pickup_date, change.return_date
        )
        if quote["total_vnd"] != change.quoted_total_vnd:
            raise RentalError("Giá đã thay đổi. Khách cần xác nhận lại tổng tiền.", 409)
        if change.kind == RentalChangeRequest.Kind.RESCHEDULE:
            _reschedule_holds(rental, change, lines, assignments, staff, now)
        else:
            _extend_holds(rental, change, lines, assignments)

        RentalLine.objects.bulk_update(lines, ["total_vnd"])
        rental.pickup_date = change.pickup_date
        rental.return_date = change.return_date
        rental.total_vnd = change.quoted_total_vnd
        rental.save(update_fields=["pickup_date", "return_date", "total_vnd"])

    change.status = (
        RentalChangeRequest.Status.APPROVED
        if approve
        else RentalChangeRequest.Status.REJECTED
    )
    change.reviewed_at = now
    change.reviewed_by = staff
    change.review_note = review_note
    change.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_note"])
    return change
