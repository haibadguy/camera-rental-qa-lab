from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import Equipment, Rental


class CatalogTests(TestCase):
    def test_catalog_filters_and_detail_agree_with_api(self):
        call_command("seed_catalog", stdout=StringIO())
        lens = Equipment.objects.get(code="LEN-001")
        response = self.client.get(
            reverse("equipment-list"), {"search": "Sigma", "kind": "LENS"}
        )
        self.assertContains(response, lens.name)
        self.assertNotContains(response, "Sony A6400")
        self.assertContains(
            self.client.get(reverse("equipment-detail", args=[lens.pk])), "30 mm"
        )
        api = APIClient()
        self.assertEqual(
            api.get(reverse("api-equipment-list"), {"kind": "LENS"}).json()[0]["id"],
            lens.pk,
        )
        self.assertEqual(
            api.get(reverse("api-equipment-detail", args=[lens.pk])).json()["kind"],
            "LENS",
        )

    def test_staff_retires_equipment_through_inventory_form(self):
        staff = get_user_model().objects.create_user("inventory-staff", is_staff=True)
        self.client.force_login(staff)
        data = {
            "code": "CAM-100",
            "name": "Demo camera",
            "kind": "CAMERA",
            "specifications": "APS-C",
            "daily_rate_vnd": 100000,
            "total_stock": 2,
            "is_active": "on",
        }
        self.assertRedirects(
            self.client.post(reverse("new-equipment"), data), reverse("staff-equipment")
        )
        item = Equipment.objects.get(code="CAM-100")
        self.assertContains(
            self.client.get(reverse("staff-equipment")), "Có thực tế trong kho"
        )
        del data["is_active"]
        self.assertRedirects(
            self.client.post(reverse("edit-equipment", args=[item.pk]), data),
            reverse("staff-equipment"),
        )
        self.assertEqual(
            self.client.get(reverse("equipment-detail", args=[item.pk])).status_code,
            404,
        )
        self.assertContains(
            self.client.get(reverse("staff-equipment")), "Đã ngừng nhận đặt thuê"
        )

    def test_catalog_displays_equipment_from_database(self):
        Equipment.objects.create(
            code="CAM-900",
            name="Máy ảnh kiểm thử",
            daily_rate_vnd=120_000,
            total_stock=0,
        )

        response = self.client.get(reverse("equipment-list"))

        self.assertContains(response, "CAM-900")
        self.assertContains(response, "Máy ảnh kiểm thử")
        self.assertContains(response, "120.000 ₫/ngày")

    def test_empty_catalog_displays_message(self):
        response = self.client.get(reverse("equipment-list"))

        self.assertContains(response, "Chưa có thiết bị trong danh mục.")

    def test_seed_catalog_is_repeatable(self):
        call_command("seed_catalog", stdout=StringIO())
        first_run = list(Equipment.objects.values_list())
        call_command("seed_catalog", stdout=StringIO())

        self.assertEqual(len(first_run), 3)
        self.assertEqual(list(Equipment.objects.values_list()), first_run)
        response = self.client.get(reverse("equipment-list"))
        self.assertContains(response, "CAM-001")
        self.assertContains(response, "Sony A6400")
        self.assertContains(response, "300.000 ₫/ngày")

    def test_seed_catalog_preserves_existing_equipment(self):
        existing = Equipment.objects.create(
            code="CAM-001",
            name="Sony A6400 đã chỉnh sửa",
            daily_rate_vnd=280_000,
            total_stock=0,
        )

        call_command("seed_catalog", stdout=StringIO())

        existing.refresh_from_db()
        self.assertEqual(existing.name, "Sony A6400 đã chỉnh sửa")
        self.assertEqual(existing.daily_rate_vnd, 280_000)
        self.assertEqual(existing.total_stock, 0)
        self.assertEqual(Equipment.objects.count(), 3)

    def test_demo_seed_preserves_rentals_and_accounts_on_restart(self):
        call_command("seed_demo", stdout=StringIO())
        rental = Rental.objects.get()
        self.assertEqual(rental.status, Rental.Status.PICKED_UP)
        self.assertIsNotNone(rental.picked_up_at)
        staff = get_user_model().objects.get(username="demo-staff")
        services.return_rental(staff, rental.pk)
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertEqual(Rental.objects.get().status, Rental.Status.RETURNED)


