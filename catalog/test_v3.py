from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from . import services
from .models import AssetHandover, AssetUnit, CashShift, Equipment, FinanceEntry, MaintenanceCase
from .roles import COUNTER_BOOKER_GROUP, FINANCE_CLERK_GROUP, FINANCE_MANAGER_GROUP, OPERATOR_GROUP, REPORTING_MANAGER_GROUP
from .test_finance import staff_with_groups


def make_stock(code):
    item = Equipment.objects.create(
        code=code, name=code, total_stock=1, daily_rate_vnd=100_000, tracks_assets=True
    )
    AssetUnit.objects.create(equipment=item, code=f"{code}-01", reporting_since=timezone.now())
    return item


class CounterTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user("counter-customer")
        self.operator = staff_with_groups("operator", OPERATOR_GROUP, FINANCE_CLERK_GROUP)
        self.booker = staff_with_groups("booker", OPERATOR_GROUP, COUNTER_BOOKER_GROUP)
        self.body = {
            "command_id": str(uuid4()), "username": self.customer.username,
            "pickup_date": timezone.localdate(), "return_date": timezone.localdate() + timedelta(days=1),
            "lines": [{"equipment_id": make_stock(code).pk, "quantity": 1} for code in ("CAM", "LENS")],
        }

    def test_booker_permissions_idempotency_and_visibility(self):
        api = APIClient()
        path = reverse("api-counter-orders")
        api.force_authenticate(self.operator)
        self.assertEqual(api.post(path, self.body, format="json").status_code, 403)
        api.force_authenticate(self.booker)
        first = api.post(path, self.body, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        second = api.post(path, self.body, format="json")
        self.assertEqual(first.data, second.data)
        changed = self.body | {"username": "different"}
        self.assertEqual(api.post(path, changed, format="json").status_code, 409)
        self.assertEqual(self.customer.rental_set.count(), 1)
        rental = self.customer.rental_set.get()
        self.assertEqual(rental.counter_commands.get().actor, self.booker)
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse("rental-detail", args=[rental.pk])), "CAM")
        self.assertEqual(self.client.get(reverse("counter-book-order")).status_code, 403)

    def test_scan_rolls_back_all_and_receives_part_of_order(self):
        rental = services.book_for_customer(self.booker, **self.body)
        request = uuid4()
        with self.assertRaisesRegex(services.RentalError, "không thuộc"):
            services.scan_assets(self.operator, rental.pk, "PREPARE", ["CAM-01", "WRONG"], request)
        self.assertFalse(AssetHandover.objects.exists())
        self.assertEqual(rental.counter_commands.count(), 1)
        first = services.scan_assets(self.operator, rental.pk, "PREPARE", ["CAM-01", "LENS-01"], request)
        second = services.scan_assets(self.operator, rental.pk, "PREPARE", ["LENS-01", "CAM-01"], request)
        self.assertEqual(first.pk, second.pk)
        services.post_finance_entry(
            self.operator, rental.pk, kind="RENT_RECEIPT", method="CASH",
            amount_vnd=200_000, command_id=uuid4(),
        )
        services.pick_up_rental(self.operator, rental.pk)
        services.scan_assets(self.operator, rental.pk, "RECEIVE", ["CAM-01"], uuid4())
        rental.refresh_from_db()
        self.assertEqual(rental.status, rental.Status.PICKED_UP)
        self.assertEqual(services.receipt_summary(rental)["returned"], 1)
        self.assertEqual(AssetUnit.objects.get(code="CAM-01").status, "INSPECTION")

    def test_cart_preserves_two_skus_across_search(self):
        self.client.force_login(self.customer)
        url = reverse("book-order")
        first, second = self.body["lines"]
        dates = {key: str(self.body[key]) for key in ("pickup_date", "return_date")}
        quantity_first = f"quantity_{first['equipment_id']}"
        quantity_second = f"quantity_{second['equipment_id']}"
        response = self.client.post(url, dates | {"search": "LENS", "browse": 1, quantity_first: 1}, follow=True)
        self.assertContains(response, f'name="{quantity_first}"')
        self.assertContains(response, f'name="{quantity_second}"')
        self.assertEqual(self.client.post(url, dates | {quantity_first: 1, quantity_second: 1}).status_code, 302)
        self.assertEqual(self.customer.rental_set.get().lines.count(), 2)


