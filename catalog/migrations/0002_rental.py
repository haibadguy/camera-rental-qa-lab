import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Rental",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pickup_date", models.DateField()),
                ("return_date", models.DateField()),
                ("quantity", models.PositiveIntegerField()),
                ("daily_rate_vnd", models.PositiveIntegerField()),
                ("total_vnd", models.DecimalField(decimal_places=0, max_digits=26)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CONFIRMED", "Đã đặt"),
                            ("CANCELLED", "Đã hủy"),
                            ("RETURNED", "Đã trả"),
                        ],
                        default="CONFIRMED",
                        max_length=9,
                    ),
                ),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "equipment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalog.equipment",
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
                "indexes": [
                    models.Index(
                        fields=["equipment", "status", "return_date"],
                        name="rental_stock_window_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(quantity__gt=0),
                        name="rental_quantity_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(return_date__gt=models.F("pickup_date")),
                        name="rental_dates_in_order",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(status="RETURNED", returned_at__isnull=False)
                            | models.Q(
                                status__in=["CONFIRMED", "CANCELLED"],
                                returned_at__isnull=True,
                            )
                        ),
                        name="rental_return_state_valid",
                    ),
                ],
            },
        ),
    ]
