from django.core.management.base import BaseCommand

from catalog.incident_photos import purge_expired_photos


class Command(BaseCommand):
    help = "Delete expired incident images while retaining their audit records."

    def handle(self, *args, **options):
        removed = purge_expired_photos()
        self.stdout.write(f"Deleted {removed} expired incident photos.")
