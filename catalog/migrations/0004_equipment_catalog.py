from django.db import migrations, models


def classify_lenses(apps, schema_editor):
    equipment = apps.get_model("catalog", "Equipment")
    catalog = equipment.objects.using(schema_editor.connection.alias)
    catalog.filter(code__startswith="LEN-").update(kind="LENS")
    demo_specs = {
        ("CAM-001", "Sony A6400"): "Cảm biến APS-C 24,2 MP\nNgàm Sony E\nQuay video 4K",
        (
            "CAM-002",
            "Canon EOS R50",
        ): "Cảm biến APS-C 24,2 MP\nNgàm Canon RF\nQuay video 4K",
        (
            "LEN-001",
            "Sigma 30mm f/1.4 DC DN",
        ): "Tiêu cự 30 mm\nKhẩu độ f/1.4\nPhiên bản ngàm Sony E",
    }
    for (code, name), specs in demo_specs.items():
        catalog.filter(code=code, name=name).update(specifications=specs)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_rental_lifecycle")]

    operations = [
        migrations.AddField(
            model_name="equipment",
            name="kind",
            field=models.CharField(
                choices=[("CAMERA", "Máy ảnh"), ("LENS", "Ống kính")],
                default="CAMERA",
                max_length=6,
            ),
        ),
        migrations.AddField(
            model_name="equipment",
            name="specifications",
            field=models.TextField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="equipment",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(classify_lenses, migrations.RunPython.noop),
    ]
