from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .errors import RentalError
from .inventory import minimum_stock
from .models import Equipment


def catalog_items(*, search="", kind=""):
    equipment = Equipment.objects.filter(is_active=True)
    if search:
        equipment = equipment.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )
    if kind:
        equipment = equipment.filter(kind=kind)
    return equipment


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
    if total_stock < minimum_stock(equipment, timezone.localdate()):
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
