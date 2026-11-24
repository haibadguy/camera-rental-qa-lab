from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from .custody import rental_handovers
from .errors import RentalError
from .finance import period_movements, receivables
from .inventory import (
    checked_out_assets,
    equipment_with_physical_stock,
    rental_asset_history,
)
from .models import AssetHandover, AssetReservation, AssetUnit, MaintenanceCase, Rental
from .roles import can_manage_reporting


def _require_manager(actor):
    if not can_manage_reporting(actor):
        raise RentalError("Cần quyền quản lý để xem báo cáo.", 403)


def _period(first, last):
    if (
        type(first) is not date
        or type(last) is not date
        or first > last
        or last == date.max
    ):
        raise RentalError("Chọn kỳ báo cáo hợp lệ.")
    zone = timezone.get_default_timezone()
    return datetime.combine(first, time.min, zone), datetime.combine(
        last + timedelta(days=1), time.min, zone
    )


def _intervals(start, end, ranges):
    """Clip ranges to the measured period and merge overlaps for one unit."""
    result = []
    for lower, upper in sorted(
        (max(start, lower), min(end, upper)) for lower, upper in ranges
    ):
        if lower >= upper:
            continue
        if result and lower <= result[-1][1]:
            result[-1] = (result[-1][0], max(upper, result[-1][1]))
        else:
            result.append((lower, upper))
    return result


def _seconds(intervals):
    return sum((end - start).total_seconds() for start, end in intervals)


def _utilization(start, end, now, *, legacy_stock):
    end = min(now, end)
    borrowed = defaultdict(list)
    for asset_id, pickup, receipt, lost, handover_id, rental_id in (
        AssetHandover.objects.filter(
            picked_up_at__lt=end, asset__equipment__tracks_assets=True
        )
        .filter(
            Q(returned_at__gte=start)
            | Q(lost_at__gte=start)
            | Q(returned_at__isnull=True, lost_at__isnull=True)
        )
        .values_list(
            "asset_id",
            "picked_up_at",
            "returned_at",
            "lost_at",
            "pk",
            "reservation__line__rental_id",
        )
        .iterator()
    ):
        borrowed[asset_id].append(
            (pickup, receipt or lost or now, handover_id, rental_id)
        )

    unknown = defaultdict(list)
    legacy = AssetReservation.objects.filter(
        released_at__isnull=True,
        handover__isnull=True,
        line__rental__status__in=[
            Rental.Status.PICKED_UP,
            Rental.Status.RETURNED,
            Rental.Status.CLOSED,
        ],
    ).filter(
        Q(line__rental__picked_up_at__lt=end)
        | Q(line__rental__picked_up_at__isnull=True),
        Q(line__rental__returned_at__gte=start)
        | Q(line__rental__returned_at__isnull=True),
    )
    for asset_id, pickup, receipt, closed in legacy.values_list(
        "asset_id",
        "line__rental__picked_up_at",
        "line__rental__returned_at",
        "line__rental__closed_at",
    ).iterator():
        unknown[asset_id].append((pickup or start, receipt or closed or now))

    retirement = dict(
        MaintenanceCase.objects.filter(resolution=MaintenanceCase.Resolution.RETIRED)
        .values("asset_id")
        .annotate(first=Min("resolved_at"))
        .values_list("asset_id", "first")
    )
    rows = []
    incomplete = legacy_stock
    for asset in (
        AssetUnit.objects.filter(equipment__tracks_assets=True)
        .select_related("equipment")
        .iterator()
    ):
        available_from = asset.reporting_since
        retired_at = retirement.get(asset.pk)
        if available_from is None or (
            asset.status == AssetUnit.Status.RETIRED and retired_at is None
        ):
            incomplete = True
            continue
        if retired_at and retired_at <= start:
            continue
        if available_from > start:
            incomplete = True
        lower, upper = max(start, available_from), min(end, retired_at or end)
        if upper <= lower:
            continue
        gaps = _intervals(lower, upper, unknown[asset.pk])
        sources = [
            (pickup, receipt, handover_id, rental_id)
            for pickup, receipt, handover_id, rental_id in borrowed[asset.pk]
            if pickup < upper and receipt > lower
        ]
        used = _intervals(
            lower, upper, [(pickup, receipt) for pickup, receipt, _, _ in sources]
        )
        gap_seconds = _seconds(gaps)
        if gap_seconds:
            incomplete = True
        available_seconds = (upper - lower).total_seconds() - gap_seconds
        used_seconds = _seconds(used) - sum(
            _seconds(_intervals(a, b, gaps)) for a, b in used
        )
        if available_seconds:
            rows.append(
                {
                    "asset": asset,
                    "available_hours": available_seconds / 3600,
                    "used_hours": used_seconds / 3600,
                    "sources": [
                        (rental_id, handover_id)
                        for _, _, handover_id, rental_id in sources
                    ],
                    "from_at": lower,
                    "until_at": upper,
                }
            )
    available = sum(row["available_hours"] for row in rows)
    used = sum(row["used_hours"] for row in rows)
    return {
        "rows": rows,
        "available_hours": available,
        "used_hours": used,
        "percent": 100 * used / available if available else None,
        "incomplete": incomplete,
    }


