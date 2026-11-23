from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.utils import timezone


class Equipment(models.Model):
    class Kind(models.TextChoices):
        CAMERA = "CAMERA", "Máy ảnh"
        LENS = "LENS", "Ống kính"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    daily_rate_vnd = models.PositiveIntegerField()
    total_stock = models.PositiveIntegerField()
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.CAMERA)
    specifications = models.TextField(blank=True, max_length=1000)
    accessory_checklist = models.TextField(
        "Phụ kiện cần kiểm tra", blank=True, max_length=2000
    )
    is_active = models.BooleanField(default=True)
    tracks_assets = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class Rental(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Đã đặt"
        PICKED_UP = "PICKED_UP", "Đã bàn giao"
        CANCELLED = "CANCELLED", "Đã hủy"
        RETURNED = "RETURNED", "Đã trả"
        CLOSED = "CLOSED", "Đóng có ngoại lệ"

    class CancellationReason(models.TextChoices):
        NO_SHOW = "NO_SHOW", "Khách không đến nhận thiết bị"

    # The scalar fields are the v1 projection. Multi-item orders use lines only.
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, null=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    pickup_date = models.DateField()
    return_date = models.DateField()
    quantity = models.PositiveIntegerField(null=True)
    daily_rate_vnd = models.PositiveIntegerField(null=True)
    total_vnd = models.DecimalField(max_digits=26, decimal_places=0)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.CONFIRMED
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(
        max_length=7, choices=CancellationReason.choices, blank=True, default=""
    )

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.PICKED_UP
            and timezone.localdate() > self.return_date
        )

    @property
    def was_returned_late(self):
        return (
            self.returned_at is not None
            and timezone.localdate(self.returned_at) > self.return_date
        )

    class Meta:
        ordering = ["-id"]
        permissions = [
            ("operate_rentals", "Can perform rental operations"),
            ("manage_rental_incidents", "Can resolve rental incidents"),
        ]
        indexes = [
            models.Index(
                fields=["equipment", "status", "return_date"],
                name="rental_stock_window_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        equipment__isnull=True,
                        quantity__isnull=True,
                        daily_rate_vnd__isnull=True,
                    )
                    | models.Q(
                        equipment__isnull=False,
                        quantity__isnull=False,
                        quantity__gt=0,
                        daily_rate_vnd__isnull=False,
                    )
                ),
                name="rental_legacy_projection_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(return_date__gt=models.F("pickup_date")),
                name="rental_dates_in_order",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(status="RETURNED", returned_at__isnull=False)
                        & (
                            models.Q(picked_up_at__isnull=True)
                            | models.Q(returned_at__gte=models.F("picked_up_at"))
                        )
                    )
                    | models.Q(
                        status="PICKED_UP",
                        picked_up_at__isnull=False,
                        returned_at__isnull=True,
                    )
                    | models.Q(
                        status="CLOSED",
                        picked_up_at__isnull=False,
                        returned_at__isnull=True,
                    )
                    | models.Q(
                        status__in=["CONFIRMED", "CANCELLED"],
                        picked_up_at__isnull=True,
                        returned_at__isnull=True,
                    )
                ),
                name="rental_return_state_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="CLOSED", closed_at__isnull=False)
                    | (~models.Q(status="CLOSED") & models.Q(closed_at__isnull=True))
                ),
                name="rental_exception_has_close_time",
            ),
            models.CheckConstraint(
                condition=models.Q(cancellation_reason="")
                | models.Q(status="CANCELLED", cancellation_reason="NO_SHOW"),
                name="rental_cancel_reason_valid",
            ),
        ]


class AssetUnit(models.Model):
    class Status(models.TextChoices):
        READY = "READY", "Sẵn sàng"
        INSPECTION = "INSPECTION", "Chờ kiểm tra"
        QUARANTINED = "QUARANTINED", "Cách ly"
        RETIRED = "RETIRED", "Ngừng sử dụng"

    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="assets"
    )
    code = models.CharField("Mã kho", max_length=48, unique=True)
    serial = models.CharField("Serial hãng", max_length=100, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.READY
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class RentalLine(models.Model):
    rental = models.ForeignKey(Rental, on_delete=models.PROTECT, related_name="lines")
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    daily_rate_vnd = models.PositiveIntegerField()
    total_vnd = models.DecimalField(max_digits=26, decimal_places=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["rental", "equipment"], name="rental_line_equipment_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="rental_line_quantity_positive"
            ),
        ]


class AssetReservation(models.Model):
    asset = models.ForeignKey(
        AssetUnit, on_delete=models.PROTECT, related_name="reservations"
    )
    line = models.ForeignKey(
        RentalLine, on_delete=models.PROTECT, related_name="reservations", null=True
    )
    maintenance = models.OneToOneField(
        "MaintenanceCase",
        on_delete=models.PROTECT,
        related_name="reservation",
        null=True,
    )
    period = DateRangeField()
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True
    )
    replaces = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, related_name="replacement"
    )

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="asset_reservation_no_overlap",
                expressions=[
                    ("asset", RangeOperators.EQUAL),
                    ("period", RangeOperators.OVERLAPS),
                ],
                condition=models.Q(released_at__isnull=True),
            ),
            models.CheckConstraint(
                condition=models.Q(period__isempty=False),
                name="asset_reservation_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(line__isnull=False, maintenance__isnull=True)
                    | models.Q(line__isnull=True, maintenance__isnull=False)
                ),
                name="asset_reservation_exactly_one_source",
            ),
        ]


