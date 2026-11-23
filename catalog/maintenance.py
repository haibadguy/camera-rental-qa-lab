from django.db import transaction
from django.utils import timezone

from .custody import lock_handover_context, sync_rental_return
from .errors import RentalError
from .inventory import checked_out_assets, free_assets, validate_period
from .models import (
    AssetHandover,
    AssetReservation,
    AssetUnit,
    Equipment,
    MaintenanceCase,
)
from .roles import can_manage, can_operate


def _require_operator(staff):
    if not can_operate(staff):
        raise RentalError("Chỉ nhân viên có quyền vận hành được xử lý bảo trì.", 403)


def _required_notes(value):
    notes = value.strip() if isinstance(value, str) else ""
    if not notes or len(notes) > 2000:
        raise RentalError("Nhập ghi chú từ 1 đến 2.000 ký tự.")
    return notes


def _lock_asset(asset_id):
    equipment_id = AssetUnit.objects.values_list("equipment_id", flat=True).get(
        pk=asset_id
    )
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    if not equipment.tracks_assets:
        raise RentalError("Mẫu này chưa chuyển sang quản lý theo mã kho.", 409)
    return AssetUnit.objects.select_for_update().get(pk=asset_id)


def _lock_incident_handover(staff, asset_id, handover_id):
    rental_id = AssetHandover.objects.values_list(
        "reservation__line__rental_id", flat=True
    ).get(pk=handover_id, asset_id=asset_id)
    return lock_handover_context(staff, rental_id, handover_id)


def _lock_case(staff, case_id):
    asset_id, handover_id = MaintenanceCase.objects.values_list(
        "asset_id", "handover_id"
    ).get(pk=case_id)
    if handover_id is None:
        rental, handover = (None, None)
        asset = _lock_asset(asset_id)
    else:
        rental, handover = _lock_incident_handover(staff, asset_id, handover_id)
        asset = AssetUnit.objects.select_for_update().get(pk=asset_id)
    case = MaintenanceCase.objects.select_for_update().get(pk=case_id)
    return case, asset, rental, handover


def _is_out(asset):
    return checked_out_assets().filter(asset_id=asset.pk).exists()


def apply_inspection_result(staff, handover):
    if AssetUnit.objects.filter(
        pk=handover.asset_id, status=AssetUnit.Status.RETIRED
    ).exists():
        return
    unresolved = MaintenanceCase.objects.filter(
        asset_id=handover.asset_id,
        state__in=(MaintenanceCase.State.OPEN, MaintenanceCase.State.IN_REPAIR),
    )
    if unresolved.exists():
        return
    if handover.inspection_result == AssetHandover.Inspection.READY:
        AssetUnit.objects.filter(
            pk=handover.asset_id, status=AssetUnit.Status.INSPECTION
        ).update(status=AssetUnit.Status.READY)
    else:
        report_incident(
            staff,
            handover.asset_id,
            handover.inspection_result,
            handover.return_notes,
            handover_id=handover.pk,
        )


@transaction.atomic
def plan_maintenance(staff, asset_id, pickup_date, return_date, notes):
    _require_operator(staff)
    validate_period(pickup_date, return_date)
    notes = _required_notes(notes)
    asset = _lock_asset(asset_id)
    if (
        not free_assets([asset.equipment_id], pickup_date, return_date)
        .filter(pk=asset.pk)
        .exists()
    ):
        raise RentalError("Mã kho không khả dụng suốt kỳ bảo trì.", 409)
    case = MaintenanceCase.objects.create(
        asset=asset,
        kind=MaintenanceCase.Kind.PLANNED,
        state=MaintenanceCase.State.PLANNED,
        notes=notes,
        reported_by=staff,
    )
    AssetReservation.objects.create(
        asset=asset,
        maintenance=case,
        period=(pickup_date, return_date),
        changed_by=staff,
    )
    return case


@transaction.atomic
def report_incident(staff, asset_id, kind, notes, *, handover_id=None):
    _require_operator(staff)
    if kind not in (
        MaintenanceCase.Kind.DAMAGE,
        MaintenanceCase.Kind.MISSING_ACCESSORY,
        MaintenanceCase.Kind.LOST,
    ):
        raise RentalError("Loại sự cố không hợp lệ.")
    notes = _required_notes(notes)
    if handover_id is None and kind == MaintenanceCase.Kind.LOST:
        handover_id = (
            AssetHandover.objects.filter(
                asset_id=asset_id,
                picked_up_at__isnull=False,
                returned_at__isnull=True,
                lost_at__isnull=True,
            )
            .values_list("id", flat=True)
            .first()
        )
    handover = None
    if handover_id is None:
        asset = _lock_asset(asset_id)
    else:
        _, handover = _lock_incident_handover(staff, asset_id, handover_id)
        asset = AssetUnit.objects.select_for_update().get(pk=asset_id)
    if asset.status == AssetUnit.Status.RETIRED:
        raise RentalError("Thiết bị đã ngừng sử dụng.", 409)
    if handover is not None:
        if handover.picked_up_at is None or handover.lost_at is not None:
            raise RentalError("Lượt giao nhận này không thể ghi sự cố.", 409)
        if kind == MaintenanceCase.Kind.LOST and handover.returned_at is not None:
            raise RentalError("Lượt giao nhận này đã ghi nhận thiết bị về kho.", 409)
        if kind != MaintenanceCase.Kind.LOST and handover.returned_at is None:
            raise RentalError(
                "Ghi nhận thiết bị đã về trước khi kết luận kiểm tra.", 409
            )
    elif _is_out(asset):
        raise RentalError(
            "Thiết bị đang ở ngoài kho. Ghi sự cố từ lượt giao nhận.", 409
        )

    open_incident = (
        asset.maintenance_cases.exclude(kind=MaintenanceCase.Kind.PLANNED)
        .exclude(state=MaintenanceCase.State.RESOLVED)
        .first()
    )
    if open_incident is not None:
        # A recovered unit may fail inspection. Keep the original loss report
        # and the separate inspection record linked to the same handover.
        if (
            handover is not None
            and open_incident.handover_id == handover.pk
            and open_incident.kind == MaintenanceCase.Kind.LOST
            and handover.inspected_at is not None
            and handover.inspection_result == kind
        ):
            return open_incident
        raise RentalError("Thiết bị đã có sự cố đang xử lý.", 409)
    case = MaintenanceCase.objects.create(
        asset=asset, handover=handover, kind=kind, notes=notes, reported_by=staff
    )
    asset.status = AssetUnit.Status.QUARANTINED
    asset.save(update_fields=["status"])
    return case