def rental_report(actor, first, last):
    _require_manager(actor)
    start, end = _period(first, last)
    now = timezone.now()
    orders = Rental.objects.filter(
        pickup_date__gte=first, pickup_date__lte=last
    ).select_related("customer")
    entries = period_movements(start, end)
    stock = list(equipment_with_physical_stock())
    counts = orders.aggregate(
        active=Count(
            "pk",
            filter=Q(status__in=[Rental.Status.CONFIRMED, Rental.Status.PICKED_UP]),
        ),
        completed=Count(
            "pk", filter=Q(status__in=[Rental.Status.RETURNED, Rental.Status.CLOSED])
        ),
        cancelled=Count("pk", filter=Q(status=Rental.Status.CANCELLED)),
        no_show=Count(
            "pk", filter=Q(cancellation_reason=Rental.CancellationReason.NO_SHOW)
        ),
    )
    period_totals = entries.aggregate(
        rent_net_total=Sum("rent_net_vnd", default=0),
        deposit_received_total=Sum("deposit_received_vnd", default=0),
        deposit_refunded_total=Sum("deposit_refunded_vnd", default=0),
    )
    money = {
        "rent_net_vnd": period_totals["rent_net_total"],
        "deposit_received_vnd": period_totals["deposit_received_total"],
        "deposit_refunded_vnd": period_totals["deposit_refunded_total"],
        **receivables(orders),
    }
    return {
        "first": first,
        "last": last,
        "generated_at": now,
        "counts": counts,
        "money": money,
        "orders": orders,
        "entries": entries,
        "stock": stock,
        "outstanding": sum(item.outstanding for item in stock),
        "out_assets": checked_out_assets()
        .select_related("asset__equipment", "line")
        .order_by("asset__code"),
        "usage": _utilization(
            start, end, now, legacy_stock=any(not item.tracks_assets for item in stock)
        ),
    }


def rental_audit(actor, rental_id):
    _require_manager(actor)
    rental = Rental.objects.select_related("customer").get(pk=rental_id)
    return {
        "rental": rental,
        "assignments": rental_asset_history(rental),
        "handovers": rental_handovers(rental),
        "changes": rental.changes.select_related("reviewed_by"),
        "incidents": MaintenanceCase.objects.filter(
            handover__reservation__line__rental=rental
        ).select_related("asset", "reported_by", "resolved_by"),
        "entries": rental.finance_entries.select_related("recorded_by"),
        "charges": rental.finance_charges.select_related(
            "reviewed_by", "handover__asset", "incident"
        ).filter(reviewed_at__isnull=False),
    }
