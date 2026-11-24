from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connections
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
    FinanceCharge,
    FinanceEntry,
    MaintenanceCase,
    Rental,
    RentalLine,
    Stocktake,
    StocktakeLine,
)
from .roles import (
    FINANCE_CLERK_GROUP,
    OPERATOR_GROUP,
    REPORTING_MANAGER_GROUP,
    STOCK_COUNTER_GROUP,
)
from .test_finance import fund_rental, staff_with_groups


class ReportingTests(TestCase):
    def setUp(self):
        self.manager = staff_with_groups("report-manager", REPORTING_MANAGER_GROUP)
        self.counter = staff_with_groups("report-counter", STOCK_COUNTER_GROUP)
        self.customer = get_user_model().objects.create_user("report-customer")
        self.day = timezone.localdate() - timedelta(days=4)
        self.start = datetime.combine(
            self.day, time.min, timezone.get_default_timezone()
        )
        self.equipment = Equipment.objects.create(
            code="REP",
            name="Mẫu báo cáo",
            total_stock=3,
            daily_rate_vnd=100_000,
            tracks_assets=True,
        )

    def rental(
        self,
        *,
        day=None,
        end=None,
        status="CONFIRMED",
        picked=None,
        returned=None,
        no_show=False,
    ):
        day = day or self.day
        return Rental.objects.create(
            equipment=self.equipment,
            customer=self.customer,
            pickup_date=day,
            return_date=end or (day + timedelta(days=1)),
            daily_rate_vnd=100_000,
            total_vnd=100_000,
            quantity=1,
            status=status,
            picked_up_at=picked,
            returned_at=returned,
            cancellation_reason="NO_SHOW" if no_show else "",
            finance_enabled=True,
        )

    def entry(self, rental, kind, amount, at, *, reverses=None, charge=None):
        entry = FinanceEntry.objects.create(
            rental=rental,
            kind=kind,
            amount_vnd=amount,
            reverses=reverses,
            charge=charge,
            recorded_by=self.manager,
            command_id=uuid4(),
            method="CASH"
            if kind
            in ["RENT_RECEIPT", "DEPOSIT_RECEIPT", "RENT_REFUND", "DEPOSIT_REFUND"]
            else "",
        )
        FinanceEntry.objects.filter(pk=entry.pk).update(recorded_at=at)
        return entry

    def hold(self, asset, rental, *, item_custody=True):
        line = RentalLine.objects.create(
            rental=rental,
            equipment=self.equipment,
            quantity=1,
            daily_rate_vnd=100_000,
            total_vnd=100_000,
        )
        hold = AssetReservation.objects.create(
            line=line,
            asset=asset,
            period=(rental.pickup_date, rental.return_date),
        )
        if not item_custody:
            return hold
        return AssetHandover.objects.create(
            reservation=hold,
            asset=asset,
            prepared_by=self.manager,
            picked_up_by=self.manager,
            picked_up_at=rental.picked_up_at,
            returned_at=rental.returned_at,
            returned_by=self.manager,
        )

    def test_net_cash_uses_local_day_and_records_reversal_in_its_own_period(self):
        rental = self.rental()
        prior = self.entry(
            rental, "RENT_RECEIPT", 70_000, self.start - timedelta(microseconds=1)
        )
        self.entry(rental, "RENT_RECEIPT", 120_000, self.start)
        self.entry(rental, "DEPOSIT_RECEIPT", 50_000, self.start)
        self.entry(rental, "RENT_REFUND", 30_000, self.start)
        refund = self.entry(rental, "DEPOSIT_REFUND", 10_000, self.start)
        charge = FinanceCharge.objects.create(
            rental=rental,
            reason="LATE",
            amount_vnd=20_000,
            status="APPROVED",
            command_id=uuid4(),
            notes="Fixture khoản thu",
            proposed_by=self.manager,
            reviewed_at=self.start,
            reviewed_by=self.manager,
        )
        self.entry(rental, "DEPOSIT_APPLIED", 20_000, self.start, charge=charge)
        self.entry(
            rental, "REVERSAL", 70_000, self.start + timedelta(hours=1), reverses=prior
        )
        self.entry(
            rental, "REVERSAL", 10_000, self.start + timedelta(days=1), reverses=refund
        )
        report = services.rental_report(self.manager, self.day, self.day)
        self.assertEqual(report["money"]["rent_net_vnd"], 40_000)
        self.assertEqual(report["money"]["deposit_received_vnd"], 50_000)
        self.assertEqual(report["money"]["deposit_refunded_vnd"], 10_000)
        self.assertEqual(report["money"]["deposit_held_vnd"], 30_000)
        self.assertEqual(report["entries"].count(), 6)
        day_before = self.day - timedelta(days=1)
        self.assertEqual(
            services.rental_report(self.manager, day_before, day_before)["money"][
                "rent_net_vnd"
            ],
            70_000,
        )

    def test_order_buckets_and_usage_clip_hours_to_membership_and_known_custody(self):
        first = AssetUnit.objects.create(
            equipment=self.equipment,
            code="REP-A",
            reporting_since=self.start - timedelta(days=1),
        )
        retired = AssetUnit.objects.create(
            equipment=self.equipment,
            code="REP-B",
            reporting_since=self.start - timedelta(days=1),
            status="RETIRED",
        )
        partial = AssetUnit.objects.create(
            equipment=self.equipment,
            code="REP-C",
            reporting_since=self.start + timedelta(hours=8),
        )
        MaintenanceCase.objects.create(
            asset=retired,
            kind="PLANNED",
            state="RESOLVED",
            notes="Ngừng sử dụng",
            reported_by=self.manager,
            resolution="RETIRED",
            resolved_by=self.manager,
            resolved_at=self.start + timedelta(hours=12),
        )
        early = self.rental(
            day=self.day - timedelta(days=1),
            end=self.day + timedelta(days=1),
            status="RETURNED",
            picked=self.start - timedelta(hours=2),
            returned=self.start + timedelta(hours=6),
        )
        self.hold(first, early)
        uncertain = self.rental(
            day=self.day - timedelta(days=1),
            end=self.day,
            status="RETURNED",
            picked=self.start + timedelta(hours=8),
            returned=self.start + timedelta(hours=14),
        )
        self.hold(partial, uncertain, item_custody=False)
        complete = self.rental(
            status="RETURNED",
            picked=self.start + timedelta(hours=17),
            returned=self.start + timedelta(hours=19),
        )
        source = self.hold(partial, complete)
        self.rental()
        self.rental(status="CANCELLED", no_show=True)

        report = services.rental_report(self.manager, self.day, self.day)
        self.assertEqual(
            report["counts"],
            {"active": 1, "completed": 1, "cancelled": 1, "no_show": 1},
        )
        self.assertEqual(report["usage"]["available_hours"], 46)
        self.assertEqual(report["usage"]["used_hours"], 8)
        self.assertAlmostEqual(report["usage"]["percent"], 800 / 46)
        self.assertTrue(report["usage"]["incomplete"])
        self.assertEqual(
            report["usage"]["rows"][-1]["sources"], [(complete.pk, source.pk)]
        )

    def test_web_and_api_require_report_permission_and_trace_to_source(self):
        rental = self.rental()
        entry = self.entry(rental, "RENT_RECEIPT", 100_000, self.start)
        query = {"first": self.day.isoformat(), "last": self.day.isoformat()}
        url = reverse("management-reports")
        source = reverse("management-audit", args=[rental.pk])
        api = APIClient()
        self.client.force_login(self.counter)
        api.force_authenticate(self.counter)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            api.get(reverse("api-management-reports"), query).status_code, 403
        )
        self.assertEqual(self.client.get(source).status_code, 403)
        self.client.force_login(self.manager)
        api.force_authenticate(self.manager)
        self.assertContains(self.client.get(url, query), f"{source}#entry-{entry.pk}")
        self.assertContains(self.client.get(source), f"Giao dịch #{entry.pk}")
        self.assertEqual(
            api.get(reverse("api-management-reports"), query).data["money"][
                "rent_net_vnd"
            ],
            "100000",
        )
        self.assertEqual(
            api.get(reverse("api-management-audit", args=[rental.pk])).data["entries"][
                0
            ]["id"],
            entry.pk,
        )


