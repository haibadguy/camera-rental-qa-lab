from django.db import transaction
from django.db.models import TextChoices
from django.utils import timezone

from .errors import RentalError
from .inventory import available_stock, checked_out_quantity
from .models import Equipment, Rental


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


@transaction.atomic
def book_rental(customer, equipment_id, pickup_date, return_date, quantity):
    if not customer.is_authenticated:
        raise RentalError("Cần đăng nhập để đặt thuê.", 403)
    if type(quantity) is not int or quantity < MIN_RENTAL_QUANTITY:
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
    return Rental.objects.filter(**filters.get(queue, {})).select_related(
        "equipment", "customer"
    )


def _lock_rental(rentals, rental_id):
    equipment_id = rentals.values_list("equipment_id", flat=True).get(pk=rental_id)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    rental = rentals.select_related(None).select_for_update().get(pk=rental_id)
    return rental, equipment


@transaction.atomic
def cancel_rental(customer, rental_id):
    rental, _ = _lock_rental(customer_rentals(customer), rental_id)
    if not can_cancel(rental, timezone.localdate()):
        raise RentalError("Chỉ hủy được đơn đã đặt trước ngày nhận.", 409)
    rental.status = Rental.Status.CANCELLED
    rental.save(update_fields=["status"])
    return rental


@transaction.atomic
def pick_up_rental(staff, rental_id):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được ghi nhận bàn giao.", 403)
    rental, equipment = _lock_rental(Rental.objects.all(), rental_id)
    now = timezone.now()
    if not can_pick_up(rental, timezone.localdate(now)):
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
    if not can_mark_no_show(rental, timezone.localdate()):
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
    if not can_return(rental) or now < rental.picked_up_at:
        raise RentalError("Chỉ ghi nhận trả đơn đã bàn giao.", 409)
    rental.status = Rental.Status.RETURNED
    rental.returned_at = now
    rental.save(update_fields=["status", "returned_at"])
    return rental
