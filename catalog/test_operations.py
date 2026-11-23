from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import AssetUnit, Equipment, Rental
from .roles import MANAGER_GROUP, OPERATOR_GROUP


class OperationsAdapterTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.customer = users.create_user("operations-customer")
        self.stranger = users.create_user("operations-stranger")
        self.staff = users.create_user("operations-staff", is_staff=True)
        self.operator = users.create_user("operations-operator", is_staff=True)
        self.operator.groups.add(Group.objects.get(name=OPERATOR_GROUP))
        self.manager = users.create_user("operations-manager", is_staff=True)
        self.manager.groups.add(Group.objects.get(name=MANAGER_GROUP))
        self.item = Equipment.objects.create(
            code="OPS",
            name="Máy vận hành",
            daily_rate_vnd=100_000,
            total_stock=2,
            accessory_checklist="Pin và sạc",
        )
        for code in ("OPS-1", "OPS-2"):
            services.register_asset(self.staff, self.item.pk, code)
        self.item = services.enable_asset_tracking(self.staff, self.item.pk)
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.api = APIClient()

    def test_custody_requires_role_and_records_partial_return_for_owner(self):
        order = services.book_rental(
            self.customer, self.item.pk, self.today, self.tomorrow, 2
        )
        order_id = order.pk
        staff_url = reverse("operations-order", args=[order_id])
        api_url = reverse("api-operations-order", args=[order_id])
        customer_url = reverse("rental-detail", args=[order_id])
        changes_url = reverse("api-rental-changes", args=[order_id])
        for account in (self.stranger, self.staff):
            self.client.force_login(account)
            self.api.force_authenticate(account)
            self.assertEqual(self.client.get(staff_url).status_code, 403)
            self.assertEqual(self.api.get(api_url).status_code, 403)
            self.assertEqual(self.client.get(customer_url).status_code, 404)
            self.assertEqual(self.api.get(changes_url).status_code, 404)

        self.client.force_login(self.operator)
        self.api.force_authenticate(self.operator)
        self.assertEqual(
            self.api.post(reverse("api-pick-up", args=[order_id])).status_code, 409
        )
        holds = self.api.get(api_url).data["reservations"]
        self.assertEqual(len(holds), 2)
        for hold in holds:
            response = self.client.post(
                staff_url, {"action": "prepare", "item_id": hold["id"]}
            )
            self.assertRedirects(response, staff_url)
        pickup_url = reverse("api-operations-pick-up", args=[order_id])
        self.assertEqual(
            self.api.post(pickup_url).data["status"], Rental.Status.PICKED_UP
        )
        self.assertEqual(self.api.post(pickup_url).status_code, 409)
        self.assertEqual(
            self.api.post(reverse("api-return", args=[order_id])).status_code, 409
        )
        first, second = self.api.get(api_url).data["handovers"]
        self.assertEqual(first["expected_accessories"], "Pin và sạc")

        receive_url = reverse("api-receive-asset", args=[order_id, first["id"]])
        self.assertEqual(self.api.post(receive_url).status_code, 204)
        self.assertEqual(self.api.post(receive_url).status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, Rental.Status.PICKED_UP)
        self.assertEqual(services.checked_out_quantity(self.item), 1)
        self.assertEqual(
            AssetUnit.objects.get(pk=first["asset_id"]).status,
            AssetUnit.Status.INSPECTION,
        )

        self.client.force_login(self.customer)
        response = self.client.get(customer_url)
        self.assertContains(response, "1/2 thiết bị")
        self.assertNotContains(response, first["asset_code"])
        self.assertNotContains(response, "Yêu cầu gia hạn")
        customer_api = APIClient()
        customer_api.force_authenticate(self.customer)
        detail = customer_api.get(reverse("api-order-detail", args=[order_id])).data
        self.assertEqual(detail["receipt"], {"picked_up": 2, "returned": 1, "lost": 0})
        inspect_url = reverse("api-inspect-asset", args=[order_id, first["id"]])
        self.assertEqual(
            self.api.post(inspect_url, {"result": "READY"}).status_code, 204
        )

        self.client.force_login(self.operator)
        response = self.client.post(
            staff_url, {"action": "receive", "item_id": second["id"]}
        )
        self.assertRedirects(response, staff_url)
        order.refresh_from_db()
        self.assertEqual(order.status, Rental.Status.RETURNED)
        self.assertIsNotNone(order.returned_at)
        self.assertEqual(
            services.available_stock(self.item, self.today, self.tomorrow), 0
        )

    def test_maintenance_renders_calendar_and_reserves_resolution_for_manager(self):
        asset = self.item.assets.first()
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("maintenance-plan"),
            {
                "asset": asset.pk,
                "pickup_date": self.today,
                "return_date": self.tomorrow,
                "notes": "Kiểm tra nguồn.",
            },
        )
        self.assertEqual(response.status_code, 302)
        case = asset.maintenance_cases.get()
        detail_url = reverse("maintenance-detail", args=[case.pk])
        self.assertRedirects(response, detail_url)
        calendar = self.client.get(reverse("staff-assets", args=[self.item.pk]))
        self.assertContains(calendar, f"Bảo trì #{case.pk}")
        self.assertContains(calendar, detail_url)
        self.assertEqual(
            services.available_stock(self.item, self.today, self.tomorrow), 1
        )

        payload = {"resolution": "READY", "notes": "Đã kiểm tra nguồn."}
        self.assertEqual(
            self.client.post(detail_url, payload | {"action": "resolve"}).status_code,
            403,
        )
        resolve_url = reverse("api-maintenance-resolve", args=[case.pk])
        self.api.force_authenticate(self.operator)
        self.assertEqual(self.api.post(resolve_url, payload).status_code, 403)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.post(resolve_url, payload).data["state"], "RESOLVED")
        self.assertEqual(
            services.available_stock(self.item, self.today, self.tomorrow), 2
        )
