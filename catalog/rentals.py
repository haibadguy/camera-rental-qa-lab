from django.db import transaction
from django.db.models import TextChoices
from django.utils import timezone

from .errors import RentalError
from .inventory import (
    available_stock,
    checked_out_assets,
    checked_out_quantity,
    free_assets,
    validate_period,
)
from .models import AssetReservation, Equipment, Rental, RentalLine

MIN_RENTAL_QUANTITY = 1
MAX_RENTAL_QUANTITY = 2_147_483_647


class StaffRentalQueue(TextChoices):
    ALL = "all", "Tất cả"
    PICKUP_TODAY = "pickup-today", "Nhận hôm nay"
    RETURN_TODAY = "return-today", "Trả hôm nay"
    OVERDUE = "overdue", "Quá hạn"


def can_cancel(rental, today):
    return rental.status == Rental.Status.CONFIRMED and today < rental.pickup_date


def can_pick_up(rental, today):
    return (
        rental.status == Rental.Status.CONFIRMED
        and rental.pickup_date <= today < rental.return_date
    )


def can_mark_no_show(rental, today):
    return rental.status == Rental.Status.CONFIRMED and today > rental.pickup_date


def can_return(rental):
    return rental.status == Rental.Status.PICKED_UP


def book_rental(customer, equipment_id, pickup_date, return_date, quantity):
    return book_order(
        customer,
        pickup_date,
        return_date,
        [{"equipment_id": equipment_id, "quantity": quantity}],
        require_assets=False,
    )


@transaction.atomic
def book_order(customer, pickup_date, return_date, lines, *, require_assets=True):
    if not customer.is_authenticated:
        raise RentalError("Cần đăng nhập để đặt thuê.", 403)
    validate_period(pickup_date, return_date)
    quantities = {}
    for line in lines:
        equipment_id, quantity = line["equipment_id"], line["quantity"]
        if (
            type(quantity) is not int
            or not MIN_RENTAL_QUANTITY <= quantity <= MAX_RENTAL_QUANTITY
        ):
            raise RentalError(
                "Số lượng phải là số nguyên dương trong giới hạn cho phép."
            )
        if equipment_id in quantities:
            raise RentalError("Mỗi mẫu thiết bị chỉ được xuất hiện một lần trong đơn.")
        quantities[equipment_id] = quantity
    if not quantities:
        raise RentalError("Chọn ít nhất một thiết bị.")

    equipment = list(
        Equipment.objects.select_for_update().filter(pk__in=quantities).order_by("pk")
    )
    if len(equipment) != len(quantities):
        raise Equipment.DoesNotExist
    days = (return_date - pickup_date).days
    rental_lines = []
    assignments = {}
    for item in equipment:
        quantity = quantities[item.pk]
        if not item.is_active:
            raise RentalError(f"{item.code} đã ngừng nhận đơn thuê mới.", 409)
        if item.tracks_assets:
            assets = free_assets([item.pk], pickup_date, return_date)
            assignments[item.pk] = list(assets.values_list("pk", flat=True)[:quantity])
            enough = len(assignments[item.pk]) == quantity
        elif require_assets or len(quantities) > 1:
            raise RentalError(f"{item.code} chưa bật giữ theo mã kho.", 409)
        else:
            enough = quantity <= available_stock(item, pickup_date, return_date)
        if not enough:
            raise RentalError(
                f"Không đủ thiết bị cho kỳ thuê đã chọn. Mẫu: {item.code}.", 409
            )
        rental_lines.append(
            RentalLine(
                equipment=item,
                quantity=quantity,
                daily_rate_vnd=item.daily_rate_vnd,
                total_vnd=days * quantity * item.daily_rate_vnd,
            )
        )

    projection = {}
    if len(rental_lines) == 1:
        line = rental_lines[0]
        projection = {
            "equipment": line.equipment,
            "quantity": line.quantity,
            "daily_rate_vnd": line.daily_rate_vnd,
        }
    rental = Rental.objects.create(
        customer=customer,
        pickup_date=pickup_date,
        return_date=return_date,
        total_vnd=sum(line.total_vnd for line in rental_lines),
        **projection,
    )
    for line in rental_lines:
        line.rental = rental
    RentalLine.objects.bulk_create(rental_lines)
    AssetReservation.objects.bulk_create(
        [
            AssetReservation(
                line=line, asset_id=asset_id, period=(pickup_date, return_date)
            )
            for line in rental_lines
            for asset_id in assignments.get(line.equipment_id, ())
        ]
    )
    return rental


def customer_rentals(customer, *, legacy_only=False):
    rentals = Rental.objects.filter(customer=customer).select_related("equipment")
    return rentals.filter(equipment__isnull=False) if legacy_only else rentals


