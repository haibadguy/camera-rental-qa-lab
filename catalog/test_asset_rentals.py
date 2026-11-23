from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import (
    AssetHandover,
    AssetReservation,
    AssetUnit,
    Equipment,
    Rental,
    RentalLine,
)
from .roles import OPERATOR_GROUP
from .test_finance import fund_rental


class AssetRentalTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.customer = users.create_user("asset-customer")
        self.staff = users.create_user("asset-staff", is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.camera = self.make_equipment("CAM", 120_000, 2)
        self.lens = self.make_equipment("LEN", 80_000, 1)
        self.pickup = timezone.localdate() + timedelta(days=2)
        self.dropoff = self.pickup + timedelta(days=2)

    def make_equipment(self, sku, rate, quantity):
        equipment = Equipment.objects.create(
            code=sku, name=sku, daily_rate_vnd=rate, total_stock=quantity
        )
        for index in range(quantity):
            services.register_asset(self.staff, equipment.pk, f"{sku}-{index}")
        return services.enable_asset_tracking(self.staff, equipment.pk)

    def payload(self, *lines):
        return {
            "pickup_date": self.pickup.isoformat(),
            "return_date": self.dropoff.isoformat(),
            "lines": [
                {"equipment_id": item.pk, "quantity": quantity}
                for item, quantity in lines
            ],
        }

    def book(self, *lines):
        return self.api.post(reverse("api-orders"), self.payload(*lines), format="json")

    def test_multi_line_snapshot_ownership_legacy_projection_and_cancellation(self):
        response = self.book((self.camera, 2), (self.lens, 1))
        self.assertEqual(response.status_code, 201, response.data)
        rental_id = response.data["id"]
        self.assertEqual(response.data["total_vnd"], "640000")
        self.assertEqual(
            AssetReservation.objects.filter(line__rental_id=rental_id).count(), 3
        )
        Equipment.objects.filter(pk=self.camera.pk).update(daily_rate_vnd=1)
        self.assertEqual(
            self.api.get(reverse("api-order-detail", args=[rental_id])).data["lines"][
                0
            ]["daily_rate_vnd"],
            120_000,
        )
        self.assertEqual(self.api.get(reverse("api-rentals")).data, [])
        self.assertEqual(
            self.api.post(reverse("api-cancel", args=[rental_id])).status_code, 404
        )
        self.api.force_authenticate(get_user_model().objects.create_user("stranger"))
        url = reverse("api-cancel-order", args=[rental_id])
        self.assertEqual(self.api.post(url).status_code, 404)
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(url).status_code, 200)
        self.assertEqual(self.api.post(url).status_code, 409)
        self.assertEqual(
            AssetReservation.objects.filter(released_at__isnull=False).count(), 3
        )
        self.assertEqual(self.book((self.camera, 2), (self.lens, 1)).status_code, 201)

    def test_shortage_duplicate_sku_and_v1_payload_leave_no_partial_state(self):
        self.assertEqual(self.book((self.camera, 1), (self.lens, 2)).status_code, 409)
        self.assertEqual(self.book((self.camera, 1), (self.camera, 1)).status_code, 400)
        payload = self.payload((self.camera, 1), (self.lens, 1))
        payload.update(equipment_id=self.camera.pk, quantity=1)
        self.assertEqual(
            self.api.post(reverse("api-rentals"), payload, format="json").status_code,
            400,
        )
        self.assertEqual(Rental.objects.count(), 0)
        self.assertEqual(RentalLine.objects.count(), 0)
        self.assertEqual(AssetReservation.objects.count(), 0)

    def test_web_booking_calendar_and_staff_swap_preserve_history(self):
        self.client.force_login(self.customer)
        form = {
            "pickup_date": self.pickup.isoformat(),
            "return_date": self.dropoff.isoformat(),
            f"quantity_{self.camera.pk}": 1,
            f"quantity_{self.lens.pk}": 1,
        }
        self.assertEqual(
            self.client.post(
                reverse("book-order"), form | {"quantity_9999": 1}
            ).status_code,
            400,
        )
        self.assertFalse(Rental.objects.exists())
        response = self.client.post(reverse("book-order"), form, follow=True)
        self.assertContains(response, "400.000 ₫")
        self.assertNotContains(response, "CAM-0")
        hold = AssetReservation.objects.get(asset__equipment=self.camera)
        staff_url = reverse("replace-asset", args=[hold.line.rental_id, hold.pk])
        self.assertEqual(
            self.client.post(staff_url, {"replacement_code": "CAM-1"}).status_code, 403
        )
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(staff_url, {"replacement_code": "LEN-0"}).status_code, 409
        )
        hold.refresh_from_db()
        self.assertIsNone(hold.released_at)
        response = self.client.post(
            staff_url, {"replacement_code": "CAM-1"}, follow=True
        )
        self.assertContains(response, "Đổi từ CAM-0")
        hold.refresh_from_db()
        self.assertIsNotNone(hold.released_at)
        self.assertEqual(hold.replacement.asset.code, "CAM-1")
        self.assertEqual(hold.replacement.changed_by, self.staff)
        self.assertEqual(hold.replacement.period, hold.period)
        self.assertEqual(
            self.client.post(staff_url, {"replacement_code": "CAM-0"}).status_code, 409
        )
        calendar = self.client.get(reverse("staff-assets", args=[self.camera.pk]))
        for text in ("CAM-0", "CAM-1", "Đã giải phóng"):
            self.assertContains(calendar, text)

    def test_range_exclusion_and_full_period_availability(self):
        middle = self.pickup + timedelta(days=1)
        order = services.book_rental(
            self.customer, self.camera.pk, self.pickup, middle, 1
        )
        reservation = AssetReservation.objects.get(line__rental=order)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetReservation.objects.create(
                line=reservation.line,
                asset=reservation.asset,
                period=(self.pickup, self.dropoff),
            )
        adjacent = services.book_rental(
            self.customer, self.camera.pk, middle, self.dropoff, 1
        )
        second = AssetReservation.objects.get(line__rental=adjacent)
        self.assertEqual(second.asset, reservation.asset)
        services.replace_reserved_asset(self.staff, adjacent.pk, second.pk, "CAM-1")
        self.assertEqual(services.available_stock(self.camera, self.pickup, middle), 1)
        self.assertEqual(services.available_stock(self.camera, middle, self.dropoff), 1)
        self.assertEqual(
            services.available_stock(self.camera, self.pickup, self.dropoff), 0
        )

    def test_legacy_activation_reports_unassigned_orders_and_keeps_writes_safe(self):
        legacy = Equipment.objects.create(
            code="OLD", name="Old", daily_rate_vnd=200, total_stock=1
        )
        services.register_asset(self.staff, legacy.pk, "OLD-1")
        self.assertEqual(self.book((legacy, 1), (self.lens, 1)).status_code, 409)
        order = services.book_rental(
            self.customer, legacy.pk, self.pickup, self.dropoff, 1
        )
        self.client.force_login(self.staff)
        url = reverse("staff-assets", args=[legacy.pk])
        response = self.client.post(url, {"action": "enable"})
        self.assertContains(response, f"Đơn #{order.pk}", status_code=409)
        self.assertFalse(AssetReservation.objects.exists())
        legacy.refresh_from_db()
        self.assertFalse(legacy.tracks_assets)
        services.cancel_rental(self.customer, order.pk)
        self.assertEqual(self.client.post(url, {"action": "enable"}).status_code, 302)
        order = services.book_rental(
            self.customer, legacy.pk, self.pickup, self.dropoff, 1
        )
        self.assertEqual(
            AssetReservation.objects.get(line__rental=order).asset.code, "OLD-1"
        )

    def test_handover_checks_physical_asset_and_early_return_keeps_schedule(self):
        self.staff.groups.add(Group.objects.get(name=OPERATOR_GROUP))
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        next_day = tomorrow + timedelta(days=1)
        first = services.book_rental(self.customer, self.lens.pk, today, tomorrow, 1)
        next_order = services.book_rental(
            self.customer, self.lens.pk, tomorrow, next_day, 1
        )
        hold = AssetReservation.objects.get(line__rental=first)
        handover = services.prepare_asset(self.staff, first.pk, hold.pk)
        fund_rental(first, self.staff)
        services.pick_up_rental(self.staff, first.pk)
        # Transfer the scenario to the next day without rewriting the stored periods.
        with (
            patch(
                "catalog.rentals.timezone.now",
                return_value=timezone.now() + timedelta(days=1),
            ),
            self.assertRaisesMessage(services.RentalError, "Không đủ thiết bị thực tế"),
        ):
            services.pick_up_rental(self.staff, next_order.pk)
        services.receive_asset(self.staff, first.pk, handover.pk)
        services.inspect_asset(
            self.staff, first.pk, handover.pk, AssetHandover.Inspection.READY
        )
        self.assertEqual(services.available_stock(self.lens, today, tomorrow), 0)
        self.assertEqual(services.checked_out_quantity(self.lens), 0)


