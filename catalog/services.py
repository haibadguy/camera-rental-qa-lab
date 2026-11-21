from collections import defaultdict

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Equipment, Rental


class RentalError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


MAX_RENTAL_DAYS = 30


def catalog_items(*, search="", kind=""):
    equipment = Equipment.objects.filter(is_active=True)
    if search:
        equipment = equipment.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )
    if kind:
        equipment = equipment.filter(kind=kind)
    return equipment


def validate_period(pickup_date, return_date):
    if pickup_date < timezone.localdate():
        raise RentalError("Ngày nhận phải từ hôm nay trở đi.")
    if return_date <= pickup_date:
        raise RentalError("Ngày trả phải sau ngày nhận.")
    if (return_date - pickup_date).days > MAX_RENTAL_DAYS:
        raise RentalError(f"Thời gian thuê tối đa {MAX_RENTAL_DAYS} ngày.")


def _scheduled_reservations(start, end=None):
    # An early return frees a physical unit while its original booking stays on the calendar.
    reservations = Rental.objects.filter(
        status__in=(
            Rental.Status.CONFIRMED,
            Rental.Status.PICKED_UP,
            Rental.Status.RETURNED,
        ),
        return_date__gt=start,
    )
    if end is not None:
        reservations = reservations.filter(pickup_date__lt=end)
    return reservations.order_by()


def _peak_reserved(reservations, start, end=None):
    changes = defaultdict(int)
    for pickup, dropoff, quantity in reservations:
        changes[max(start, pickup)] += quantity
        changes[min(end, dropoff) if end is not None else dropoff] -= quantity

    reserved = peak = 0
    for day in sorted(changes):
        reserved += changes[day]
        peak = max(peak, reserved)
    return peak


def available_stock(equipment, pickup_date, return_date):
    validate_period(pickup_date, return_date)
    reservations = _scheduled_reservations(pickup_date, return_date).filter(
        equipment=equipment
    )
    peak = _peak_reserved(
        reservations.values_list("pickup_date", "return_date", "quantity"),
        pickup_date,
        return_date,
    )
    return max(0, equipment.total_stock - peak)


def catalog_availability(equipment, pickup_date, return_date):
    validate_period(pickup_date, return_date)
    reservations = _scheduled_reservations(pickup_date, return_date).filter(
        equipment_id__in=[item.pk for item in equipment],
    )
    windows = defaultdict(list)
    for equipment_id, pickup, dropoff, quantity in reservations.values_list(
        "equipment_id",
        "pickup_date",
        "return_date",
        "quantity",
    ):
        windows[equipment_id].append((pickup, dropoff, quantity))
    return {
        item.pk: max(
            0,
            item.total_stock
            - _peak_reserved(windows[item.pk], pickup_date, return_date),
        )
        for item in equipment
    }


@transaction.atomic
def book_rental(customer, equipment_id, pickup_date, return_date, quantity):
    if not customer.is_authenticated:
        raise RentalError("Cần đăng nhập để đặt thuê.", 403)
    if type(quantity) is not int or quantity < 1:
        raise RentalError("Số lượng phải là số nguyên dương.")

    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    if not equipment.is_active:
        raise RentalError("Thiết bị đã ngừng nhận đơn thuê mới.", 409)
    if quantity > available_stock(equipment, pickup_date, return_date):
        raise RentalError("Không đủ thiết bị cho kỳ thuê đã chọn.", 409)

    return Rental.objects.create(
        customer=customer,
        equipment=equipment,
        pickup_date=pickup_date,
        return_date=return_date,
        quantity=quantity,
        daily_rate_vnd=equipment.daily_rate_vnd,
        total_vnd=(return_date - pickup_date).days
        * quantity
        * equipment.daily_rate_vnd,
    )


def customer_rentals(customer):
    return Rental.objects.filter(customer=customer).select_related("equipment")


def _lock_rental(rentals, rental_id):
    equipment_id = rentals.values_list("equipment_id", flat=True).get(pk=rental_id)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    rental = rentals.select_related(None).select_for_update().get(pk=rental_id)
    return rental, equipment