def staff_rentals(queue):
    today = timezone.localdate()
    filters = {
        StaffRentalQueue.PICKUP_TODAY: {
            "status": Rental.Status.CONFIRMED,
            "pickup_date": today,
        },
        StaffRentalQueue.RETURN_TODAY: {
            "status": Rental.Status.PICKED_UP,
            "return_date": today,
        },
        StaffRentalQueue.OVERDUE: {
            "status": Rental.Status.PICKED_UP,
            "return_date__lt": today,
        },
    }
    return (
        Rental.objects.filter(**filters.get(queue, {}))
        .select_related("equipment", "customer")
        .prefetch_related("lines__equipment")
    )


def _lock_rental(rentals, rental_id, *, legacy_only=False):
    if legacy_only:
        rentals = rentals.filter(equipment__isnull=False)
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


@transaction.atomic
def cancel_rental(customer, rental_id, *, legacy_only=False):
    rental, _ = _lock_rental(
        customer_rentals(customer), rental_id, legacy_only=legacy_only
    )
    if not can_cancel(rental, timezone.localdate()):
        raise RentalError("Chỉ hủy được đơn đã đặt trước ngày nhận.", 409)
    rental.status = Rental.Status.CANCELLED
    rental.save(update_fields=["status"])
    _release_reservations(rental)
    return rental


@transaction.atomic
def pick_up_rental(staff, rental_id, *, legacy_only=False):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được ghi nhận bàn giao.", 403)
    rental, equipment = _lock_rental(
        Rental.objects.all(), rental_id, legacy_only=legacy_only
    )
    now = timezone.now()
    if not can_pick_up(rental, timezone.localdate(now)):
        raise RentalError(
            "Chỉ bàn giao đơn đã đặt từ ngày nhận đến trước ngày trả.", 409
        )
    reservations = AssetReservation.objects.filter(
        line__rental=rental, released_at__isnull=True
    )
    if all(item.tracks_assets for item in equipment):
        expected = sum(rental.lines.values_list("quantity", flat=True))
        enough = (
            reservations.count() == expected
            and not checked_out_assets()
            .filter(asset_id__in=reservations.values("asset_id"))
            .exists()
        )
    else:
        item = equipment[0]
        enough = rental.quantity <= item.total_stock - checked_out_quantity(item)
    if not enough:
        raise RentalError(
            "Không đủ thiết bị thực tế để bàn giao. Kiểm tra các đơn chưa trả.", 409
        )
    rental.status = Rental.Status.PICKED_UP
    rental.picked_up_at = now
    rental.save(update_fields=["status", "picked_up_at"])
    return rental


@transaction.atomic
def mark_no_show(staff, rental_id, *, legacy_only=False):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được xử lý khách không đến nhận.", 403)
    rental, _ = _lock_rental(Rental.objects.all(), rental_id, legacy_only=legacy_only)
    if not can_mark_no_show(rental, timezone.localdate()):
        raise RentalError("Chỉ xử lý đơn chưa bàn giao sau ngày nhận.", 409)
    rental.status = Rental.Status.CANCELLED
    rental.cancellation_reason = Rental.CancellationReason.NO_SHOW
    rental.save(update_fields=["status", "cancellation_reason"])
    _release_reservations(rental)
    return rental


@transaction.atomic
def return_rental(staff, rental_id, *, legacy_only=False):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được ghi nhận trả.", 403)
    rental, _ = _lock_rental(Rental.objects.all(), rental_id, legacy_only=legacy_only)
    now = timezone.now()
    if not can_return(rental) or now < rental.picked_up_at:
        raise RentalError("Chỉ ghi nhận trả đơn đã bàn giao.", 409)
    rental.status = Rental.Status.RETURNED
    rental.returned_at = now
    rental.save(update_fields=["status", "returned_at"])
    return rental


def _release_reservations(rental):
    AssetReservation.objects.filter(
        line__rental=rental, released_at__isnull=True
    ).update(released_at=timezone.now())


def can_replace_asset(rental, today):
    return rental.status == Rental.Status.CONFIRMED and today < rental.return_date


@transaction.atomic
def replace_reserved_asset(staff, rental_id, reservation_id, replacement_code):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được đổi thiết bị đã giữ.", 403)
    rental, _ = _lock_rental(Rental.objects.all(), rental_id)
    old = AssetReservation.objects.select_related("line").get(
        pk=reservation_id, line__rental=rental
    )
    if (
        not can_replace_asset(rental, timezone.localdate())
        or old.released_at is not None
    ):
        raise RentalError(
            "Chỉ đổi thiết bị đang giữ cho đơn chưa bàn giao và còn hạn.", 409
        )
    replacement = (
        free_assets([old.line.equipment_id], rental.pickup_date, rental.return_date)
        .filter(code=replacement_code.strip())
        .first()
    )
    if replacement is None:
        raise RentalError("Máy thay thế phải cùng mẫu và khả dụng suốt kỳ.", 409)
    old.released_at = timezone.now()
    old.save(update_fields=["released_at"])
    return AssetReservation.objects.create(
        asset=replacement,
        line=old.line,
        period=old.period,
        replaces=old,
        changed_by=staff,
    )