class RegistrationTests(TestCase):
    def test_registration_and_login_create_a_customer_without_staff_privileges(self):
        password = "M1-Client-Forest-47"
        data = {
            "username": "new-customer",
            "password1": password,
            "password2": password,
            "is_staff": "1",
        }
        response = self.client.post(reverse("register"), data)
        self.assertRedirects(response, reverse("login"))
        user = get_user_model().objects.get(username=data["username"])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(password))
        self.assertEqual(self.client.post(reverse("register"), data).status_code, 400)
        self.assertRedirects(
            self.client.post(
                reverse("login"), {"username": user.username, "password": password}
            ),
            reverse("equipment-list"),
        )
        self.assertEqual(self.client.get(reverse("staff-rentals")).status_code, 403)

    def test_password_validation_rejects_invalid_registration(self):
        response = self.client.post(
            reverse("register"),
            {"username": "new-customer", "password1": "123", "password2": "123"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.exists())


class RentalFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.customer = users.create_user("customer")
        cls.other = users.create_user("other")
        cls.staff = users.create_user("staff", is_staff=True)
        cls.equipment = Equipment.objects.create(
            code="CAM-900", name="Camera", daily_rate_vnd=300_000, total_stock=2
        )
        cls.today = timezone.localdate()
        cls.pickup = cls.today + timedelta(days=1)
        cls.dropoff = cls.pickup + timedelta(days=2)

    def test_product_detail_checks_stock_and_preserves_valid_dates_for_booking(self):
        detail = reverse("equipment-detail", args=[self.equipment.pk])
        booking = reverse("book", args=[self.equipment.pk])
        period = {
            "pickup_date": self.pickup.isoformat(),
            "return_date": self.dropoff.isoformat(),
        }
        available = self.client.get(detail, period)
        self.assertContains(available, "Còn 2 thiết bị theo lịch đã chọn.")
        self.assertContains(
            available, f'{booking}?pickup_date={self.pickup}&amp;return_date={self.dropoff}'
        )
        self.client.force_login(self.customer)
        form = self.client.get(booking, period | {"quantity": 2}).context["form"]
        self.assertEqual(form["pickup_date"].value(), period["pickup_date"])
        self.assertEqual(form["return_date"].value(), period["return_date"])
        self.assertEqual(form["quantity"].value(), 1)
        self.assertFalse(Rental.objects.exists())

        services.book_rental(self.other, self.equipment.pk, self.pickup, self.dropoff, 2)
        sold_out = self.client.get(detail, period)
        self.assertContains(sold_out, "Không còn thiết bị theo lịch này.")
        self.assertNotContains(sold_out, booking)
        invalid = self.client.get(detail, period | {"return_date": self.pickup})
        self.assertContains(invalid, "Ngày trả phải sau ngày nhận.")
        self.assertIsNone(invalid.context["availability"])

    def test_web_booking_and_api_cancellation_share_stock_and_prices(self):
        self.client.force_login(self.customer)
        result = self.client.post(
            reverse("book", args=[self.equipment.pk]),
            {
                "pickup_date": self.pickup.isoformat(),
                "return_date": self.dropoff.isoformat(),
                "quantity": 2,
            },
        )
        rental = Rental.objects.get()
        self.assertRedirects(result, reverse("rental-detail", args=[rental.pk]))
        self.assertEqual(rental.total_vnd, 1_200_000)
        self.assertContains(self.client.get(result.url), "1.200.000 ₫")

        api = APIClient()
        period = {"pickup_date": self.pickup, "return_date": self.dropoff}
        listing = reverse("api-equipment-list")
        self.assertEqual(api.get(listing, period).json()[0]["available_stock"], 0)
        api.force_authenticate(self.other)
        cancel = reverse("api-cancel", args=[rental.pk])
        self.assertEqual(api.post(cancel).status_code, 404)
        api.force_authenticate(self.customer)
        self.assertEqual(api.post(cancel).json()["status"], "CANCELLED")
        self.assertEqual(api.post(cancel).status_code, 409)
        self.assertEqual(api.get(listing, period).json()[0]["available_stock"], 2)

    def test_api_rejects_invalid_dates_invalid_quantity_and_excess_stock(self):
        api = APIClient()
        api.force_authenticate(self.customer)
        booking = {
            "equipment_id": self.equipment.pk,
            "pickup_date": self.pickup.isoformat(),
            "return_date": self.dropoff.isoformat(),
            "quantity": 1,
        }
        for changes, expected in (
            ({"pickup_date": (self.today - timedelta(days=1)).isoformat()}, 400),
            ({"return_date": self.pickup.isoformat()}, 400),
            ({"quantity": 0}, 400),
            ({"quantity": 1.5}, 400),
            ({"quantity": 3}, 409),
        ):
            with self.subTest(changes=changes):
                response = api.post(
                    reverse("api-rentals"), booking | changes, format="json"
                )
                self.assertEqual(response.status_code, expected)
        self.assertFalse(Rental.objects.exists())

    def test_rental_duration_limit_applies_to_availability_and_booking(self):
        api = APIClient()
        api.force_authenticate(self.customer)
        period = {
            "pickup_date": self.pickup.isoformat(),
            "return_date": (self.pickup + timedelta(days=31)).isoformat(),
        }
        self.assertEqual(
            api.get(reverse("api-equipment-list"), period).status_code, 400
        )
        booking = period | {"equipment_id": self.equipment.pk, "quantity": 1}
        self.assertEqual(
            api.post(reverse("api-rentals"), booking, format="json").status_code, 400
        )
        booking["return_date"] = (self.pickup + timedelta(days=30)).isoformat()
        self.assertEqual(
            api.post(reverse("api-rentals"), booking, format="json").status_code, 201
        )

    def test_retirement_blocks_new_bookings_but_allows_existing_handover_and_return(
        self,
    ):
        order = services.book_rental(
            self.customer, self.equipment.pk, self.today, self.dropoff, 1
        )
        services.update_equipment(
            self.staff, self.equipment.pk, "Camera", 300_000, 2, is_active=False
        )
        api = APIClient()
        api.force_authenticate(self.other)
        self.assertEqual(
            api.get(
                reverse("api-equipment-detail", args=[self.equipment.pk])
            ).status_code,
            404,
        )
        booking = {
            "equipment_id": self.equipment.pk,
            "quantity": 1,
            "pickup_date": self.today.isoformat(),
            "return_date": self.dropoff.isoformat(),
        }
        self.assertEqual(
            api.post(reverse("api-rentals"), booking, format="json").status_code, 409
        )
        api.force_authenticate(self.staff)
        self.assertEqual(
            api.post(reverse("api-pick-up", args=[order.pk])).json()["status"],
            "PICKED_UP",
        )
        self.assertEqual(
            api.post(reverse("api-return", args=[order.pk])).json()["status"],
            "RETURNED",
        )

    def test_no_show_releases_remaining_schedule_after_pickup_day(self):
        rental = Rental.objects.create(
            customer=self.customer,
            equipment=self.equipment,
            pickup_date=self.today - timedelta(days=1),
            return_date=self.dropoff,
            quantity=2,
            daily_rate_vnd=100,
            total_vnd=600,
        )
        self.assertEqual(
            services.available_stock(self.equipment, self.today, self.dropoff), 0
        )
        self.client.force_login(self.staff)
        result = self.client.post(reverse("no-show-rental", args=[rental.pk]))
        self.assertRedirects(result, reverse("staff-rental-detail", args=[rental.pk]))
        rental.refresh_from_db()
        self.assertEqual(rental.cancellation_reason, "NO_SHOW")
        self.assertEqual(
            services.available_stock(self.equipment, self.today, self.dropoff), 2
        )
        same_day = services.book_rental(
            self.other, self.equipment.pk, self.today, self.dropoff, 1
        )
        with self.assertRaises(services.RentalError):
            services.mark_no_show(self.staff, same_day.pk)

    def test_peak_stock_with_adjacent_rentals_and_staff_update(self):
        boundary = self.pickup + timedelta(days=1)
        first = services.book_rental(
            self.customer, self.equipment.pk, self.pickup, boundary, 1
        )
        services.book_rental(self.other, self.equipment.pk, boundary, self.dropoff, 1)
        self.assertEqual(
            services.available_stock(self.equipment, self.pickup, self.dropoff), 1
        )
        with self.assertRaises(services.RentalError) as failure:
            services.update_equipment(
                self.staff, self.equipment.pk, "Camera", 100_000, 0
            )
        self.assertEqual(failure.exception.status, 409)
        reduced = services.update_equipment(
            self.staff, self.equipment.pk, "Camera", 100_000, 1
        )
        self.assertEqual(
            services.available_stock(reduced, self.pickup, self.dropoff), 0
        )
        first.refresh_from_db()
        self.assertEqual(first.daily_rate_vnd, 300_000)

    def _create_unreturned_rental(self, *, days_past_due=1, quantity=1):
        now = timezone.now()
        dropoff = self.today - timedelta(days=days_past_due)
        return Rental.objects.create(
            customer=self.customer,
            equipment=self.equipment,
            pickup_date=dropoff - timedelta(days=1),
            return_date=dropoff,
            quantity=quantity,
            daily_rate_vnd=300_000,
            total_vnd=300_000 * quantity,
            status=Rental.Status.PICKED_UP,
            picked_up_at=now - timedelta(days=days_past_due + 1),
        )

    def test_pickup_then_early_return_share_web_api_and_keep_booking_window(self):
        rental = services.book_rental(
            self.customer, self.equipment.pk, self.today, self.dropoff, 2
        )
        pickup_url = reverse("pick-up-rental", args=[rental.pk])
        return_url = reverse("api-return", args=[rental.pk])
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(pickup_url).status_code, 403)
        api = APIClient()
        self.assertEqual(api.post(return_url).status_code, 401)
        api.force_authenticate(self.customer)
        self.assertEqual(api.post(return_url).status_code, 403)
        self.assertEqual(
            api.post(reverse("api-pick-up", args=[rental.pk])).status_code, 403
        )
        api.force_authenticate(self.staff)
        self.assertEqual(api.post(return_url).status_code, 409)
        self.client.force_login(self.staff)
        self.assertRedirects(
            self.client.post(pickup_url),
            reverse("staff-rental-detail", args=[rental.pk]),
        )
        self.assertEqual(self.client.post(pickup_url).status_code, 409)
        result = api.post(return_url).json()
        self.assertEqual(result["status"], "RETURNED")
        self.assertIsNotNone(result["picked_up_at"])
        self.assertIsNotNone(result["returned_at"])
        self.assertEqual(api.post(return_url).status_code, 409)
        self.assertEqual(
            services.available_stock(self.equipment, self.today, self.dropoff), 0
        )
        self.assertEqual(
            services.available_stock(
                self.equipment, self.dropoff, self.dropoff + timedelta(days=1)
            ),
            2,
        )

    def test_overdue_rental_blocks_handover_and_stock_reduction_until_returned(self):
        overdue = self._create_unreturned_rental(quantity=2)
        next_rental = services.book_rental(
            self.other, self.equipment.pk, self.today, self.dropoff, 2
        )
        pickup_url = reverse("api-pick-up", args=[next_rental.pk])
        api = APIClient()
        api.force_authenticate(self.customer)
        self.assertTrue(
            api.get(reverse("api-rental-detail", args=[overdue.pk])).json()[
                "is_overdue"
            ]
        )
        self.client.force_login(self.staff)
        self.assertContains(
            self.client.get(reverse("staff-rentals")), "Quá hạn trả thiết bị"
        )
        api.force_authenticate(self.staff)
        self.assertEqual(api.post(pickup_url).status_code, 409)
        next_rental.refresh_from_db()
        self.assertEqual(next_rental.status, Rental.Status.CONFIRMED)
        self.assertIsNone(next_rental.picked_up_at)
        result = api.post(reverse("api-return", args=[overdue.pk])).json()
        self.assertEqual(result["status"], "RETURNED")
        self.assertTrue(result["was_returned_late"])
        self.assertEqual(api.post(pickup_url).json()["status"], "PICKED_UP")

    def test_stock_cannot_be_reduced_below_outstanding_overdue_quantity(self):
        self._create_unreturned_rental(quantity=2)
        with self.assertRaises(services.RentalError):
            services.update_equipment(
                self.staff, self.equipment.pk, "Camera", 300_000, 1
            )
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.total_stock, 2)

    def test_only_staff_can_mark_no_show_at_end_of_pickup_window(self):
        due = Rental.objects.create(
            customer=self.customer,
            equipment=self.equipment,
            pickup_date=self.today - timedelta(days=1),
            return_date=self.today,
            quantity=1,
            daily_rate_vnd=300_000,
            total_vnd=300_000,
        )
        future = services.book_rental(
            self.other, self.equipment.pk, self.pickup, self.dropoff, 1
        )
        api = APIClient()
        api.force_authenticate(self.customer)
        no_show = reverse("api-no-show", args=[due.pk])
        self.assertEqual(api.post(no_show).status_code, 403)
        self.assertEqual(
            api.post(reverse("api-cancel", args=[due.pk])).status_code, 409
        )
        api.force_authenticate(self.staff)
        self.assertEqual(
            api.post(reverse("api-no-show", args=[future.pk])).status_code, 409
        )
        self.assertEqual(
            api.post(reverse("api-pick-up", args=[future.pk])).status_code, 409
        )
        self.assertEqual(
            api.post(reverse("api-pick-up", args=[due.pk])).status_code, 409
        )
        result = api.post(no_show).json()
        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(result["cancellation_reason"], "NO_SHOW")
        self.assertEqual(api.post(no_show).status_code, 409)
        self.assertEqual(
            api.post(reverse("api-return", args=[due.pk])).status_code, 409
        )
        due.refresh_from_db()
        self.assertIsNone(due.returned_at)


