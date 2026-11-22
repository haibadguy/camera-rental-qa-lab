from django.contrib.auth import views as auth_views
from django.urls import path

from catalog import api, views

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
    path("rentals/<int:rental_id>/", views.rental_detail, name="rental-detail"),
    path("rentals/<int:rental_id>/cancel/", views.cancel, name="cancel-rental"),
    path("staff/equipment/new/", views.manage_equipment, name="new-equipment"),
    path("staff/equipment/", views.staff_equipment, name="staff-equipment"),
    path(
        "staff/equipment/<int:equipment_id>/",
        views.manage_equipment,
        name="edit-equipment",
    ),
    path("staff/rentals/", views.staff_rentals, name="staff-rentals"),
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
]
