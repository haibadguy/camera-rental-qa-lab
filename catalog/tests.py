from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
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

    def test_invalid_dates_keep_valid_catalog_filters_without_showing_stock(self):
        call_command("seed_catalog", stdout=StringIO())
        for dates in (
            {"pickup_date": "invalid-date", "return_date": timezone.localdate()},
            {"pickup_date": timezone.localdate()},
        ):
            with self.subTest(dates=dates):
                response = self.client.get(
                    reverse("equipment-list"),
                    {"search": "LEN-001", "kind": "LENS"} | dates,
                )
                self.assertContains(response, "Sigma 30mm")
                self.assertNotContains(response, "Sony A6400")
                self.assertNotContains(response, "Còn theo lịch:")
                self.assertTrue(response.context["form"].errors)

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
    def test_registration_returns_customer_to_booking_with_selected_dates(self):
        equipment = Equipment.objects.create(
            code="LENS", name="Lens", daily_rate_vnd=150_000, total_stock=1
        )
        pickup = timezone.localdate()
        period = {
            "pickup_date": pickup.isoformat(),
            "return_date": (pickup + timedelta(days=2)).isoformat(),
        }
        booking = reverse("book", args=[equipment.pk], query=period)
        login = reverse("login", query={"next": booking})
        register = reverse("register", query={"next": booking})
        self.assertRedirects(self.client.get(booking), login)
        self.assertContains(self.client.get(login), f'href="{register}"', count=2)

        password = "V7!kQ3@z"
        data = {"username": "new-renter", "password1": password, "password2": password}
        self.assertEqual(
            self.client.post(register, data | {"password2": "different"}).status_code,
            400,
        )
        self.assertRedirects(self.client.post(register, data), login)
        self.assertRedirects(
            self.client.post(login, {"username": "new-renter", "password": password}),
            booking,
        )
        form = self.client.get(booking).context["form"]
        for field, value in period.items():
            self.assertEqual(form[field].value(), value)
        self.assertFalse(Rental.objects.exists())

    def test_registration_ignores_external_redirect_target(self):
        register = reverse("register", query={"next": "//example.org/booking"})
        password = "M1-Client-Forest-47"
        self.assertRedirects(
            self.client.post(
                register,
                {
                    "username": "local-renter",
                    "password1": password,
                    "password2": password,
                },
            ),
            reverse("login"),
        )

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

    def test_password_validation_displays_vietnamese_minimum_length_error(self):
        for password, expected_codes in (
            ("V7!kQ3@", ["password_too_short"]),
            (
                "123",
                ["password_too_short", "password_too_common", "password_entirely_numeric"],
            ),
        ):
            with self.subTest(password=password):
                response = self.client.post(
                    reverse("register"),
                    {
                        "username": "new-customer",
                        "password1": password,
                        "password2": password,
                    },
                )
                self.assertEqual(response.status_code, 400)
                errors = response.context["form"].errors.as_data()["password2"]
                self.assertEqual([error.code for error in errors], expected_codes)
                self.assertEqual(
                    errors[0].message, "Mật khẩu của bạn phải chứa ít nhất 8 ký tự."
                )
                self.assertNotContains(
                    response, "This password is too short.", status_code=400
                )
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
        self.assertContains(available, "Thuê từ 1 đến 30 ngày.")
        self.assertContains(
            available, f'{booking}?pickup_date={self.pickup}&amp;return_date={self.dropoff}'
        )
        self.client.force_login(self.customer)
        booking_page = self.client.get(booking, period | {"quantity": 2})
        self.assertContains(booking_page, 'data-max-rental-days="30"')
        form = booking_page.context["form"]
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

    def test_catalog_offers_booking_only_for_available_periods(self):
        catalog = reverse("equipment-list")
        booking = reverse("book", args=[self.equipment.pk])
        period = {"pickup_date": self.pickup, "return_date": self.dropoff}
        filters = {"kind": self.equipment.kind, "search": self.equipment.code}

        self.assertNotContains(self.client.get(catalog, filters), booking)
        available = self.client.get(catalog, filters | period)
        self.assertContains(
            available,
            f'{booking}?pickup_date={self.pickup}&amp;return_date={self.dropoff}',
        )
        self.assertContains(available, "Còn theo lịch: 2")

        services.book_rental(self.other, self.equipment.pk, self.pickup, self.dropoff, 2)
        sold_out = self.client.get(catalog, filters | period)
        self.assertContains(sold_out, "Còn theo lịch: 0")
        self.assertNotContains(sold_out, booking)

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

    def test_handoff_information_is_shown_before_booking_and_on_active_orders(self):
        detail = reverse("equipment-detail", args=[self.equipment.pk])
        booking = reverse("book", args=[self.equipment.pk])
        with self.settings(RENTAL_STORE={}):
            self.assertContains(self.client.get(detail), "chưa được công bố")
        self.client.force_login(self.customer)
        rental = services.book_rental(
            self.customer, self.equipment.pk, self.pickup, self.dropoff, 1
        )
        order = reverse("rental-detail", args=[rental.pk])
        store = {
            "name": "Cửa hàng kiểm thử",
            "address": "Địa chỉ dùng trong test",
            "hours": "09:00–18:00",
            "phone": "0900 000 000",
            "phone_dial": "0900000000",
            "support_url": "https://example.com/support",
            "notes": "Thông tin giao nhận dùng trong test",
        }
        with self.settings(RENTAL_STORE=store):
            for path in (detail, booking, order):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertContains(response, store["address"])
                    self.assertContains(response, store["notes"])
                    self.assertContains(response, 'href="tel:0900000000"')
                    self.assertNotContains(response, "chưa được công bố")
            services.cancel_rental(self.customer, rental.pk)
            self.assertNotContains(self.client.get(order), store["address"])

    def test_web_booking_conflict_keeps_dates_quantity_and_existing_stock(self):
        existing = services.book_rental(
            self.other, self.equipment.pk, self.pickup, self.dropoff, 1
        )
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("book", args=[self.equipment.pk]),
            {
                "pickup_date": self.pickup.isoformat(),
                "return_date": self.dropoff.isoformat(),
                "quantity": "2",
            },
        )
        self.assertContains(
            response, "Không đủ thiết bị cho kỳ thuê đã chọn.", status_code=409
        )
        form = response.context["form"]
        self.assertEqual(form["pickup_date"].value(), self.pickup.isoformat())
        self.assertEqual(form["return_date"].value(), self.dropoff.isoformat())
        self.assertEqual(form["quantity"].value(), "2")
        self.assertEqual(Rental.objects.get().pk, existing.pk)
        self.assertEqual(
            services.available_stock(self.equipment, self.pickup, self.dropoff), 1
        )

    def test_web_and_api_keep_other_customers_orders_private(self):
        owned = services.book_rental(
            self.customer, self.equipment.pk, self.pickup, self.dropoff, 1
        )
        private = services.book_rental(
            self.other, self.equipment.pk, self.pickup, self.dropoff, 1
        )
        self.client.force_login(self.customer)
        self.assertQuerySetEqual(
            self.client.get(reverse("my-rentals")).context["rentals"], [owned]
        )
        self.assertEqual(
            self.client.get(reverse("rental-detail", args=[private.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("cancel-rental", args=[private.pk])).status_code,
            404,
        )
        api = APIClient()
        api.force_authenticate(self.customer)
        response = api.get(reverse("api-rentals"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([rental["id"] for rental in response.json()], [owned.pk])
        self.assertEqual(
            api.get(reverse("api-rental-detail", args=[private.pk])).status_code, 404
        )
        private.refresh_from_db()
        self.assertEqual(private.status, Rental.Status.CONFIRMED)

    def test_stock_edit_conflict_does_not_apply_any_fields(self):
        booked = services.book_rental(
            self.customer, self.equipment.pk, self.pickup, self.dropoff, 2
        )
        edit = reverse("edit-equipment", args=[self.equipment.pk])
        change = {
            "code": "CHANGED",
            "name": "New name",
            "kind": "LENS",
            "specifications": "New specs",
            "daily_rate_vnd": 100_000,
            "total_stock": 1,
        }
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(edit, change).status_code, 403)
        self.client.force_login(self.staff)
        response = self.client.post(edit, change)
        self.assertContains(
            response,
            "Tổng tồn mới thấp hơn số lượng đã giữ hoặc đang được thuê.",
            status_code=409,
        )
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.code, "CAM-900")
        self.assertEqual(self.equipment.name, "Camera")
        self.assertEqual(self.equipment.kind, Equipment.Kind.CAMERA)
        self.assertEqual(self.equipment.specifications, "")
        self.assertEqual(self.equipment.daily_rate_vnd, 300_000)
        self.assertEqual(self.equipment.total_stock, 2)
        self.assertTrue(self.equipment.is_active)
        booked.refresh_from_db()
        self.assertEqual(booked.status, Rental.Status.CONFIRMED)
        self.assertEqual(booked.total_vnd, 1_200_000)

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
        stock_page = self.client.get(reverse("staff-equipment"))
        stock = stock_page.context["equipment"].get(pk=self.equipment.pk)
        self.assertEqual((stock.outstanding, stock.available_now), (2, 0))
        api.force_authenticate(self.staff)
        self.assertEqual(api.post(pickup_url).status_code, 409)
        next_rental.refresh_from_db()
        self.assertEqual(next_rental.status, Rental.Status.CONFIRMED)
        self.assertIsNone(next_rental.picked_up_at)
        result = api.post(reverse("api-return", args=[overdue.pk])).json()
        self.assertEqual(result["status"], "RETURNED")
        self.assertTrue(result["was_returned_late"])
        stock_page = self.client.get(reverse("staff-equipment"))
        stock = stock_page.context["equipment"].get(pk=self.equipment.pk)
        self.assertEqual((stock.outstanding, stock.available_now), (0, 2))
        self.assertEqual(api.post(pickup_url).json()["status"], "PICKED_UP")

    def test_stock_cannot_be_reduced_below_outstanding_overdue_quantity(self):
        self._create_unreturned_rental(quantity=2)
        with self.assertRaises(services.RentalError):
            services.update_equipment(
                self.staff, self.equipment.pk, "Camera", 300_000, 1
            )
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.total_stock, 2)

    def test_staff_queues_separate_pickups_due_returns_and_overdue_orders(self):
        pickup = services.book_rental(
            self.customer, self.equipment.pk, self.today, self.dropoff, 1
        )
        due = self._create_unreturned_rental(days_past_due=0)
        overdue = self._create_unreturned_rental(days_past_due=1)
        orders = reverse("staff-rentals")

        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(orders, {"queue": "overdue"}).status_code, 403)
        self.client.force_login(self.staff)
        for queue, rental in (
            ("pickup-today", pickup),
            ("return-today", due),
            ("overdue", overdue),
        ):
            with self.subTest(queue=queue):
                response = self.client.get(orders, {"queue": queue})
                self.assertQuerySetEqual(response.context["rentals"], [rental])
                self.assertEqual(response.context["active_queue"], queue)

        services.return_rental(self.staff, due.pk)
        self.assertContains(
            self.client.get(orders, {"queue": "return-today"}),
            "Không có đơn trong mục này.",
        )

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


