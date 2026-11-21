from django.conf import settings
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
    is_active = models.BooleanField(default=True)

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

    class CancellationReason(models.TextChoices):
        NO_SHOW = "NO_SHOW", "Khách không đến nhận thiết bị"

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    pickup_date = models.DateField()
    return_date = models.DateField()
    quantity = models.PositiveIntegerField()
    daily_rate_vnd = models.PositiveIntegerField()
    total_vnd = models.DecimalField(max_digits=26, decimal_places=0)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.CONFIRMED
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
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
        indexes = [
            models.Index(
                fields=["equipment", "status", "return_date"],
                name="rental_stock_window_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="rental_quantity_positive"
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
                        status__in=["CONFIRMED", "CANCELLED"],
                        picked_up_at__isnull=True,
                        returned_at__isnull=True,
                    )
                ),
                name="rental_return_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(cancellation_reason="")
                | models.Q(status="CANCELLED", cancellation_reason="NO_SHOW"),
                name="rental_cancel_reason_valid",
            ),
        ]
