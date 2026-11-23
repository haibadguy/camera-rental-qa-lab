from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.roles import (
    FINANCE_CLERK_GROUP,
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    OPERATOR_GROUP,
    ROLE_GROUPS,
)


class Command(BaseCommand):
    help = "Assign an operational role to an existing active staff account."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=ROLE_GROUPS)

    @transaction.atomic
    def handle(self, *args, username, role, **options):
        users = get_user_model().objects.select_for_update()
        account = users.filter(username=username, is_staff=True, is_active=True).first()
        if account is None:
            raise CommandError("Use an existing active staff account.")
        target_name = ROLE_GROUPS[role]
        finance = (FINANCE_CLERK_GROUP, FINANCE_MANAGER_GROUP)
        family = finance if target_name in finance else (OPERATOR_GROUP, MANAGER_GROUP)
        groups = Group.objects.filter(name__in=family)
        target = groups.filter(name=target_name).first()
        if target is None:
            raise CommandError("Run migrations before assigning operational roles.")
        account.groups.remove(*groups)
        account.groups.add(target)
        self.stdout.write(self.style.SUCCESS("Rental role assigned."))