class StocktakeTests(TestCase):
    def setUp(self):
        self.manager = staff_with_groups("count-manager", REPORTING_MANAGER_GROUP)
        self.counter = staff_with_groups(
            "count-counter", STOCK_COUNTER_GROUP, OPERATOR_GROUP, FINANCE_CLERK_GROUP
        )
        self.customer = get_user_model().objects.create_user("count-customer")
        self.equipment = Equipment.objects.create(
            code="COUNT",
            name="Mẫu kiểm kê",
            total_stock=2,
            daily_rate_vnd=100_000,
            tracks_assets=True,
        )
        self.camera = AssetUnit.objects.create(
            equipment=self.equipment, code="COUNT-A", reporting_since=timezone.now()
        )
        self.spare = AssetUnit.objects.create(
            equipment=self.equipment,
            code="COUNT-B",
            status=AssetUnit.Status.QUARANTINED,
            reporting_since=timezone.now(),
        )

    def test_snapshot_retains_expected_status_and_links_movement_after_opening(self):
        today = timezone.localdate()
        order = services.book_rental(
            self.customer, self.equipment.pk, today, today + timedelta(days=1), 1
        )
        reservation = order.lines.get().reservations.get()
        handover = services.prepare_asset(self.counter, order.pk, reservation.pk)
        fund_rental(order, self.counter)
        services.pick_up_rental(self.counter, order.pk)
        session = services.open_stocktake(self.counter, self.equipment.pk)
        with self.assertRaisesMessage(services.RentalError, "đã có phiên"):
            services.open_stocktake(self.counter, self.equipment.pk)
        self.assertEqual(session.lines.get(code=self.camera.code).expected, "OUT")
        self.assertEqual(
            session.lines.get(code=self.spare.code).expected, "QUARANTINED"
        )
        with self.assertRaisesMessage(services.RentalError, "không phát sinh"):
            services.record_stocktake_line(
                self.counter,
                session.pk,
                code=self.camera.code,
                observed="OUT",
                movement_id=handover.pk,
            )

        services.receive_asset(self.counter, order.pk, handover.pk)
        services.inspect_asset(self.counter, order.pk, handover.pk, "READY")
        line = services.record_stocktake_line(
            self.counter,
            session.pk,
            code=self.camera.code,
            observed="READY",
            movement_id=handover.pk,
            notes="Đã nhận và kiểm sau khi mở phiên.",
        )
        self.assertEqual(line.expected, "OUT")
        self.assertEqual(line.movement_id, handover.pk)
        with self.assertRaisesMessage(services.RentalError, "đối chiếu đủ"):
            services.close_stocktake(self.manager, session.pk)
        services.record_stocktake_line(
            self.counter, session.pk, code=self.spare.code, observed="QUARANTINED"
        )
        unknown = services.record_stocktake_line(
            self.counter, session.pk, code="OTHER-CODE", observed="READY"
        )
        self.assertIsNone(unknown.asset_id)
        self.assertEqual(unknown.expected, "UNEXPECTED")
        with self.assertRaisesMessage(services.RentalError, "chênh lệch"):
            services.close_stocktake(self.manager, session.pk)
        services.resolve_stocktake_line(
            self.manager, session.pk, line.pk, notes="Khớp lượt nhận thực tế."
        )
        services.resolve_stocktake_line(
            self.manager, session.pk, unknown.pk, notes="Kiểm tra mã ngoài danh sách."
        )
        services.close_stocktake(self.manager, session.pk)
        with self.assertRaisesMessage(services.RentalError, "đã chốt"):
            services.record_stocktake_line(
                self.counter, session.pk, code=self.camera.code, observed="MISSING"
            )
        self.spare.refresh_from_db()
        self.assertEqual(self.spare.status, "QUARANTINED")
        self.assertEqual(
            services.stocktake_detail(self.manager, session.pk)["movements"].get().pk,
            handover.pk,
        )

    def test_web_and_api_record_permissions_and_manager_closure(self):
        api = APIClient()
        api.force_authenticate(self.customer)
        self.assertEqual(
            api.post(
                reverse("api-stocktakes"), {"equipment_id": self.equipment.pk}
            ).status_code,
            403,
        )
        self.client.force_login(self.counter)
        response = self.client.post(
            reverse("stocktakes"), {"equipment": self.equipment.pk}, follow=True
        )
        self.assertContains(response, "Kết quả theo mã kho")
        session = Stocktake.objects.get(equipment=self.equipment)
        api.force_authenticate(self.counter)
        self.assertEqual(
            api.post(reverse("api-stocktake-close", args=[session.pk])).status_code, 403
        )
        result = api.post(
            reverse("api-stocktake-record", args=[session.pk]),
            {"code": self.camera.code, "observed": "MISSING"},
        )
        self.assertEqual(result.data["expected"], "READY")
        self.assertEqual(
            api.post(
                reverse("api-stocktake-resolve", args=[session.pk, result.data["id"]]),
                {"notes": "Đã đối chiếu"},
            ).status_code,
            403,
        )
        api.force_authenticate(self.manager)
        self.assertEqual(
            api.post(
                reverse("api-stocktake-resolve", args=[session.pk, result.data["id"]]),
                {
                    "notes": "Đã đối chiếu và hẹn kiểm tra lại.",
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            api.get(reverse("api-stocktake-detail", args=[session.pk])).data["lines"][
                0
            ]["resolved_by"],
            self.manager.username,
        )

    def test_brand_filter_retains_search_after_invalid_dates_and_existing_api_shape(
        self,
    ):
        item = self.equipment
        services.update_equipment(
            self.counter,
            item.pk,
            item.name,
            item.daily_rate_vnd,
            item.total_stock,
            brand="  Leica  ",
        )
        Equipment.objects.create(
            code="COUNT-OTHER",
            name="Mẫu khác",
            total_stock=1,
            daily_rate_vnd=90_000,
            brand="Sony",
        )
        query = {"search": "COUNT", "kind": "CAMERA", "brand": "leica"}
        page = self.client.get(
            reverse("equipment-list"), query | {"pickup_date": "invalid"}
        )
        self.assertContains(page, item.name)
        self.assertNotContains(page, "Mẫu khác")
        self.assertEqual(page.context["form"].errors.keys(), {"pickup_date"})
        api = APIClient()
        listing = api.get(reverse("api-equipment-list"), query).data
        self.assertEqual([entry["id"] for entry in listing], [item.pk])
        self.assertEqual(
            set(listing[0]),
            {
                "id",
                "code",
                "name",
                "kind",
                "specifications",
                "daily_rate_vnd",
                "deposit_vnd",
            },
        )


class StocktakeConcurrencyTests(TransactionTestCase):
    def test_two_requests_open_one_snapshot(self):
        actor = staff_with_groups("stock-race", STOCK_COUNTER_GROUP)
        equipment = Equipment.objects.create(
            code="COUNT-RACE",
            name="Kiểm đồng thời",
            total_stock=1,
            daily_rate_vnd=1,
            tracks_assets=True,
        )
        AssetUnit.objects.create(equipment=equipment, code="COUNT-RACE-1")
        barrier = Barrier(2)

        def post():
            try:
                clerk = get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                services.open_stocktake(clerk, equipment.pk)
                return 201
            except services.RentalError as error:
                return error.status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(post) for _ in range(2)]
            self.assertCountEqual([job.result(timeout=15) for job in jobs], [201, 409])
        self.assertEqual(Stocktake.objects.filter(equipment=equipment).count(), 1)
        self.assertEqual(
            StocktakeLine.objects.filter(stocktake__equipment=equipment).count(), 1
        )


class ReportingMigrationTests(TransactionTestCase):
    def test_upgrade_from_0007_starts_tracking_and_retains_unverified_brands(self):
        previous_target = [("catalog", "0007_rental_finance")]
        executor = MigrationExecutor(connections["default"])
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(previous_target)
            models = executor.loader.project_state(previous_target).apps
            old_equipment = models.get_model("catalog", "Equipment")
            old_units = models.get_model("catalog", "AssetUnit")
            item = old_equipment.objects.create(
                code="MEASURE",
                name="Mẫu v2-m3",
                total_stock=1,
                daily_rate_vnd=1,
                tracks_assets=True,
            )
            other = old_equipment.objects.create(
                code="UNASSIGNED", name="Mẫu Base", total_stock=1, daily_rate_vnd=1
            )
            tracked = old_units.objects.create(
                equipment=item, code="MEASURE-1", serial="SAVED"
            )
            untracked = old_units.objects.create(equipment=other, code="UNASSIGNED-1")
            before = timezone.now()
            MigrationExecutor(connections["default"]).migrate(latest)
            current = AssetUnit.objects.get(pk=tracked.pk)
            self.assertEqual(current.serial, "SAVED")
            self.assertGreaterEqual(current.reporting_since, before)
            self.assertIsNone(AssetUnit.objects.get(pk=untracked.pk).reporting_since)
            self.assertEqual(Equipment.objects.get(pk=item.pk).brand, "")
            self.assertFalse(Stocktake.objects.exists())
        finally:
            MigrationExecutor(connections["default"]).migrate(latest)
