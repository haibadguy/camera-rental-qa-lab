from django.contrib.auth.models import Group, Permission

OPERATOR_GROUP = "Rental Operators"
MANAGER_GROUP = "Rental Managers"
OPERATE = "operate_rentals"
MANAGE = "manage_rental_incidents"


def can_operate(user):
    return user.is_authenticated and user.has_perm(f"catalog.{OPERATE}")


def can_manage(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE}")


def create_operation_groups(sender, using, **kwargs):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.using(using).filter(
            content_type__app_label="catalog",
            content_type__model="rental",
            codename__in=(OPERATE, MANAGE),
        )
    }
    if len(permissions) != 2:
        return
    groups = Group.objects.using(using)
    operator, _ = groups.get_or_create(name=OPERATOR_GROUP)
    manager, _ = groups.get_or_create(name=MANAGER_GROUP)
    operator.permissions.add(permissions[OPERATE])
    manager.permissions.add(permissions[OPERATE], permissions[MANAGE])