@transaction.atomic
def start_repair(staff, case_id, notes):
    _require_operator(staff)
    notes = _required_notes(notes)
    case, asset, _, handover = _lock_case(staff, case_id)
    if case.state not in (MaintenanceCase.State.PLANNED, MaintenanceCase.State.OPEN):
        raise RentalError("Hồ sơ này không thể bắt đầu sửa.", 409)
    if asset.status == AssetUnit.Status.RETIRED or _is_out(asset):
        raise RentalError("Chỉ sửa thiết bị thực tế đang ở kho.", 409)
    if case.kind == MaintenanceCase.Kind.LOST and (
        handover is None or handover.returned_at is None
    ):
        raise RentalError("Cần tìm thấy và nhận lại thiết bị trước khi sửa.", 409)
    if case.state == MaintenanceCase.State.PLANNED:
        period = case.reservation.period
        if not period.lower <= timezone.localdate() < period.upper:
            raise RentalError("Chỉ bắt đầu trong kỳ bảo trì đã lên lịch.", 409)

    case.state = MaintenanceCase.State.IN_REPAIR
    case.repair_notes = notes
    case.repaired_at = timezone.now()
    case.repaired_by = staff
    case.save(update_fields=["state", "repair_notes", "repaired_at", "repaired_by"])
    asset.status = AssetUnit.Status.QUARANTINED
    asset.save(update_fields=["status"])
    return case


@transaction.atomic
def resolve_case(manager, case_id, resolution, notes):
    if not can_manage(manager):
        raise RentalError("Chỉ quản lý được đóng hồ sơ bảo trì.", 403)
    if resolution not in MaintenanceCase.Resolution.values:
        raise RentalError("Kết quả xử lý không hợp lệ.")
    notes = _required_notes(notes)
    case, asset, rental, handover = _lock_case(manager, case_id)
    if case.state == MaintenanceCase.State.RESOLVED:
        raise RentalError("Hồ sơ đã được đóng.", 409)
    retiring = resolution == MaintenanceCase.Resolution.RETIRED
    closing_loss = (
        case.kind == MaintenanceCase.Kind.LOST
        and handover is not None
        and handover.returned_at is None
        and handover.lost_at is None
    )
    if _is_out(asset) and not (retiring and closing_loss):
        raise RentalError("Thiết bị vẫn đang ở ngoài kho.", 409)
    if not retiring:
        if asset.status == AssetUnit.Status.RETIRED:
            raise RentalError(
                "Thiết bị đã ngừng sử dụng, không thể mở lại từ hồ sơ này.", 409
            )
        if AssetHandover.objects.filter(
            asset=asset, returned_at__isnull=False, inspected_at__isnull=True
        ).exists():
            raise RentalError("Thiết bị vẫn còn lượt trả đang chờ kiểm tra.", 409)
        if (
            case.kind == MaintenanceCase.Kind.LOST
            and handover is not None
            and (
                handover.returned_at is None
                or (
                    handover.inspection_result != AssetHandover.Inspection.READY
                    and case.state != MaintenanceCase.State.IN_REPAIR
                )
            )
        ):
            raise RentalError("Thiết bị mất cần được nhận lại và kiểm tra đạt.", 409)
    now = timezone.now()
    if retiring and closing_loss:
        handover.lost_at = now
        handover.lost_by = manager
        handover.save(update_fields=["lost_at", "lost_by"])
        sync_rental_return(rental)

    planned_only = case.state == MaintenanceCase.State.PLANNED
    case.state = MaintenanceCase.State.RESOLVED
    case.resolution = resolution
    case.resolution_notes = notes
    case.resolved_by = manager
    case.resolved_at = now
    case.save(
        update_fields=[
            "state",
            "resolution",
            "resolution_notes",
            "resolved_by",
            "resolved_at",
        ]
    )
    AssetReservation.objects.filter(
        maintenance_id=case.pk, released_at__isnull=True
    ).update(released_at=now)
    if retiring:
        asset.status = AssetUnit.Status.RETIRED
        asset.save(update_fields=["status"])
    elif (
        not planned_only
        and not asset.maintenance_cases.filter(
            state__in=(MaintenanceCase.State.OPEN, MaintenanceCase.State.IN_REPAIR)
        ).exists()
    ):
        asset.status = AssetUnit.Status.READY
        asset.save(update_fields=["status"])
    return case


def maintenance_cases(staff):
    _require_operator(staff)
    return MaintenanceCase.objects.select_related(
        "asset__equipment",
        "handover__reservation__line__rental",
        "reported_by",
        "repaired_by",
        "resolved_by",
        "reservation",
    )
