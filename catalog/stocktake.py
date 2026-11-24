from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .errors import RentalError
from .inventory import checked_out_assets
from .models import AssetHandover, Equipment, Stocktake, StocktakeLine
from .roles import can_count_stock, can_manage_reporting

Condition = StocktakeLine.Condition
OBSERVATIONS = tuple(
    (value, label)
    for value, label in Condition.choices
    if value != Condition.UNEXPECTED
)
MOVEMENT_FIELDS = ("picked_up_at", "returned_at", "inspected_at", "lost_at")


def _require_counter(actor):
    if not can_count_stock(actor):
        raise RentalError("Cần quyền kiểm kê thiết bị.", 403)


def _require_manager(actor):
    if not can_manage_reporting(actor):
        raise RentalError("Cần quyền quản lý để chốt kiểm kê.", 403)


def _notes(value, *, required=False):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or (required and not value.strip())
    ):
        raise RentalError(
            "Ghi lý do từ 1 đến 2.000 ký tự."
            if required
            else "Ghi chú tối đa 2.000 ký tự."
        )
    return value.strip()


def stocktake_history(actor):
    _require_counter(actor)
    return Stocktake.objects.select_related("equipment", "opened_by", "closed_by")


def stocktake_detail(actor, stocktake_id):
    stocktake = stocktake_history(actor).get(pk=stocktake_id)
    end = stocktake.closed_at or timezone.now()
    period = Q(**{f"{MOVEMENT_FIELDS[0]}__range": (stocktake.opened_at, end)})
    for field in MOVEMENT_FIELDS[1:]:
        period |= Q(**{f"{field}__range": (stocktake.opened_at, end)})
    movements = (
        AssetHandover.objects.filter(period, asset__equipment=stocktake.equipment)
        .select_related("asset", "reservation__line")
        .order_by("pk")
    )
    return {
        "stocktake": stocktake,
        "period_end": end,
        "lines": stocktake.lines.select_related(
            "counted_by", "resolved_by", "movement__reservation__line"
        ),
        "movements": movements,
    }


@transaction.atomic
def open_stocktake(actor, equipment_id):
    _require_counter(actor)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    if not equipment.tracks_assets:
        raise RentalError("Mẫu này cần quản lý theo mã kho trước khi kiểm kê.", 409)
    if equipment.stocktakes.filter(closed_at__isnull=True).exists():
        raise RentalError("Mẫu này đã có phiên kiểm kê đang mở.", 409)
    stocktake = Stocktake.objects.create(equipment=equipment, opened_by=actor)
    out = set(
        checked_out_assets()
        .filter(asset__equipment=equipment)
        .values_list("asset_id", flat=True)
    )
    StocktakeLine.objects.bulk_create(
        [
            StocktakeLine(
                stocktake=stocktake,
                asset=asset,
                code=asset.code,
                expected=Condition.OUT if asset.pk in out else asset.status,
            )
            for asset in equipment.assets.all()
        ]
    )
    return stocktake


def _open_session(stocktake_id):
    stocktake = Stocktake.objects.select_for_update().get(pk=stocktake_id)
    if stocktake.closed_at:
        raise RentalError("Phiên kiểm kê đã chốt.", 409)
    return stocktake


def _movement(stocktake, code, movement_id, now):
    if movement_id is None:
        return None
    handover = AssetHandover.objects.get(
        pk=movement_id,
        asset__code=code,
        asset__equipment_id=stocktake.equipment_id,
    )
    dates = [getattr(handover, field) for field in MOVEMENT_FIELDS]
    if not any(date and stocktake.opened_at <= date <= now for date in dates):
        raise RentalError(
            "Lượt giao nhận không phát sinh trong phiên kiểm kê này.", 409
        )
    return handover


@transaction.atomic
def record_stocktake_line(
    actor, stocktake_id, *, code, observed, notes="", movement_id=None
):
    _require_counter(actor)
    if not isinstance(code, str) or not code.strip() or len(code.strip()) > 48:
        raise RentalError("Nhập mã kho hợp lệ.")
    if observed not in dict(OBSERVATIONS):
        raise RentalError("Chọn tình trạng đối chiếu.")
    notes = _notes(notes)
    code = code.strip()
    stocktake = _open_session(stocktake_id)
    now = timezone.now()
    movement = _movement(stocktake, code, movement_id, now)
    line = stocktake.lines.filter(code=code).first()
    if line is None:
        line = StocktakeLine(
            stocktake=stocktake, code=code, expected=Condition.UNEXPECTED
        )
    if line.resolved_at:
        raise RentalError("Kết quả này đã được quản lý xử lý.", 409)
    line.observed = observed
    line.notes = notes
    line.movement = movement
    line.counted_at = now
    line.counted_by = actor
    line.save()
    return line


@transaction.atomic
def resolve_stocktake_line(actor, stocktake_id, line_id, *, notes):
    _require_manager(actor)
    notes = _notes(notes, required=True)
    stocktake = _open_session(stocktake_id)
    line = stocktake.lines.get(pk=line_id)
    if not line.observed or line.expected == line.observed or line.resolved_at:
        raise RentalError("Dòng này không có chênh lệch đang chờ xử lý.", 409)
    line.resolved_at = timezone.now()
    line.resolved_by = actor
    line.resolution_note = notes
    line.save(update_fields=["resolved_at", "resolved_by", "resolution_note"])
    return line


@transaction.atomic
def close_stocktake(actor, stocktake_id):
    _require_manager(actor)
    stocktake = _open_session(stocktake_id)
    if stocktake.lines.filter(observed="").exists():
        raise RentalError("Cần đối chiếu đủ các mã kho trước khi chốt.", 409)
    if (
        stocktake.lines.filter(resolved_at__isnull=True)
        .exclude(observed=F("expected"))
        .exists()
    ):
        raise RentalError("Còn chênh lệch chưa được xử lý.", 409)
    stocktake.closed_at = timezone.now()
    stocktake.closed_by = actor
    stocktake.save(update_fields=["closed_at", "closed_by"])
    return stocktake
