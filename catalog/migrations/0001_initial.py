from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Equipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("daily_rate_vnd", models.PositiveIntegerField()),
                ("total_stock", models.PositiveIntegerField()),
            ],
            options={"ordering": ["code"]},
        ),
    ]
