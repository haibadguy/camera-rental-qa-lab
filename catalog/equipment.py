from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .errors import RentalError
from .inventory import minimum_stock, unassigned_legacy_rentals
from .models import AssetUnit, Equipment


def catalog_items(*, search="", kind="", brand=""):
    equipment = Equipment.objects.filter(is_active=True)
    if search:
        equipment = equipment.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )
    if kind:
        equipment = equipment.filter(kind=kind)
    if brand:
        equipment = equipment.filter(brand__iexact=brand.strip())
    return equipment


def catalog_brands():
    return (
        catalog_items()
        .exclude(brand="")
        .order_by("brand")
        .values_list("brand", flat=True)
        .distinct()
    )


@transaction.atomic
def create_equipment(
    staff,
    code,
    name,
    daily_rate_vnd,
    total_stock,
    *,
    kind=Equipment.Kind.CAMERA,
    brand="",
    specifications="",
    accessory_checklist="",
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
            "brand": _brand(brand),
            "specifications": specifications,
            "accessory_checklist": accessory_checklist,
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
    brand=None,
    specifications=None,
    accessory_checklist=None,
    is_active=None,
):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được sửa thiết bị.", 403)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    if equipment.tracks_assets and total_stock != equipment.total_stock:
        raise RentalError("Tổng tồn được cập nhật từ sổ thiết bị vật lý.", 409)
    if not equipment.tracks_assets and total_stock < minimum_stock(
        equipment, timezone.localdate()
    ):
        raise RentalError(
            "Tổng tồn mới thấp hơn số lượng đã giữ hoặc đang được thuê.", 409
        )
    equipment.name = name
    equipment.daily_rate_vnd = daily_rate_vnd
    equipment.total_stock = total_stock
    changes = {
        "kind": kind,
        "brand": _brand(brand) if brand is not None else None,
        "specifications": specifications,
        "accessory_checklist": accessory_checklist,
        "is_active": is_active,
    }
    updated_fields = ["name", "daily_rate_vnd", "total_stock"]
    for field, value in changes.items():
        if value is not None:
            setattr(equipment, field, value)
            updated_fields.append(field)
    equipment.save(update_fields=updated_fields)
    return equipment


def _brand(value):
    if (
        not isinstance(value, str)
        or len(value.strip()) > Equipment._meta.get_field("brand").max_length
    ):
        raise RentalError("Thương hiệu không hợp lệ.")
    return value.strip()


@transaction.atomic
def register_asset(staff, equipment_id, code, serial=""):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được đăng ký thiết bị vật lý.", 403)
    code, serial = code.strip(), serial.strip()
    if not code or len(code) > 48 or len(serial) > 100:
        raise RentalError("Mã kho hoặc serial không hợp lệ.")
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    asset, created = AssetUnit.objects.get_or_create(
        code=code,
        defaults={
            "equipment": equipment,
            "serial": serial,
            "reporting_since": timezone.now() if equipment.tracks_assets else None,
        },
    )
    if not created:
        raise RentalError("Mã kho đã được sử dụng.", 409)
    if equipment.tracks_assets:
        equipment.total_stock = equipment.assets.count()
        equipment.save(update_fields=["total_stock"])
    return asset


@transaction.atomic
def enable_asset_tracking(staff, equipment_id):
    if not staff.is_staff:
        raise RentalError("Chỉ nhân viên được chuyển sang giữ theo mã kho.", 403)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
    if equipment.tracks_assets:
        return equipment
    if unassigned_legacy_rentals(equipment).exists():
        raise RentalError("Còn đơn v1 chưa đối soát. Xem danh sách bên dưới.", 409)
    if equipment.assets.count() != equipment.total_stock:
        raise RentalError("Số thiết bị đã đăng ký phải khớp tổng tồn v1.", 409)
    equipment.tracks_assets = True
    equipment.save(update_fields=["tracks_assets"])
    equipment.assets.filter(reporting_since__isnull=True).update(
        reporting_since=timezone.now()
    )
    return equipment
