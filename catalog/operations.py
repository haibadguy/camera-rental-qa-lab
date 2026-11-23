from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .custody import record_asset_inspection
from .errors import RentalError
from .inventory import checked_out_assets
from .maintenance import apply_inspection_result
from .models import AssetHandover, AssetReservation, AssetUnit, Rental
from .roles import can_operate


@transaction.atomic
def inspect_asset(staff, rental_id, handover_id, result, notes=""):
    handover = record_asset_inspection(staff, rental_id, handover_id, result, notes)
    apply_inspection_result(staff, handover)
    return handover


def ops_rentals(staff, queue="all"):
    if not can_operate(staff):
        raise RentalError("Cần quyền xem công việc vận hành.", 403)
    today = timezone.localdate()
    due_outside = checked_out_assets().filter(line__rental__return_date__lte=today)
    risk = AssetReservation.objects.filter(
        line__rental_id=OuterRef("pk"),
        released_at__isnull=True,
    ).filter(
        ~Q(asset__status=AssetUnit.Status.READY)
        | Q(asset_id__in=due_outside.values("asset_id"))
    )
    waiting = AssetHandover.objects.filter(
        reservation__line__rental_id=OuterRef("pk"),
        returned_at__isnull=False,
        inspected_at__isnull=True,
    )
    rentals = (
        Rental.objects.annotate(
            ops_at_risk=Q(status=Rental.Status.CONFIRMED) & Exists(risk),
            ops_waiting_inspection=Exists(waiting),
        )
        .select_related("customer", "equipment")
        .prefetch_related("lines__equipment")
    )
    if queue == "risk":
        return rentals.filter(status=Rental.Status.CONFIRMED, ops_at_risk=True)
    if queue == "overdue":
        return rentals.filter(status=Rental.Status.PICKED_UP, return_date__lt=today)
    return rentals.filter(
        Q(status__in=(Rental.Status.CONFIRMED, Rental.Status.PICKED_UP))
        | Q(ops_waiting_inspection=True)
    )
