from django.contrib.auth.models import Group, Permission

OPERATOR_GROUP = "Rental Operators"
MANAGER_GROUP = "Rental Managers"
FINANCE_CLERK_GROUP = "Rental Finance Clerks"
FINANCE_MANAGER_GROUP = "Rental Finance Managers"
OPERATE = "operate_rentals"
MANAGE = "manage_rental_incidents"
RECORD_FINANCE = "record_rental_finance"
MANAGE_FINANCE = "manage_rental_finance"

ROLE_GROUPS = {
    "operator": OPERATOR_GROUP,
    "manager": MANAGER_GROUP,
    "finance-clerk": FINANCE_CLERK_GROUP,
    "finance-manager": FINANCE_MANAGER_GROUP,
}


def can_operate(user):
    return user.is_authenticated and user.has_perm(f"catalog.{OPERATE}")


def can_manage(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE}")


def can_record_finance(user):
    return user.is_authenticated and user.has_perm(f"catalog.{RECORD_FINANCE}")


def can_manage_finance(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE_FINANCE}")


def create_operation_groups(sender, using, **kwargs):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.using(using).filter(
            content_type__app_label="catalog",
            content_type__model="rental",
            codename__in=(OPERATE, MANAGE, RECORD_FINANCE, MANAGE_FINANCE),
        )
    }
    groups = Group.objects.using(using)
    for group_name, codenames in (
        (OPERATOR_GROUP, (OPERATE,)),
        (MANAGER_GROUP, (OPERATE, MANAGE)),
        (FINANCE_CLERK_GROUP, (RECORD_FINANCE,)),
        (FINANCE_MANAGER_GROUP, (RECORD_FINANCE, MANAGE_FINANCE)),
    ):
        if all(codename in permissions for codename in codenames):
            group, _ = groups.get_or_create(name=group_name)
            group.permissions.add(*(permissions[codename] for codename in codenames))