class ConcurrentBookingTests(TransactionTestCase):
    def _post_concurrently(self, requests):
        ready = Barrier(len(requests), timeout=10)

        def post(request):
            user, url, body = request
            api = APIClient()
            api.force_authenticate(user)
            try:
                ready.wait()
                return api.post(url, body, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(post, requests))

    @skipUnlessDBFeature("has_select_for_update")
    def test_two_postgres_connections_cannot_book_the_last_item_twice(self):
        self.assertEqual(connection.vendor, "postgresql")
        users = [
            get_user_model().objects.create_user(name) for name in ("first", "second")
        ]
        equipment = Equipment.objects.create(
            code="LAST", name="Last", daily_rate_vnd=100, total_stock=1
        )
        pickup = timezone.localdate() + timedelta(days=1)
        body = {
            "equipment_id": equipment.pk,
            "pickup_date": pickup.isoformat(),
            "return_date": (pickup + timedelta(days=1)).isoformat(),
            "quantity": 1,
        }
        self.assertCountEqual(
            self._post_concurrently(
                [(user, reverse("api-rentals"), body) for user in users]
            ),
            [201, 409],
        )
        self.assertEqual(Rental.objects.count(), 1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_handover_cannot_exceed_physical_stock(self):
        users = get_user_model().objects
        customer = users.create_user("customer")
        staff = users.create_user("staff", is_staff=True)
        equipment = Equipment.objects.create(
            code="LAST", name="Last", daily_rate_vnd=100, total_stock=2
        )
        today = timezone.localdate()
        Rental.objects.create(
            customer=customer,
            equipment=equipment,
            pickup_date=today - timedelta(days=2),
            return_date=today - timedelta(days=1),
            quantity=1,
            daily_rate_vnd=100,
            total_vnd=100,
            status=Rental.Status.PICKED_UP,
            picked_up_at=timezone.now() - timedelta(days=2),
        )
        rentals = [
            services.book_rental(
                customer, equipment.pk, today, today + timedelta(days=1), 1
            )
            for _ in range(2)
        ]
        requests = [
            (staff, reverse("api-pick-up", args=[rental.pk]), {}) for rental in rentals
        ]
        self.assertCountEqual(self._post_concurrently(requests), [200, 409])
        self.assertEqual(
            Rental.objects.filter(status=Rental.Status.PICKED_UP).count(), 2
        )