class LegacyRentalMigrationTests(TransactionTestCase):
    def test_upgrade_from_0002_preserves_rental_history(self):
        old_schema = [("catalog", "0002_rental")]
        upgraded_schema = [("catalog", "0004_equipment_catalog")]
        executor = MigrationExecutor(connection)
        current_schema = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old_schema)
            models_before = executor.loader.project_state(old_schema).apps
            user = models_before.get_model("auth", "User").objects.create(
                username="legacy-customer"
            )
            legacy_equipment = models_before.get_model("catalog", "Equipment")
            equipment = legacy_equipment.objects.create(
                code="LEN-LEGACY",
                name="Legacy lens",
                daily_rate_vnd=200_000,
                total_stock=2,
            )
            rentals_before = models_before.get_model("catalog", "Rental").objects
            pickup = timezone.localdate() - timedelta(days=4)
            returned_at = timezone.now() - timedelta(days=2)
            for status in ("CONFIRMED", "CANCELLED", "RETURNED"):
                rentals_before.create(
                    customer_id=user.pk,
                    equipment_id=equipment.pk,
                    pickup_date=pickup,
                    return_date=pickup + timedelta(days=2),
                    quantity=2,
                    daily_rate_vnd=150_000,
                    total_vnd=600_000,
                    status=status,
                    returned_at=returned_at if status == "RETURNED" else None,
                )
            historical_fields = (
                "id",
                "equipment_id",
                "customer_id",
                "pickup_date",
                "return_date",
                "quantity",
                "daily_rate_vnd",
                "total_vnd",
                "status",
                "returned_at",
            )
            history = list(rentals_before.order_by("pk").values_list(*historical_fields))

            executor = MigrationExecutor(connection)
            executor.migrate(upgraded_schema)
            models_after = executor.loader.project_state(upgraded_schema).apps
            rentals_after = models_after.get_model("catalog", "Rental").objects
            self.assertEqual(
                list(rentals_after.order_by("pk").values_list(*historical_fields)),
                history,
            )
            self.assertEqual(
                list(
                    rentals_after.order_by("pk").values_list(
                        "picked_up_at", "cancellation_reason"
                    )
                ),
                [(None, "")] * len(history),
            )
            lens = models_after.get_model("catalog", "Equipment").objects.get(
                pk=equipment.pk
            )
            self.assertEqual(lens.kind, "LENS")
            self.assertTrue(lens.is_active)
        finally:
            MigrationExecutor(connection).migrate(current_schema)
