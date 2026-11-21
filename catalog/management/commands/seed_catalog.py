from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Equipment


DEMO_EQUIPMENT = (
    (
        "CAM-001",
        "Sony A6400",
        300_000,
        2,
        Equipment.Kind.CAMERA,
        "Cảm biến APS-C 24,2 MP\nNgàm Sony E\nQuay video 4K",
    ),
    (
        "CAM-002",
        "Canon EOS R50",
        350_000,
        1,
        Equipment.Kind.CAMERA,
        "Cảm biến APS-C 24,2 MP\nNgàm Canon RF\nQuay video 4K",
    ),
    (
        "LEN-001",
        "Sigma 30mm f/1.4 DC DN",
        150_000,
        2,
        Equipment.Kind.LENS,
        "Tiêu cự 30 mm\nKhẩu độ f/1.4\nPhiên bản ngàm Sony E",
    ),
)


class Command(BaseCommand):
    help = "Add the demo equipment to the local catalog."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for (
            code,
            name,
            daily_rate_vnd,
            total_stock,
            kind,
            specifications,
        ) in DEMO_EQUIPMENT:
            _, was_created = Equipment.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "daily_rate_vnd": daily_rate_vnd,
                    "total_stock": total_stock,
                    "kind": kind,
                    "specifications": specifications,
                },
            )
            created += was_created

        self.stdout.write(f"Created {created} demo equipment entries.")