class PhotoTests(TestCase):
    def test_photo_is_private_validated_retryable_and_purged(self):
        operator = staff_with_groups("photo-operator", OPERATOR_GROUP)
        customer = get_user_model().objects.create_user("photo-customer")
        item = make_stock("PHOTO")
        asset = item.assets.get()
        case = services.report_incident(operator, asset.pk, MaintenanceCase.Kind.DAMAGE, "Lens mount")
        output = BytesIO()
        Image.new("RGB", (32, 24), "orange").save(output, "JPEG")
        command = uuid4()
        with TemporaryDirectory() as directory, override_settings(INCIDENT_MEDIA_ROOT=directory):
            with self.assertRaises(services.RentalError):
                services.attach_photo(operator, case.pk, uuid4(), SimpleUploadedFile("fake.jpg", b"data"))
            content = output.getvalue()
            self.client.force_login(operator)
            upload_url = reverse("maintenance-detail", args=[case.pk])
            uploaded = self.client.post(upload_url, {
                "action": "photo", "command_id": command,
                "upload": SimpleUploadedFile("real.jpg", content, content_type="image/jpeg"),
            })
            self.assertRedirects(uploaded, upload_url)
            first = case.photos.get()
            second = services.attach_photo(operator, case.pk, command, SimpleUploadedFile("real.jpg", content))
            self.assertEqual(first.pk, second.pk)
            url = reverse("incident-photo", args=[case.pk, first.pk])
            self.client.force_login(customer)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(operator)
            response = self.client.get(url)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertTrue(b"".join(response.streaming_content).startswith(b"\xff\xd8"))
            case.photos.update(expires_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(self.client.get(url).status_code, 404)
            call_command("purge_incident_photos", stdout=StringIO())
            first.refresh_from_db()
            self.assertIsNotNone(first.deleted_at)


@override_settings(CASH_SHIFT_REQUIRED=True)
class ShiftTests(TestCase):
    def test_reversal_later_ca_and_report_snapshot_preserve_ledger(self):
        clerk = staff_with_groups("shift-clerk", FINANCE_CLERK_GROUP)
        manager = staff_with_groups("shift-manager", FINANCE_MANAGER_GROUP, REPORTING_MANAGER_GROUP)
        customer = get_user_model().objects.create_user("shift-customer")
        today = timezone.localdate()
        rental = services.book_rental(customer, make_stock("SHIFT").pk, today, today + timedelta(days=1), 1)
        inputs = {
            "kind": "RENT_RECEIPT", "command_id": uuid4(), "amount_vnd": 100_000, "method": "TRANSFER",
        }
        with self.assertRaisesRegex(services.RentalError, "mở ca"):
            services.post_finance_entry(clerk, rental.pk, **inputs)
        shift = services.open_shift(clerk, 50_000)
        with self.assertRaisesRegex(services.RentalError, "Đã có ca"):
            services.open_shift(clerk, 0)
        entry = services.post_finance_entry(clerk, rental.pk, **inputs)
        with self.assertRaisesRegex(services.RentalError, "Nhập lý do"):
            services.submit_shift(clerk, shift.pk, 50_000, 99_999)
        submitted = services.submit_shift(clerk, shift.pk, 50_000, 99_999, "Thiếu 1 đồng")
        self.assertEqual(submitted.transfer_difference_vnd, -1)
        self.assertEqual(submitted.expected_transfer_vnd, 100_000)
        self.assertEqual(services.post_finance_entry(clerk, rental.pk, **inputs).pk, entry.pk)
        new_shift = services.open_shift(clerk, 50_000)
        with self.assertRaises(services.RentalError):
            services.close_shift(clerk, shift.pk, "Đối chiếu với ngân hàng")
        services.close_shift(manager, shift.pk, "Đối chiếu với ngân hàng")
        reversal = services.post_finance_entry(
            manager, rental.pk, kind="REVERSAL", command_id=uuid4(), notes="Ghi nhầm",
            entry_id=entry.pk,
        )
        self.assertEqual(reversal.shift_id, new_shift.pk)
        _, totals = services.cash_shift_detail(manager, new_shift.pk)
        self.assertEqual(totals, {"cash": 50_000, "transfer": -100_000})
        self.assertEqual(services.rental_report(manager, today, today, summary=True)["money"]["balance_due_vnd"], 100_000)
        call_command("rebuild_finance_snapshots", "--verify", stdout=StringIO())
        self.client.force_login(manager)
        self.assertContains(self.client.get(reverse("cash-shift-detail", args=[shift.pk])), "Thiếu 1 đồng")


@override_settings(CASH_SHIFT_REQUIRED=True)
class ShiftConcurrencyTests(TransactionTestCase):
    def test_posting_race_with_submit_has_one_ledger_result(self):
        actor = staff_with_groups("race-clerk", FINANCE_CLERK_GROUP)
        customer = get_user_model().objects.create_user("race-customer")
        today = timezone.localdate()
        rental = services.book_rental(customer, make_stock("RACE").pk, today, today + timedelta(days=1), 1)
        shift = services.open_shift(actor, 0)
        barrier = Barrier(2, timeout=10)

        def run(function):
            try:
                barrier.wait()
                return function()
            finally:
                connections.close_all()

        def post():
            try:
                services.post_finance_entry(
                    actor, rental.pk, kind="RENT_RECEIPT", method="CASH",
                    command_id=uuid4(), amount_vnd=100_000,
                )
            except services.RentalError as error:
                return error.status
            return 201

        def submit():
            return services.submit_shift(actor, shift.pk, 0, 0, "Kiểm tra chênh lệch")

        with ThreadPoolExecutor(max_workers=2) as workers:
            received = workers.submit(run, post)
            submitted = workers.submit(run, submit)
            status, closed = received.result(timeout=15), submitted.result(timeout=15)

        self.assertEqual(closed.status, CashShift.Status.SUBMITTED)
        self.assertIn(status, (201, 409))
        self.assertEqual(FinanceEntry.objects.filter(shift=shift).count(), int(status == 201))
        self.assertEqual(closed.expected_cash_vnd, 100_000 if status == 201 else 0)


class PaginationTests(TestCase):
    def test_catalog_filters_pagination_and_legacy_shape(self):
        for index in range(26):
            make_stock(f"SKU-{index:02}")
        api = APIClient()
        path = reverse("api-catalog-v3")
        date = timezone.localdate()
        result = api.get(path, {"pickup_date": date, "return_date": date + timedelta(days=1)})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(len(result.data["results"]), 24)
        self.assertEqual(result.data["count"], 26)
        self.assertEqual(result.data["results"][0]["available_stock"], 1)
        self.assertEqual(len(api.get(path, {"page": 2}).data["results"]), 2)
        self.assertEqual(len(api.get(reverse("api-equipment-list")).data), 26)
