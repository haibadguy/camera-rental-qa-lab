from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .errors import RentalError
from .inventory import free_assets
from .maintenance import (
    maintenance_cases,
    plan_maintenance,
    report_incident,
    resolve_case,
    start_repair,
)
from .models import (
    AssetHandover,
    AssetReservation,
    AssetUnit,
    Equipment,
    MaintenanceCase,
    Rental,
)
from .rentals import book_order
from .roles import MANAGER_GROUP, OPERATOR_GROUP


def _actor(username, group_name):
    user = get_user_model().objects.create_user(username, is_staff=True)
    user.groups.add(Group.objects.get(name=group_name))
    return user


def _asset():
    equipment = Equipment.objects.create(
        code="M-01",
        name="Camera",
        daily_rate_vnd=120_000,
        total_stock=1,
        tracks_assets=True,
    )
    return equipment, AssetUnit.objects.create(equipment=equipment, code="M-01-A")


class MaintenanceTests(TestCase):
    def setUp(self):
        self.operator = _actor("m2-operator", OPERATOR_GROUP)
        self.manager = _actor("m2-manager", MANAGER_GROUP)
        self.customer = get_user_model().objects.create_user("m2-customer")
        self.equipment, self.asset = _asset()
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.later = self.tomorrow + timedelta(days=1)

    def _book(self, start, end):
        return book_order(
            self.customer,
            start,
            end,
            [{"equipment_id": self.equipment.id, "quantity": 1}],
        )

    def test_planned_maintenance_shares_booking_calendar_and_range_boundaries(self):
        self._book(self.today, self.tomorrow)
        with self.assertRaises(RentalError) as conflict:
            plan_maintenance(
                self.operator, self.asset.id, self.today, self.later, "Bảo dưỡng"
            )
        self.assertEqual(conflict.exception.status, 409)
        self.assertFalse(MaintenanceCase.objects.exists())
        plan = plan_maintenance(
            self.operator, self.asset.id, self.tomorrow, self.later, "Bảo dưỡng"
        )
        self.assertEqual(plan.state, MaintenanceCase.State.PLANNED)
        self.assertEqual(plan.reservation.asset, self.asset)
        with self.assertRaises(RentalError) as blocked:
            self._book(self.tomorrow, self.later)
        self.assertEqual(blocked.exception.status, 409)
        resolve_case(
            self.manager, plan.id, MaintenanceCase.Resolution.READY, "Đã kiểm tra đạt"
        )
        self.assertIsNotNone(AssetReservation.objects.get(maintenance=plan).released_at)
        self._book(self.tomorrow, self.later)

    def test_planned_work_starts_in_window_and_stays_unavailable_until_release(self):
        plan = plan_maintenance(
            self.operator, self.asset.id, self.today, self.tomorrow, "Vệ sinh cảm biến"
        )
        start_repair(self.operator, plan.id, "Đã tiếp nhận để vệ sinh")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetUnit.Status.QUARANTINED)
        self.assertFalse(
            free_assets([self.equipment.id], self.tomorrow, self.later).exists()
        )
        resolve_case(
            self.manager, plan.id, MaintenanceCase.Resolution.READY, "Kiểm tra ảnh đạt"
        )
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetUnit.Status.READY)

    def test_unplanned_damage_blocks_new_availability_and_keeps_existing_hold(self):
        order = self._book(self.tomorrow, self.later)
        case = report_incident(
            self.operator,
            self.asset.id,
            MaintenanceCase.Kind.DAMAGE,
            "Khóa ngàm bị kẹt",
        )
        hold = AssetReservation.objects.get(line__rental=order)
        self.assertIsNone(hold.released_at)
        self.assertFalse(
            free_assets([self.equipment.id], self.today, self.tomorrow).exists()
        )
        with self.assertRaises(RentalError) as duplicate:
            report_incident(
                self.operator, self.asset.id, MaintenanceCase.Kind.DAMAGE, "Ghi trùng"
            )
        self.assertEqual(duplicate.exception.status, 409)
        with self.assertRaises(RentalError) as forbidden:
            resolve_case(
                self.operator, case.id, MaintenanceCase.Resolution.READY, "Đã kiểm tra"
            )
        self.assertEqual(forbidden.exception.status, 403)
        start_repair(self.operator, case.id, "Thay khóa ngàm")
        case = resolve_case(
            self.manager,
            case.id,
            MaintenanceCase.Resolution.READY,
            "Khóa ngàm hoạt động tốt",
        )
        self.assertEqual(case.repaired_by, self.operator)
        self.assertEqual(case.resolved_by, self.manager)
        self.assertEqual(case.resolution_notes, "Khóa ngàm hoạt động tốt")
        self.assertTrue(
            free_assets([self.equipment.id], self.today, self.tomorrow).exists()
        )
        self.assertFalse(
            free_assets([self.equipment.id], self.tomorrow, self.later).exists()
        )
        with self.assertRaises(RentalError) as hidden:
            maintenance_cases(self.customer)
        self.assertEqual(hidden.exception.status, 403)

    def test_manager_closes_lost_custody_without_creating_a_return_timestamp(self):
        order = self._book(self.today, self.tomorrow)
        order.picked_up_at = timezone.now()
        order.status = Rental.Status.PICKED_UP
        order.save(update_fields=["picked_up_at", "status"])
        pickup = AssetHandover.objects.create(
            asset=self.asset,
            reservation=AssetReservation.objects.get(line__rental=order),
            prepared_by=self.operator,
            picked_up_at=order.picked_up_at,
            picked_up_by=self.operator,
        )
        case = report_incident(
            self.operator,
            self.asset.pk,
            MaintenanceCase.Kind.LOST,
            "Khách báo mất thân máy",
        )
        self.assertEqual(case.handover, pickup)
        pickup.refresh_from_db()
        self.assertIsNone(pickup.lost_at)
        resolve_case(
            self.manager,
            case.id,
            MaintenanceCase.Resolution.RETIRED,
            "Xác nhận mất máy",
        )
        pickup.refresh_from_db()
        order.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertIsNone(pickup.returned_at)
        self.assertIsNone(order.returned_at)
        self.assertEqual(pickup.lost_by, self.manager)
        self.assertIsNotNone(pickup.lost_at)
        self.assertIsNotNone(order.closed_at)
        self.assertEqual(order.status, Rental.Status.CLOSED)
        self.assertEqual(self.asset.status, AssetUnit.Status.RETIRED)


class ConcurrentMaintenanceTests(TransactionTestCase):
    def test_booking_and_maintenance_cannot_hold_the_same_asset_and_period(self):
        self.assertEqual(connection.vendor, "postgresql")
        operator = _actor("m2-race-operator", OPERATOR_GROUP)
        customer = get_user_model().objects.create_user("m2-race-customer")
        equipment, asset = _asset()
        start = timezone.localdate()
        end = start + timedelta(days=2)
        ready = Barrier(2, timeout=10)

        def reserve(operation):
            try:
                ready.wait()
                if operation == "maintenance":
                    plan_maintenance(operator, asset.id, start, end, "Kiểm tra định kỳ")
                else:
                    book_order(
                        customer,
                        start,
                        end,
                        [{"equipment_id": equipment.id, "quantity": 1}],
                    )
                return "success"
            except RentalError as error:
                return error.status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ("booking", "maintenance")))

        self.assertCountEqual(results, ["success", 409])
        self.assertEqual(Rental.objects.count() + MaintenanceCase.objects.count(), 1)
        self.assertEqual(
            AssetReservation.objects.filter(released_at__isnull=True).count(), 1
        )