class AssetHandover(models.Model):
    class Inspection(models.TextChoices):
        READY = "READY", "Đạt kiểm tra"
        DAMAGE = "DAMAGE", "Hư hỏng"
        MISSING_ACCESSORY = "MISSING_ACCESSORY", "Thiếu phụ kiện"

    reservation = models.OneToOneField(
        AssetReservation, on_delete=models.PROTECT, related_name="handover"
    )
    asset = models.ForeignKey(
        AssetUnit, on_delete=models.PROTECT, related_name="handovers"
    )
    prepared_at = models.DateTimeField(auto_now_add=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    expected_accessories = models.TextField(blank=True)
    pickup_notes = models.TextField(blank=True, max_length=2000)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    picked_up_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    inspected_at = models.DateTimeField(null=True, blank=True)
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    inspection_result = models.CharField(
        max_length=24, choices=Inspection.choices, blank=True
    )
    return_notes = models.TextField(blank=True, max_length=2000)
    lost_at = models.DateTimeField(null=True, blank=True)
    lost_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(
                    picked_up_at__isnull=False,
                    returned_at__isnull=True,
                    lost_at__isnull=True,
                ),
                name="asset_single_open_handover",
            ),
            models.CheckConstraint(
                condition=models.Q(returned_at__isnull=True)
                | models.Q(
                    picked_up_at__isnull=False,
                    lost_at__isnull=True,
                    returned_at__gte=models.F("picked_up_at"),
                ),
                name="asset_return_follows_pickup",
            ),
            models.CheckConstraint(
                condition=models.Q(inspected_at__isnull=True)
                | models.Q(
                    returned_at__isnull=False, inspected_at__gte=models.F("returned_at")
                ),
                name="asset_inspection_follows_return",
            ),
            models.CheckConstraint(
                condition=models.Q(lost_at__isnull=True)
                | models.Q(
                    picked_up_at__isnull=False,
                    lost_at__gte=models.F("picked_up_at"),
                ),
                name="asset_loss_follows_pickup",
            ),
        ]


class RentalChangeRequest(models.Model):
    class Kind(models.TextChoices):
        RESCHEDULE = "RESCHEDULE", "Đổi lịch"
        EXTEND = "EXTEND", "Gia hạn"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Chờ duyệt"
        APPROVED = "APPROVED", "Đã duyệt"
        REJECTED = "REJECTED", "Đã từ chối"

    rental = models.ForeignKey(Rental, on_delete=models.PROTECT, related_name="changes")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    pickup_date = models.DateField()
    return_date = models.DateField()
    old_pickup_date = models.DateField()
    old_return_date = models.DateField()
    old_total_vnd = models.DecimalField(max_digits=26, decimal_places=0)
    quoted_total_vnd = models.DecimalField(max_digits=26, decimal_places=0)
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    review_note = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["-id"]


class MaintenanceCase(models.Model):
    class Kind(models.TextChoices):
        PLANNED = "PLANNED", "Bảo trì theo lịch"
        DAMAGE = "DAMAGE", "Hư hỏng"
        MISSING_ACCESSORY = "MISSING_ACCESSORY", "Thiếu phụ kiện"
        LOST = "LOST", "Mất thiết bị"

    class State(models.TextChoices):
        PLANNED = "PLANNED", "Đã lên lịch"
        OPEN = "OPEN", "Chờ xử lý"
        IN_REPAIR = "IN_REPAIR", "Đang sửa"
        RESOLVED = "RESOLVED", "Đã xử lý"

    class Resolution(models.TextChoices):
        READY = "READY", "Đạt kiểm tra, đưa về kho"
        RETIRED = "RETIRED", "Ngừng sử dụng"

    asset = models.ForeignKey(
        AssetUnit, on_delete=models.PROTECT, related_name="maintenance_cases"
    )
    handover = models.ForeignKey(
        AssetHandover, on_delete=models.PROTECT, null=True, related_name="incidents"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.OPEN)
    notes = models.TextField(max_length=2000)
    reported_at = models.DateTimeField(auto_now_add=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    repair_notes = models.TextField(blank=True, max_length=2000)
    repaired_at = models.DateTimeField(null=True, blank=True)
    repaired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    resolution = models.CharField(max_length=16, choices=Resolution.choices, blank=True)
    resolution_notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset"],
                condition=~models.Q(kind="PLANNED") & ~models.Q(state="RESOLVED"),
                name="asset_one_open_unplanned_incident",
            ),
        ]
