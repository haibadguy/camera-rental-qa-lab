import os
from datetime import datetime, time, timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone

from catalog.models import AssetHandover, AssetReservation, AssetUnit, Equipment, FinanceEntry, Rental, RentalLine
from catalog.roles import OPERATOR_GROUP, REPORTING_MANAGER_GROUP


class Command(BaseCommand):
    help = "Seed an isolated database with historical orders for the V3 scale test."

    def add_arguments(self, parser):
        parser.add_argument("--skus", type=int, default=5000)

    def handle(self, *args, skus, **options):
        if not 1 <= skus <= 5000:
            raise CommandError("Select 1–5000 synthetic SKUs.")
        if Equipment.objects.filter(code__startswith="SCALE-").exists():
            raise CommandError("Use a fresh isolated database for the scale fixture.")
        password = os.environ.get("CAMERA_SCALE_PASSWORD")
        if not password:
            raise CommandError("Set CAMERA_SCALE_PASSWORD for the synthetic accounts.")
        users = get_user_model().objects
        actor = users.create_user("scale-staff", password=password, is_staff=True)
        actor.groups.add(*Group.objects.filter(
            name__in=[OPERATOR_GROUP, REPORTING_MANAGER_GROUP]
        ))
        customers = [users.create_user(f"scale-customer-{index:02}", password=password) for index in range(10)]
        start = datetime.combine(
            timezone.localdate() - timedelta(days=360), time(9), timezone.get_default_timezone()
        )

        for batch in range(0, skus, 100):
            with transaction.atomic():
                self.seed_batch(batch, min(batch + 100, skus), start, actor, customers)
        call_command("rebuild_finance_snapshots", stdout=self.stdout)
        call_command("rebuild_finance_snapshots", "--verify", stdout=self.stdout)
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
        self.stdout.write(f"Seeded {skus} SKUs, {skus * 2} assets and {skus * 20} historical orders.")

    def seed_batch(self, lower, upper, start, actor, customers):
        equipment = Equipment.objects.bulk_create([
            Equipment(
                code=f"SCALE-{index:05}", name=f"Scale equipment {index:05}",
                brand=f"Scale brand {index % 12}", total_stock=2,
                daily_rate_vnd=100_000, tracks_assets=True,
            ) for index in range(lower, upper)
        ])
        assets = AssetUnit.objects.bulk_create([
            AssetUnit(equipment=item, code=f"{item.code}-{unit}", reporting_since=start)
            for item in equipment for unit in range(2)
        ])
        events = [
            (asset, start + timedelta(days=ordinal * 33 + index % 27))
            for index, asset in enumerate(assets) for ordinal in range(10)
        ]
        orders = Rental.objects.bulk_create([
            Rental(
                equipment_id=asset.equipment_id, customer=customers[index % len(customers)],
                pickup_date=at.date(), return_date=at.date() + timedelta(days=1),
                quantity=1, daily_rate_vnd=100_000, total_vnd=100_000,
                status=Rental.Status.RETURNED, finance_enabled=True,
                picked_up_at=at, returned_at=at + timedelta(days=1),
            ) for index, (asset, at) in enumerate(events)
        ])
        lines = RentalLine.objects.bulk_create([
            RentalLine(rental=order, equipment_id=order.equipment_id, quantity=1,
                       daily_rate_vnd=100_000, total_vnd=100_000)
            for order in orders
        ])
        holds = AssetReservation.objects.bulk_create([
            AssetReservation(line=line, asset=asset, period=(order.pickup_date, order.return_date))
            for line, order, (asset, _) in zip(lines, orders, events)
        ])
        handovers = AssetHandover.objects.bulk_create([
            AssetHandover(
                reservation=hold, asset=asset, prepared_by=actor, picked_up_by=actor,
                returned_by=actor, inspected_by=actor, picked_up_at=at,
                returned_at=at + timedelta(days=1), inspected_at=at + timedelta(days=1),
                inspection_result=AssetHandover.Inspection.READY,
            ) for hold, (asset, at) in zip(holds, events)
        ])
        AssetHandover.objects.filter(pk__range=(handovers[0].pk, handovers[-1].pk)).update(
            prepared_at=F("picked_up_at")
        )
        entries = FinanceEntry.objects.bulk_create([
            FinanceEntry(rental=order, kind=FinanceEntry.Kind.RENT_RECEIPT,
                         method=FinanceEntry.Method.CASH, amount_vnd=100_000,
                         recorded_by=actor, command_id=UUID(int=order.pk))
            for order in orders
        ])
        FinanceEntry.objects.filter(pk__range=(entries[0].pk, entries[-1].pk)).update(
            recorded_at=Subquery(Rental.objects.filter(pk=OuterRef("rental_id")).values("picked_up_at"))
        )
