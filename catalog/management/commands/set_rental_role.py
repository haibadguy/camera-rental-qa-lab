from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.roles import MANAGER_GROUP, OPERATOR_GROUP


class Command(BaseCommand):
    help = "Assign an operational role to an existing active staff account."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=("operator", "manager"))

    @transaction.atomic
    def handle(self, *args, username, role, **options):
        users = get_user_model().objects.select_for_update()
        account = users.filter(username=username, is_staff=True, is_active=True).first()
        if account is None:
            raise CommandError("Use an existing active staff account.")
        groups = Group.objects.filter(name__in=(OPERATOR_GROUP, MANAGER_GROUP))
        target = groups.filter(
            name=MANAGER_GROUP if role == "manager" else OPERATOR_GROUP
        ).first()
        if target is None:
            raise CommandError("Run migrations before assigning operational roles.")
        account.groups.remove(*groups)
        account.groups.add(target)
        self.stdout.write(self.style.SUCCESS("Operational role assigned."))
