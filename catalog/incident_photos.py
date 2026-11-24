from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import RentalError
from .models import IncidentPhoto, MaintenanceCase
from .roles import can_operate

PHOTO_KINDS = {MaintenanceCase.Kind.DAMAGE, MaintenanceCase.Kind.MISSING_ACCESSORY}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def _storage():
    return FileSystemStorage(location=settings.INCIDENT_MEDIA_ROOT)


def _name(photo):
    return f"{photo.object_key.hex}.jpg"


def _validate_image(upload):
    if not upload or not 0 < upload.size <= MAX_PHOTO_BYTES:
        raise RentalError("Ảnh phải có dung lượng tối đa 5 MB.")
    source = upload.read(MAX_PHOTO_BYTES + 1)
    if len(source) > MAX_PHOTO_BYTES:
        raise RentalError("Ảnh phải có dung lượng tối đa 5 MB.")
    try:
        with Image.open(BytesIO(source)) as image:
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or image.width * image.height > 20_000_000
                or getattr(image, "n_frames", 1) != 1
            ):
                raise RentalError("Chọn một ảnh JPEG, PNG hoặc WebP tối đa 20 megapixel.")
            clean = ImageOps.exif_transpose(image).convert("RGB")
            clean.info.clear()
            clean.thumbnail((2400, 2400))
            sanitized = BytesIO()
            clean.save(sanitized, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise RentalError("Không đọc được ảnh đã chọn.") from error
    return sha256(source).hexdigest(), sanitized.getvalue()


def attach_photo(actor, case_id, command_id, upload):
    if not can_operate(actor):
        raise RentalError("Cần quyền vận hành để đính ảnh.", 403)
    try:
        command_id = UUID(str(command_id))
    except (ValueError, TypeError) as error:
        raise RentalError("Mã yêu cầu không hợp lệ.") from error
    digest, content = _validate_image(upload)
    storage = _storage()
    stored = None
    try:
        with transaction.atomic():
            case = MaintenanceCase.objects.select_for_update().get(pk=case_id)
            if case.kind not in PHOTO_KINDS:
                raise RentalError("Chỉ đính ảnh cho sự cố hỏng hoặc thiếu phụ kiện.", 409)
            previous = case.photos.filter(command_id=command_id).first()
            if previous:
                if previous.original_digest != digest or previous.uploaded_by_id != actor.pk:
                    raise RentalError("Mã yêu cầu đã được dùng cho ảnh khác.", 409)
                return previous
            if case.photos.count() >= 3:
                raise RentalError("Mỗi hồ sơ có tối đa ba ảnh.", 409)
            photo = IncidentPhoto(
                case=case, command_id=command_id, original_digest=digest, uploaded_by=actor,
                object_key=uuid4(), expires_at=timezone.now() + timedelta(days=90),
            )
            stored = storage.save(_name(photo), ContentFile(content))
            if stored != _name(photo):
                raise RentalError("Không lưu được ảnh. Hãy thử lại.", 503)
            photo.save()
            return photo
    except Exception as error:
        if stored:
            storage.delete(stored)
        if isinstance(error, OSError):
            raise RentalError("Không lưu được ảnh. Hãy thử lại.", 503) from error
        raise


def open_photo(actor, case_id, photo_id):
    if not can_operate(actor):
        raise RentalError("Cần quyền vận hành để xem ảnh.", 403)
    photo = IncidentPhoto.objects.get(
        pk=photo_id, case_id=case_id, expires_at__gt=timezone.now(), deleted_at__isnull=True
    )
    return _storage().open(_name(photo), "rb")


def purge_expired_photos():
    now = timezone.now()
    storage = _storage()
    removed = 0
    while True:
        with transaction.atomic():
            photos = list(
                IncidentPhoto.objects.select_for_update(skip_locked=True)
                .filter(expires_at__lte=now, deleted_at__isnull=True).order_by("pk")[:100]
            )
            if not photos:
                return removed
            for photo in photos:
                storage.delete(_name(photo))
                photo.deleted_at = now
            IncidentPhoto.objects.bulk_update(photos, ["deleted_at"])
            removed += len(photos)
