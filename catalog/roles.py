from django.contrib.auth.models import Group, Permission

OPERATOR_GROUP = "Rental Operators"
MANAGER_GROUP = "Rental Managers"
FINANCE_CLERK_GROUP = "Rental Finance Clerks"
FINANCE_MANAGER_GROUP = "Rental Finance Managers"
STOCK_COUNTER_GROUP = "Rental Stock Counters"
REPORTING_MANAGER_GROUP = "Rental Reporting Managers"
COUNTER_BOOKER_GROUP = "Rental Counter Bookers"
BOOK_FOR_CUSTOMER = "book_for_customer"
OPERATE = "operate_rentals"
MANAGE = "manage_rental_incidents"
RECORD_FINANCE = "record_rental_finance"
MANAGE_FINANCE = "manage_rental_finance"
COUNT_STOCK = "count_rental_stock"
MANAGE_REPORTING = "manage_rental_reporting"

ROLE_GROUPS = {
    "operator": OPERATOR_GROUP,
    "counter-booker": COUNTER_BOOKER_GROUP,
    "manager": MANAGER_GROUP,
    "finance-clerk": FINANCE_CLERK_GROUP,
    "finance-manager": FINANCE_MANAGER_GROUP,
    "stock-counter": STOCK_COUNTER_GROUP,
    "reporting-manager": REPORTING_MANAGER_GROUP,
}

ROLE_FAMILIES = (
    (COUNTER_BOOKER_GROUP,),
    (OPERATOR_GROUP, MANAGER_GROUP),
    (FINANCE_CLERK_GROUP, FINANCE_MANAGER_GROUP),
    (STOCK_COUNTER_GROUP, REPORTING_MANAGER_GROUP),
)


def can_operate(user):
    return user.is_authenticated and user.has_perm(f"catalog.{OPERATE}")


def can_book_for_customer(user):
    return can_operate(user) and user.has_perm(f"catalog.{BOOK_FOR_CUSTOMER}")


def can_manage(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE}")


def can_record_finance(user):
    return user.is_authenticated and user.has_perm(f"catalog.{RECORD_FINANCE}")


def can_manage_finance(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE_FINANCE}")


def can_count_stock(user):
    return user.is_authenticated and user.has_perm(f"catalog.{COUNT_STOCK}")


def can_manage_reporting(user):
    return user.is_authenticated and user.has_perm(f"catalog.{MANAGE_REPORTING}")


def create_operation_groups(sender, using, **kwargs):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.using(using).filter(
            content_type__app_label="catalog",
            content_type__model="rental",
            codename__in=(
                OPERATE,
                BOOK_FOR_CUSTOMER,
                MANAGE,
                RECORD_FINANCE,
                MANAGE_FINANCE,
                COUNT_STOCK,
                MANAGE_REPORTING,
            ),
        )
    }
    groups = Group.objects.using(using)
    for group_name, codenames in (
        (OPERATOR_GROUP, (OPERATE,)),
        (COUNTER_BOOKER_GROUP, (BOOK_FOR_CUSTOMER,)),
        (MANAGER_GROUP, (OPERATE, MANAGE)),
        (FINANCE_CLERK_GROUP, (RECORD_FINANCE,)),
        (FINANCE_MANAGER_GROUP, (RECORD_FINANCE, MANAGE_FINANCE)),
        (STOCK_COUNTER_GROUP, (COUNT_STOCK,)),
        (REPORTING_MANAGER_GROUP, (COUNT_STOCK, MANAGE_REPORTING)),
    ):
        if all(codename in permissions for codename in codenames):
            group, _ = groups.get_or_create(name=group_name)
            group.permissions.add(*(permissions[codename] for codename in codenames))
