from collections import defaultdict

from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .errors import RentalError
from .models import AssetReservation, AssetUnit, Equipment, Rental

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
    return catalog_availability([equipment], pickup_date, return_date)[equipment.pk]


def catalog_availability(equipment, pickup_date, return_date):
    validate_period(pickup_date, return_date)
    equipment = list(equipment)
    reservations = _scheduled_reservations(pickup_date, return_date).filter(
        equipment_id__in=[item.pk for item in equipment if not item.tracks_assets],
    )
    windows = defaultdict(list)
    for equipment_id, pickup, dropoff, quantity in reservations.values_list(
        "equipment_id",
        "pickup_date",
        "return_date",
        "quantity",
    ):
        windows[equipment_id].append((pickup, dropoff, quantity))
    counts = defaultdict(int)
    tracked_ids = [item.pk for item in equipment if item.tracks_assets]
    if tracked_ids:
        available = free_assets(tracked_ids, pickup_date, return_date)
        for equipment_id in available.values_list("equipment_id", flat=True):
            counts[equipment_id] += 1
    return {
        item.pk: counts[item.pk]
        if item.tracks_assets
        else _remaining_stock(item, windows[item.pk], pickup_date, return_date)
        for item in equipment
    }


def _checked_out_filter(status_field):
    return Q(**{status_field: Rental.Status.PICKED_UP})


def checked_out_quantity(equipment):
    if equipment.tracks_assets:
        return checked_out_assets().filter(asset__equipment=equipment).count()
    return Rental.objects.filter(
        _checked_out_filter("status"), equipment=equipment
    ).aggregate(quantity=Sum("quantity", default=0))["quantity"]


def equipment_with_physical_stock():
    asset_counts = (
        checked_out_assets()
        .filter(asset__equipment_id=OuterRef("pk"))
        .order_by()
        .values("asset__equipment_id")
        .annotate(count=Count("pk"))
        .values("count")
    )
    legacy_counts = (
        Rental.objects.filter(
            _checked_out_filter("status"), equipment_id=OuterRef("pk")
        )
        .order_by()
        .values("equipment_id")
        .annotate(count=Sum("quantity"))
        .values("count")
    )
    ready_counts = (
        AssetUnit.objects.filter(
            equipment_id=OuterRef("pk"), status=AssetUnit.Status.READY
        )
        .exclude(pk__in=checked_out_assets().values("asset_id"))
        .order_by()
        .values("equipment_id")
        .annotate(count=Count("pk"))
        .values("count")
    )
    return (
        Equipment.objects.annotate(
            outstanding=Coalesce(
                Case(
                    When(tracks_assets=True, then=Subquery(asset_counts)),
                    default=Subquery(legacy_counts),
                    output_field=IntegerField(),
                ),
                0,
            ),
        )
        .annotate(
            available_now=Case(
                When(tracks_assets=True, then=Coalesce(Subquery(ready_counts), 0)),
                default=F("total_stock") - F("outstanding"),
                output_field=IntegerField(),
            )
        )
        .order_by("code")
    )


def minimum_stock(equipment, today):
    reservations = _scheduled_reservations(today).filter(equipment=equipment)
    peak_reserved = _peak_reserved(
        reservations.values_list("pickup_date", "return_date", "quantity"), today
    )
    return max(peak_reserved, checked_out_quantity(equipment))


def checked_out_assets():
    return AssetReservation.objects.filter(
        released_at__isnull=True, line__rental__status=Rental.Status.PICKED_UP
    ).filter(
        Q(handover__isnull=True)
        | Q(
            handover__picked_up_at__isnull=False,
            handover__returned_at__isnull=True,
            handover__lost_at__isnull=True,
        )
    )


def free_assets(equipment_ids, pickup_date, return_date, *, exclude_rental_id=None):
    conflicts = AssetReservation.objects.filter(
        released_at__isnull=True, period__overlap=(pickup_date, return_date)
    )
    overdue = checked_out_assets().filter(
        line__rental__return_date__lte=timezone.localdate()
    )
    if exclude_rental_id is not None:
        conflicts = conflicts.exclude(line__rental_id=exclude_rental_id)
        overdue = overdue.exclude(line__rental_id=exclude_rental_id)
    return (
        AssetUnit.objects.filter(
            equipment_id__in=equipment_ids, status=AssetUnit.Status.READY
        )
        .exclude(pk__in=conflicts.values("asset_id"))
        .exclude(pk__in=overdue.values("asset_id"))
    )


def unassigned_legacy_rentals(equipment):
    return (
        Rental.objects.filter(equipment=equipment)
        .filter(
            Q(status__in=(Rental.Status.CONFIRMED, Rental.Status.PICKED_UP))
            | Q(status=Rental.Status.RETURNED, return_date__gt=timezone.localdate())
        )
        .annotate(
            assigned=Count(
                "lines__reservations",
                filter=Q(lines__reservations__released_at__isnull=True),
            )
        )
        .exclude(assigned=F("quantity"))
    )


def asset_calendar(equipment):
    return (
        AssetReservation.objects.filter(asset__equipment=equipment)
        .select_related(
            "asset", "line__rental", "changed_by", "replaces__asset", "maintenance"
        )
        .order_by("-period", "asset__code")
    )


def rental_asset_history(rental):
    return (
        AssetReservation.objects.filter(line__rental=rental)
        .select_related("asset", "changed_by", "replaces__asset")
        .order_by("line_id", "id")
    )
