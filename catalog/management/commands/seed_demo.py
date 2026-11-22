from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.inventory import free_assets
from catalog.models import AssetReservation, Equipment, Rental, RentalLine
from catalog.services import checked_out_quantity


class Command(BaseCommand):
    help = "Create local demo equipment, accounts and a rental due for return."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_catalog", stdout=self.stdout)
        user_model = get_user_model()

        for username, is_staff in (
            ("demo-a", False),
            ("demo-b", False),
            ("demo-staff", True),
        ):
            user, created = user_model.objects.get_or_create(
                username=username, defaults={"is_staff": is_staff}
            )
            if not created:
                continue
            user.set_password("camera-demo-2026")
            user.save(update_fields=["password"])

            if username == "demo-a":
                now = timezone.now()
                today = timezone.localdate(now)
                yesterday = today - timedelta(days=1)
                equipment = Equipment.objects.select_for_update().get(code="CAM-001")
                asset = None
                if equipment.tracks_assets:
                    asset = free_assets(
                        [equipment.pk], yesterday, today + timedelta(days=1)
                    ).first()
                    if asset is None:
                        continue
                if equipment.total_stock > checked_out_quantity(equipment):
                    rental = Rental.objects.create(
                        equipment=equipment,
                        customer=user,
                        pickup_date=yesterday,
                        return_date=today,
                        quantity=1,
                        daily_rate_vnd=equipment.daily_rate_vnd,
                        total_vnd=equipment.daily_rate_vnd,
                        status=Rental.Status.PICKED_UP,
                        picked_up_at=now - timedelta(days=1),
                    )
                    line = RentalLine.objects.create(
                        rental=rental,
                        equipment=equipment,
                        quantity=1,
                        daily_rate_vnd=rental.daily_rate_vnd,
                        total_vnd=rental.total_vnd,
                    )
                    if asset:
                        AssetReservation.objects.create(
                            line=line, asset=asset, period=(yesterday, today)
                        )
        self.stdout.write("Demo accounts are ready.")
