from django.contrib.auth import views as auth_views
from django.urls import path

from catalog import api, operations_api, operations_web, views

urlpatterns = [
    path("", views.equipment_list, name="equipment-list"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="catalog/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path(
        "equipment/<int:equipment_id>/", views.equipment_detail, name="equipment-detail"
    ),
    path("equipment/<int:equipment_id>/book/", views.book, name="book"),
    path("rentals/", views.my_rentals, name="my-rentals"),
    path("rentals/new/", views.book_order, name="book-order"),
    path("rentals/<int:rental_id>/", views.rental_detail, name="rental-detail"),
    path("rentals/<int:rental_id>/cancel/", views.cancel, name="cancel-rental"),
    path(
        "rentals/<int:rental_id>/change/",
        operations_web.rental_change,
        name="rental-change",
    ),
    path("staff/equipment/new/", views.manage_equipment, name="new-equipment"),
    path("staff/equipment/", views.staff_equipment, name="staff-equipment"),
    path(
        "staff/equipment/<int:equipment_id>/assets/",
        views.staff_assets,
        name="staff-assets",
    ),
    path(
        "staff/equipment/<int:equipment_id>/",
        views.manage_equipment,
        name="edit-equipment",
    ),
    path("staff/rentals/", views.staff_rentals, name="staff-rentals"),
    path("staff/operations/", operations_web.operations_queue, name="operations-queue"),
    path(
        "staff/rentals/<int:rental_id>/operations/",
        operations_web.operations_order,
        name="operations-order",
    ),
    path(
        "staff/rentals/<int:rental_id>/operations/changes/<int:change_id>/",
        operations_web.review_change,
        name="operations-review-change",
    ),
    path(
        "staff/maintenance/", operations_web.maintenance_list, name="maintenance-list"
    ),
    path(
        "staff/maintenance/plan/",
        operations_web.maintenance_new,
        {"planned": True},
        name="maintenance-plan",
    ),
    path(
        "staff/maintenance/report/",
        operations_web.maintenance_new,
        name="maintenance-report",
    ),
    path(
        "staff/maintenance/<int:case_id>/",
        operations_web.maintenance_detail,
        name="maintenance-detail",
    ),
    path(
        "staff/rentals/<int:rental_id>/",
        views.staff_rental_detail,
        name="staff-rental-detail",
    ),
    path(
        "staff/rentals/<int:rental_id>/pick-up/",
        views.pick_up,
        name="pick-up-rental",
    ),
    path(
        "staff/rentals/<int:rental_id>/no-show/",
        views.no_show,
        name="no-show-rental",
    ),
    path(
        "staff/rentals/<int:rental_id>/return/",
        views.record_return,
        name="return-rental",
    ),
    path(
        "staff/rentals/<int:rental_id>/assets/<int:reservation_id>/replace/",
        views.replace_asset,
        name="replace-asset",
    ),
    path("api/equipment/", api.equipment_list, name="api-equipment-list"),
    path(
        "api/equipment/<int:equipment_id>/",
        api.equipment_detail,
        name="api-equipment-detail",
    ),
    path("api/rentals/", api.rentals, name="api-rentals"),
    path("api/rentals/<int:rental_id>/", api.rental_detail, name="api-rental-detail"),
    path("api/rentals/<int:rental_id>/cancel/", api.cancel, name="api-cancel"),
    path("api/rentals/<int:rental_id>/pick-up/", api.pick_up, name="api-pick-up"),
    path("api/rentals/<int:rental_id>/no-show/", api.no_show, name="api-no-show"),
    path("api/rentals/<int:rental_id>/return/", api.record_return, name="api-return"),
    path("api/v2/rentals/", api.orders, name="api-orders"),
    path("api/v2/rentals/<int:rental_id>/", api.order_detail, name="api-order-detail"),
    path(
        "api/v2/rentals/<int:rental_id>/cancel/",
        api.cancel_order,
        name="api-cancel-order",
    ),
    path(
        "api/v2/rentals/<int:rental_id>/changes/",
        operations_api.rental_changes,
        name="api-rental-changes",
    ),
    path(
        "api/v2/rentals/<int:rental_id>/changes/quote/",
        operations_api.change_quote,
        name="api-change-quote",
    ),
    path(
        "api/v2/operations/",
        operations_api.operations_queue,
        name="api-operations-queue",
    ),
    path(
        "api/v2/operations/rentals/<int:rental_id>/",
        operations_api.operations_order,
        name="api-operations-order",
    ),
    path(
        "api/v2/operations/rentals/<int:rental_id>/reservations/<int:reservation_id>/prepare/",
        operations_api.prepare_asset,
        name="api-prepare-asset",
    ),
    path(
        "api/v2/operations/rentals/<int:rental_id>/pick-up/",
        operations_api.pick_up,
        name="api-operations-pick-up",
    ),
    path(
        "api/v2/operations/rentals/<int:rental_id>/handovers/<int:handover_id>/receive/",
        operations_api.receive_asset,
        name="api-receive-asset",
    ),
    path(
        "api/v2/operations/rentals/<int:rental_id>/handovers/<int:handover_id>/inspect/",
        operations_api.inspect_asset,
        name="api-inspect-asset",
    ),
    path(
        "api/v2/operations/changes/<int:change_id>/review/",
        operations_api.review_change,
        name="api-review-change",
    ),
    path(
        "api/v2/operations/maintenance/",
        operations_api.maintenance_cases,
        name="api-maintenance-cases",
    ),
    path(
        "api/v2/operations/maintenance/plan/",
        operations_api.plan_maintenance,
        name="api-maintenance-plan",
    ),
    path(
        "api/v2/operations/maintenance/report/",
        operations_api.report_incident,
        name="api-maintenance-report",
    ),
    path(
        "api/v2/operations/maintenance/<int:case_id>/repair/",
        operations_api.start_repair,
        name="api-maintenance-repair",
    ),
    path(
        "api/v2/operations/maintenance/<int:case_id>/resolve/",
        operations_api.resolve_case,
        name="api-maintenance-resolve",
    ),
]