@transaction.atomic
def cancel_rental(customer, rental_id):
    rental, _ = _lock_rental(customer_rentals(customer), rental_id)
    if (
        rental.status != Rental.Status.CONFIRMED
        or timezone.localdate() >= rental.pickup_date
    ):
        raise RentalError("Chỉ hủy được đơn đã đặt trước ngày nhận.", 409)
    rental.status = Rental.Status.CANCELLED
    rental.save(update_fields=["status"])
    return rental


def checked_out_quantity(equipment):
    return Rental.objects.filter(
        equipment=equipment, status=Rental.Status.PICKED_UP
    ).aggregate(quantity=Sum("quantity", default=0))["quantity"]


@transaction.atomic
def pick_up_rental(staff, rental_id):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được ghi nhận bàn giao.", 403)
    rental, equipment = _lock_rental(Rental.objects.all(), rental_id)
    now = timezone.now()
    if (
        rental.status != Rental.Status.CONFIRMED
        or not rental.pickup_date <= timezone.localdate(now) < rental.return_date
    ):
        raise RentalError(
            "Chỉ bàn giao đơn đã đặt từ ngày nhận đến trước ngày trả.", 409
        )
    if rental.quantity > equipment.total_stock - checked_out_quantity(equipment):
        raise RentalError(
            "Không đủ thiết bị thực tế để bàn giao. Kiểm tra các đơn chưa trả.", 409
        )
    rental.status = Rental.Status.PICKED_UP
    rental.picked_up_at = now
    rental.save(update_fields=["status", "picked_up_at"])
    return rental


@transaction.atomic
def mark_no_show(staff, rental_id):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được xử lý khách không đến nhận.", 403)
    rental, _ = _lock_rental(Rental.objects.all(), rental_id)
    if (
        rental.status != Rental.Status.CONFIRMED
        or timezone.localdate() <= rental.pickup_date
    ):
        raise RentalError("Chỉ xử lý đơn chưa bàn giao sau ngày nhận.", 409)
    rental.status = Rental.Status.CANCELLED
    rental.cancellation_reason = Rental.CancellationReason.NO_SHOW
    rental.save(update_fields=["status", "cancellation_reason"])
    return rental


@transaction.atomic
def return_rental(staff, rental_id):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được ghi nhận trả.", 403)
    rental, _ = _lock_rental(Rental.objects.all(), rental_id)
    now = timezone.now()
    if rental.status != Rental.Status.PICKED_UP or now < rental.picked_up_at:
        raise RentalError("Chỉ ghi nhận trả đơn đã bàn giao.", 409)
    rental.status = Rental.Status.RETURNED
    rental.returned_at = now
    rental.save(update_fields=["status", "returned_at"])
    return rental


@transaction.atomic
def create_equipment(
    staff,
    code,
    name,
    daily_rate_vnd,
    total_stock,
    *,
    kind=Equipment.Kind.CAMERA,
    specifications="",
    is_active=True,
):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được thêm thiết bị.", 403)
    equipment, created = Equipment.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "daily_rate_vnd": daily_rate_vnd,
            "total_stock": total_stock,
            "kind": kind,
            "specifications": specifications,
            "is_active": is_active,
        },
    )
    if not created:
        raise RentalError("Mã thiết bị đã tồn tại.", 409)
    return equipment


@transaction.atomic
def update_equipment(
    staff,
    equipment_id,
    name,
    daily_rate_vnd,
    total_stock,
    *,
    kind=None,
    specifications=None,
    is_active=None,
):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được sửa thiết bị.", 403)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    today = timezone.localdate()
    reservations = _scheduled_reservations(today).filter(equipment=equipment)
    peak_reserved = _peak_reserved(
        reservations.values_list("pickup_date", "return_date", "quantity"), today
    )
    if total_stock < max(peak_reserved, checked_out_quantity(equipment)):
        raise RentalError(
            "Tổng tồn mới thấp hơn số lượng đã giữ hoặc đang được thuê.", 409
        )
    equipment.name = name
    equipment.daily_rate_vnd = daily_rate_vnd
    equipment.total_stock = total_stock
    changes = {"kind": kind, "specifications": specifications, "is_active": is_active}
    updated_fields = ["name", "daily_rate_vnd", "total_stock"]
    for field, value in changes.items():
        if value is not None:
            setattr(equipment, field, value)
            updated_fields.append(field)
    equipment.save(update_fields=updated_fields)
    return equipment
