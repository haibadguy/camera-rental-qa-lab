from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.finance import Ledger, snapshot_values
from catalog.models import Rental, RentalFinanceSnapshot


class Command(BaseCommand):
    help = "Build or verify order balances against the underlying ledger."

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true")

    def handle(self, *args, verify, **options):
        last_id = 0
        processed = 0
        while True:
            with transaction.atomic():
                rentals = list(
                    Rental.objects.filter(pk__gt=last_id)
                    .select_for_update()
                    .order_by("pk")
                    .prefetch_related("lines", "finance_entries", "finance_charges")[:500]
                )
                if not rentals:
                    break
                expected = [
                    RentalFinanceSnapshot(rental=rental, **snapshot_values(
                        Ledger(rental, list(rental.finance_entries.all()), list(rental.finance_charges.all()))
                    ))
                    for rental in rentals
                ]
                fields = ["balance_due_vnd", "deposit_held_vnd", "legacy_pending"]
                if verify:
                    ids = [rental.pk for rental in rentals]
                    actual = {
                        row[0]: row[1:] for row in RentalFinanceSnapshot.objects.filter(
                            rental_id__in=ids
                        ).values_list("rental_id", *fields)
                    }
                    for snapshot in expected:
                        values = tuple(getattr(snapshot, field) for field in fields)
                        if actual.get(snapshot.rental_id) != values:
                            raise CommandError(f"Ledger mismatch for order {snapshot.rental_id}")
                else:
                    RentalFinanceSnapshot.objects.bulk_create(
                        expected, update_conflicts=True, update_fields=fields, unique_fields=["rental"]
                    )
                last_id = rentals[-1].pk
                processed += len(rentals)
        action = "Verified" if verify else "Rebuilt"
        self.stdout.write(f"{action} {processed} order balances.")
