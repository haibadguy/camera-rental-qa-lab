from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_rental")]

    operations = [
        migrations.AddField(
            model_name="rental",
            name="picked_up_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="rental",
            name="cancellation_reason",
            field=models.CharField(
                blank=True,
                choices=[("NO_SHOW", "Khách không đến nhận thiết bị")],
                default="",
                max_length=7,
            ),
        ),
        migrations.AlterField(
            model_name="rental",
            name="status",
            field=models.CharField(
                choices=[
                    ("CONFIRMED", "Đã đặt"),
                    ("PICKED_UP", "Đã bàn giao"),
                    ("CANCELLED", "Đã hủy"),
                    ("RETURNED", "Đã trả"),
                ],
                default="CONFIRMED",
                max_length=9,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="rental", name="rental_return_state_valid"
        ),
        migrations.AddConstraint(
            model_name="rental",
            constraint=models.CheckConstraint(
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
        ),
        migrations.AddConstraint(
            model_name="rental",
            constraint=models.CheckConstraint(
                condition=models.Q(cancellation_reason="")
                | models.Q(status="CANCELLED", cancellation_reason="NO_SHOW"),
                name="rental_cancel_reason_valid",
            ),
        ),
    ]
