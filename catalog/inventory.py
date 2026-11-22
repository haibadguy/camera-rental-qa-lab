from collections import defaultdict

from django.db.models import F, Q, Sum
from django.utils import timezone

from .errors import RentalError
from .models import Equipment, Rental


MAX_RENTAL_DAYS = 30


def validate_period(pickup_date, return_date):
    if pickup_date < timezone.localdate():
        raise RentalError("Ngày nhận phải từ hôm nay trở đi.")
    if return_date <= pickup_date:
        raise RentalError("Ngày trả phải sau ngày nhận.")
    if (return_date - pickup_date).days > MAX_RENTAL_DAYS:
        raise RentalError(f"Thời gian thuê tối đa {MAX_RENTAL_DAYS} ngày.")


def _scheduled_reservations(start, end=None):
    # Early returns release physical stock while keeping the original booking window.
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


def _remaining_stock(equipment, reservations, pickup_date, return_date):
    peak = _peak_reserved(reservations, pickup_date, return_date)
    return max(0, equipment.total_stock - peak)


def available_stock(equipment, pickup_date, return_date):
    validate_period(pickup_date, return_date)
    reservations = _scheduled_reservations(pickup_date, return_date).filter(
        equipment=equipment
    )
    return _remaining_stock(
        equipment,
        reservations.values_list("pickup_date", "return_date", "quantity"),
        pickup_date,
        return_date,
    )


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
        item.pk: _remaining_stock(item, windows[item.pk], pickup_date, return_date)
        for item in equipment
    }


def _checked_out_filter(status_field):
    return Q(**{status_field: Rental.Status.PICKED_UP})


def checked_out_quantity(equipment):
    return Rental.objects.filter(
        _checked_out_filter("status"), equipment=equipment
    ).aggregate(quantity=Sum("quantity", default=0))["quantity"]


def equipment_with_physical_stock():
    return (
        Equipment.objects.annotate(
            outstanding=Sum(
                "rental__quantity",
                filter=_checked_out_filter("rental__status"),
                default=0,
            )
        )
        .annotate(available_now=F("total_stock") - F("outstanding"))
        .order_by("code")
    )


def minimum_stock(equipment, today):
    reservations = _scheduled_reservations(today).filter(equipment=equipment)
    peak_reserved = _peak_reserved(
        reservations.values_list("pickup_date", "return_date", "quantity"), today
    )
    return max(peak_reserved, checked_out_quantity(equipment))
