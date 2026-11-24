from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .errors import RentalError
from .inventory import checked_out_assets
from .models import (
    AssetHandover,
    AssetReservation,
    AssetUnit,
    Equipment,
    Rental,
    RentalLine,
)
from .roles import can_operate


def lock_rental(rentals, rental_id, *, legacy_only=False):
    if legacy_only:
        rentals = rentals.filter(equipment__isnull=False).exclude(
            status=Rental.Status.CLOSED
        )
    equipment_id = rentals.values_list("equipment_id", flat=True).get(pk=rental_id)
    equipment_ids = (
        [equipment_id]
        if equipment_id
        else RentalLine.objects.filter(rental_id=rental_id).values_list(
            "equipment_id", flat=True
        )
    )
    equipment = list(
        Equipment.objects.select_for_update()
        .filter(pk__in=equipment_ids)
        .order_by("pk")
    )
    rental = rentals.select_related(None).select_for_update().get(pk=rental_id)
    return rental, equipment


def rental_handovers(rental):
    return (
        AssetHandover.objects.filter(reservation__line__rental=rental)
        .select_related(
            "asset",
            "prepared_by",
            "picked_up_by",
            "returned_by",
            "inspected_by",
            "lost_by",
        )
        .order_by("id")
    )


def receipt_summary(rental):
    return (
        rental_handovers(rental)
        .filter(picked_up_at__isnull=False)
        .aggregate(
            picked_up=Count("pk"),
            returned=Count("pk", filter=Q(returned_at__isnull=False)),
            lost=Count("pk", filter=Q(lost_at__isnull=False)),
        )
    )


def lock_handover_context(actor, rental_id, handover_id):
    if not can_operate(actor):
        raise RentalError("Cần quyền vận hành cho thuê.", 403)
    rental, _ = lock_rental(Rental.objects.all(), rental_id)
    handover = AssetHandover.objects.select_for_update(of=("self",)).get(
        pk=handover_id,
        reservation__line__rental=rental,
        reservation__released_at__isnull=True,
        picked_up_at__isnull=False,
    )
    return rental, handover


@transaction.atomic
def prepare_asset(staff, rental_id, reservation_id, notes=""):
    if not can_operate(staff):
        raise RentalError("Cần quyền chuẩn bị thiết bị.", 403)
    rental, _ = lock_rental(Rental.objects.all(), rental_id)
    reservation = AssetReservation.objects.select_related(
        "asset", "line__equipment"
    ).get(pk=reservation_id, line__rental=rental, released_at__isnull=True)
    return prepare_locked(staff, rental, reservation, notes)


def prepare_locked(staff, rental, reservation, notes=""):
    if (
        rental.status != Rental.Status.CONFIRMED
        or rental.return_date <= timezone.localdate()
    ):
        raise RentalError("Đơn phải còn hạn và chưa bàn giao.", 409)
    if (
        reservation.asset.status != AssetUnit.Status.READY
        or checked_out_assets().filter(asset=reservation.asset).exists()
    ):
        raise RentalError("Tài sản chưa sẵn sàng trong kho.", 409)
    if not isinstance(notes, str) or len(notes) > 2000:
        raise RentalError("Ghi chú tối đa 2000 ký tự.")
    handover, created = AssetHandover.objects.get_or_create(
        reservation=reservation,
        defaults={
            "asset": reservation.asset,
            "prepared_by": staff,
            "expected_accessories": reservation.line.equipment.accessory_checklist,
            "pickup_notes": notes.strip(),
        },
    )
    if not created:
        raise RentalError("Tài sản này đã được xác nhận chuẩn bị.", 409)
    return handover


def confirm_asset_pickup(staff, rental, now):
    if not can_operate(staff):
        raise RentalError("Cần quyền vận hành để bàn giao theo mã kho.", 403)
    holds = AssetReservation.objects.filter(
        line__rental=rental, released_at__isnull=True
    )
    expected = sum(rental.lines.values_list("quantity", flat=True))
    if (
        holds.count() != expected
        or checked_out_assets().filter(asset_id__in=holds.values("asset_id")).exists()
    ):
        raise RentalError(
            "Không đủ thiết bị thực tế để bàn giao. Kiểm tra các đơn chưa trả.", 409
        )
    prepared = AssetHandover.objects.filter(
        reservation__in=holds,
        asset__status=AssetUnit.Status.READY,
        picked_up_at__isnull=True,
    )
    if prepared.count() != expected:
        raise RentalError(
            f"Chuẩn bị đủ mã kho sẵn sàng tại /staff/rentals/{rental.pk}/operations/ "
            f"hoặc /api/v2/operations/rentals/{rental.pk}/ trước khi bàn giao.",
            409,
        )
    prepared.update(picked_up_at=now, picked_up_by=staff)


@transaction.atomic
def receive_asset(staff, rental_id, handover_id):
    rental, handover = lock_handover_context(staff, rental_id, handover_id)
    receive_locked(staff, rental, handover)
    sync_rental_return(rental)
    return handover


def receive_locked(staff, rental, handover):
    if (
        rental.status != Rental.Status.PICKED_UP
        or not handover.picked_up_at
        or handover.returned_at
        or handover.lost_at
    ):
        raise RentalError("Tài sản không còn ở trạng thái đang thuê.", 409)
    handover.returned_at = timezone.now()
    handover.returned_by = staff
    handover.save(update_fields=["returned_at", "returned_by"])
    AssetUnit.objects.filter(
        pk=handover.asset_id, status=AssetUnit.Status.READY
    ).update(status=AssetUnit.Status.INSPECTION)


def record_asset_inspection(staff, rental_id, handover_id, result, notes):
    _, handover = lock_handover_context(staff, rental_id, handover_id)
    if not handover.returned_at or handover.inspected_at or handover.lost_at:
        raise RentalError("Chỉ kiểm tra tài sản đã nhận về và chưa được kiểm.", 409)
    if (
        not isinstance(notes, str)
        or len(notes) > 2000
        or result not in AssetHandover.Inspection.values
    ):
        raise RentalError("Kết quả hoặc ghi chú kiểm tra không hợp lệ.")
    notes = notes.strip()
    if result != AssetHandover.Inspection.READY and not notes:
        raise RentalError("Ghi rõ hư hỏng hoặc phụ kiện còn thiếu.")
    handover.inspection_result = result
    handover.inspected_at = timezone.now()
    handover.inspected_by = staff
    handover.return_notes = notes
    handover.save(
        update_fields=[
            "inspection_result",
            "inspected_at",
            "inspected_by",
            "return_notes",
        ]
    )
    return handover


def sync_rental_return(rental):
    if rental.status != Rental.Status.PICKED_UP:
        return
    handovers = rental_handovers(rental).filter(picked_up_at__isnull=False)
    if handovers.filter(returned_at__isnull=True, lost_at__isnull=True).exists():
        return
    if handovers.filter(lost_at__isnull=False).exists():
        rental.status = Rental.Status.CLOSED
        rental.closed_at = timezone.now()
        rental.save(update_fields=["status", "closed_at"])
    else:
        latest_receipt = (
            handovers.order_by("-returned_at")
            .values_list("returned_at", flat=True)
            .first()
        )
        if latest_receipt is not None:
            rental.status = Rental.Status.RETURNED
            rental.returned_at = latest_receipt
            rental.save(update_fields=["status", "returned_at"])