class AssetLineMigrationTests(TransactionTestCase):
    def test_0005_upgrade_preserves_open_custody_without_inventing_item_timestamps(
        self,
    ):
        before = [("catalog", "0005_asset_units_and_rental_lines")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(before)
            previous = executor.loader.project_state(before).apps
            users = previous.get_model("auth", "User").objects
            customer = users.create(username="m1-customer")
            staff = users.create(username="m1-staff", is_staff=True)
            item = previous.get_model("catalog", "Equipment").objects.create(
                code="M1",
                name="Máy V2-M1",
                daily_rate_vnd=200,
                total_stock=1,
                tracks_assets=True,
            )
            asset = previous.get_model("catalog", "AssetUnit").objects.create(
                equipment=item,
                code="M1-1",
            )
            today = timezone.localdate()
            yesterday = today - timedelta(days=1)
            picked_up_at = timezone.now() - timedelta(days=1)
            rental = previous.get_model("catalog", "Rental").objects.create(
                customer=customer,
                equipment=item,
                quantity=1,
                daily_rate_vnd=123,
                total_vnd=123,
                status="PICKED_UP",
                pickup_date=yesterday,
                return_date=today,
                picked_up_at=picked_up_at,
            )
            line = previous.get_model("catalog", "RentalLine").objects.create(
                rental=rental,
                equipment=item,
                quantity=1,
                daily_rate_vnd=123,
                total_vnd=123,
            )
            hold = previous.get_model("catalog", "AssetReservation").objects.create(
                line=line,
                asset=asset,
                period=(yesterday, today),
            )

            MigrationExecutor(connection).migrate(latest)
            upgraded = Rental.objects.get(pk=rental.pk)
            self.assertEqual(upgraded.picked_up_at, picked_up_at)
            self.assertEqual(upgraded.status, Rental.Status.PICKED_UP)
            self.assertEqual(upgraded.total_vnd, 123)
            self.assertEqual(upgraded.lines.get().pk, line.pk)
            self.assertEqual(
                AssetReservation.objects.get(pk=hold.pk).asset_id, asset.pk
            )
            self.assertFalse(AssetHandover.objects.exists())
            equipment = Equipment.objects.get(pk=item.pk)
            self.assertEqual(services.checked_out_quantity(equipment), 1)
            self.assertEqual(
                services.available_stock(equipment, today, today + timedelta(days=1)), 0
            )
            returned = services.return_rental(
                get_user_model().objects.get(pk=staff.pk), upgraded.pk
            )
            self.assertEqual(returned.status, Rental.Status.RETURNED)
            self.assertEqual(services.checked_out_quantity(equipment), 0)
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_0004_upgrade_backfills_snapshots_and_reports_active_orders(self):
        old_schema = [("catalog", "0004_equipment_catalog")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old_schema)
            old = executor.loader.project_state(old_schema).apps
            user = old.get_model("auth", "User").objects.create(username="old-customer")
            equipment = old.get_model("catalog", "Equipment").objects.create(
                code="PRE",
                name="Before v2",
                daily_rate_vnd=200,
                total_stock=5,
            )
            today = timezone.localdate()
            now = timezone.now()
            records = old.get_model("catalog", "Rental").objects
            for status, picked_up_at, returned_at in [
                ("CANCELLED", None, None),
                ("CONFIRMED", None, None),
                ("PICKED_UP", now, None),
                ("RETURNED", None, now),
            ]:
                records.create(
                    equipment_id=equipment.pk,
                    customer_id=user.pk,
                    quantity=2,
                    daily_rate_vnd=123,
                    total_vnd=492,
                    status=status,
                    pickup_date=today - timedelta(days=1),
                    return_date=today + timedelta(days=1),
                    picked_up_at=picked_up_at,
                    returned_at=returned_at,
                    cancellation_reason="NO_SHOW" if status == "CANCELLED" else "",
                )
            snapshot = list(records.order_by("pk").values())
            MigrationExecutor(connection).migrate(latest)
            upgraded = list(Rental.objects.order_by("pk").values(*snapshot[0]))
            self.assertEqual(upgraded, snapshot)
            self.assertFalse(Rental.objects.filter(closed_at__isnull=False).exists())
            self.assertEqual(
                list(
                    RentalLine.objects.order_by("rental_id").values_list(
                        "rental_id",
                        "equipment_id",
                        "quantity",
                        "daily_rate_vnd",
                        "total_vnd",
                    )
                ),
                [(row["id"], equipment.pk, 2, 123, 492) for row in snapshot],
            )
            self.assertFalse(AssetUnit.objects.exists())
            self.assertFalse(AssetReservation.objects.exists())
            item = Equipment.objects.get(pk=equipment.pk)
            self.assertFalse(item.tracks_assets)
            self.assertCountEqual(
                services.unassigned_legacy_rentals(item).values_list(
                    "status", flat=True
                ),
                ["CONFIRMED", "PICKED_UP", "RETURNED"],
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
