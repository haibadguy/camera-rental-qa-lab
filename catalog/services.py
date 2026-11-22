"""Shared rental and inventory operations for the web and API."""

from .equipment import catalog_items, create_equipment, update_equipment
from .errors import RentalError
from .inventory import (
    MAX_RENTAL_DAYS,
    available_stock,
    catalog_availability,
    checked_out_quantity,
    equipment_with_physical_stock,
    validate_period,
)
from .rentals import (
    MAX_RENTAL_QUANTITY,
    MIN_RENTAL_QUANTITY,
    StaffRentalQueue,
    book_rental,
    can_cancel,
    can_mark_no_show,
    can_pick_up,
    can_return,
    cancel_rental,
    customer_rentals,
    mark_no_show,
    pick_up_rental,
    return_rental,
    staff_rentals,
)


__all__ = [
    "MAX_RENTAL_DAYS",
    "MAX_RENTAL_QUANTITY",
    "MIN_RENTAL_QUANTITY",
    "RentalError",
    "StaffRentalQueue",
    "available_stock",
    "book_rental",
    "can_cancel",
    "can_mark_no_show",
    "can_pick_up",
    "can_return",
    "cancel_rental",
    "catalog_availability",
    "catalog_items",
    "checked_out_quantity",
    "create_equipment",
    "customer_rentals",
    "equipment_with_physical_stock",
    "mark_no_show",
    "pick_up_rental",
    "return_rental",
    "staff_rentals",
    "update_equipment",
    "validate_period",
]
