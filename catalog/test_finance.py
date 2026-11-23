from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import (
    AssetHandover,
    AssetUnit,
    Equipment,
    FinanceEntry,
    Rental,
)
from .roles import (
    FINANCE_CLERK_GROUP,
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    OPERATOR_GROUP,
)

Kind = FinanceEntry.Kind


def fund_rental(rental, staff):
    """Settle the rental price for non-finance tests that exercise a new pickup."""
    staff.groups.add(Group.objects.get(name=FINANCE_CLERK_GROUP))
    clerk = get_user_model().objects.get(pk=staff.pk)
    services.post_finance_entry(
        clerk,
        rental.pk,
        command_id=uuid4(),
        kind=Kind.RENT_RECEIPT,
        amount_vnd=rental.total_vnd,
        method="CASH",
    )


def staff_with_groups(name, *groups):
    staff = get_user_model().objects.create_user(name, is_staff=True)
    staff.groups.add(*Group.objects.filter(name__in=groups))
    return staff


class FinanceTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user("finance-customer")
        self.clerk = staff_with_groups(
            "finance-clerk", FINANCE_CLERK_GROUP, OPERATOR_GROUP
        )
        self.manager = staff_with_groups(
            "finance-manager", FINANCE_MANAGER_GROUP, MANAGER_GROUP
        )
        self.item = Equipment.objects.create(
            code="FINANCE",
            name="Máy kiểm thử quyết toán",
            total_stock=2,
            daily_rate_vnd=100_000,
            deposit_vnd=50_000,
            tracks_assets=True,
        )
        for i in range(2):
            AssetUnit.objects.create(equipment=self.item, code=f"FINANCE-{i}")
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)

    def book(self, *, quantity=1, pickup=None, end=None):
        return services.book_rental(
            self.customer,
            self.item.pk,
            pickup or self.today,
            end or self.tomorrow,
            quantity,
        )

    def cash(self, rental, kind, amount, **kwargs):
        return services.post_finance_entry(
            kwargs.pop("actor", self.clerk),
            rental.pk,
            kind=kind,
            amount_vnd=amount,
            command_id=kwargs.pop("command_id", uuid4()),
            method="CASH",
            **kwargs,
        )

    def pay(self, rental):
        self.cash(rental, Kind.RENT_RECEIPT, rental.total_vnd)
        self.cash(
            rental,
            Kind.DEPOSIT_RECEIPT,
            services.finance_summary(rental)["deposit_required_vnd"],
        )

    def prepare(self, rental):
        return [
            services.prepare_asset(self.clerk, rental.pk, hold.pk)
            for hold in services.rental_asset_history(rental)
        ]

    def test_snapshot_partial_receipts_retry_and_pickup_gate(self):
        rental = self.book(quantity=2)
        services.set_equipment_deposit(self.manager, self.item.pk, 75_000)
        self.assertEqual(
            services.finance_summary(rental)["deposit_required_vnd"], 100_000
        )
        handovers = self.prepare(rental)
        key = uuid4()
        first = self.cash(rental, Kind.RENT_RECEIPT, 150_000, command_id=key)
        same = self.cash(rental, Kind.RENT_RECEIPT, 150_000, command_id=key)
        self.assertEqual(first.pk, same.pk)
        with self.assertRaisesMessage(services.RentalError, "đã được dùng"):
            self.cash(rental, Kind.RENT_RECEIPT, 160_000, command_id=key)
        self.cash(rental, Kind.RENT_RECEIPT, 50_000)
        with self.assertRaisesMessage(services.RentalError, "đủ tiền thuê và cọc"):
            services.pick_up_rental(self.clerk, rental.pk)
        self.assertTrue(
            all(
                row.picked_up_at is None
                for row in AssetHandover.objects.filter(
                    pk__in=[item.pk for item in handovers]
                )
            )
        )
        self.cash(rental, Kind.DEPOSIT_RECEIPT, 100_000)
        self.assertEqual(
            services.pick_up_rental(self.clerk, rental.pk).status,
            Rental.Status.PICKED_UP,
        )

    def test_extension_changes_balance_and_refund_waits_for_every_inspection(self):
        rental = self.book(quantity=2)
        self.pay(rental)
        first, second = self.prepare(rental)
        services.pick_up_rental(self.clerk, rental.pk)
        change = services.request_rental_change(
            self.customer,
            rental.pk,
            "EXTEND",
            self.today,
            self.tomorrow + timedelta(days=1),
            accepted_total_vnd=400_000,
        )
        services.review_rental_change(self.clerk, change.pk, True)
        rental.refresh_from_db()
        self.assertEqual(services.finance_summary(rental)["balance_due_vnd"], 200_000)
        services.receive_asset(self.clerk, rental.pk, first.pk)
        services.inspect_asset(self.clerk, rental.pk, first.pk, "READY")
        services.receive_asset(self.clerk, rental.pk, second.pk)
        with self.assertRaisesMessage(services.RentalError, "chưa đủ điều kiện"):
            self.cash(rental, Kind.DEPOSIT_REFUND, 100_000)
        services.inspect_asset(self.clerk, rental.pk, second.pk, "READY")
        self.cash(rental, Kind.RENT_RECEIPT, 200_000)
        self.cash(rental, Kind.DEPOSIT_REFUND, 100_000)
        rental.refresh_from_db()
        summary = services.finance_summary(rental)
        self.assertEqual(summary["rent_vnd"], 400_000)
        self.assertEqual(summary["balance_due_vnd"], 0)
        self.assertEqual(summary["deposit_to_refund_vnd"], 0)

    def test_manager_resolves_waives_applies_deposit_and_reversal_preserves_history(
        self,
    ):
        rental = self.book()
        self.pay(rental)
        handover = self.prepare(rental)[0]
        services.pick_up_rental(self.clerk, rental.pk)
        services.receive_asset(self.clerk, rental.pk, handover.pk)
        services.inspect_asset(
            self.clerk, rental.pk, handover.pk, "DAMAGE", "Nút nguồn bị hỏng."
        )
        charge = services.propose_finance_charge(
            self.clerk,
            rental.pk,
            command_id=uuid4(),
            reason="DAMAGE",
            amount_vnd=120_000,
            notes="Chi phí sửa theo hồ sơ",
            handover_id=handover.pk,
        )
        self.assertIsNotNone(charge.incident_id)
        with self.assertRaisesMessage(services.RentalError, "quyền quản lý"):
            services.review_finance_charge(
                self.clerk, rental.pk, charge.pk, approve=True, notes="Duyệt"
            )
        services.review_finance_charge(
            self.manager, rental.pk, charge.pk, approve=True, notes="Đã đối chiếu"
        )
        with self.assertRaisesMessage(services.RentalError, "chưa đủ điều kiện"):
            self.cash(rental, Kind.DEPOSIT_REFUND, 1)
        services.resolve_case(
            self.manager, charge.incident_id, "READY", "Đã sửa và kiểm tra"
        )
        services.post_finance_entry(
            self.manager,
            rental.pk,
            kind=Kind.WAIVER,
            command_id=uuid4(),
            amount_vnd=20_000,
            charge_id=charge.pk,
            notes="Giảm một phần chi phí sửa.",
        )
        applied = services.post_finance_entry(
            self.manager,
            rental.pk,
            kind=Kind.DEPOSIT_APPLIED,
            command_id=uuid4(),
            amount_vnd=50_000,
            charge_id=charge.pk,
            notes="Dùng cọc đã thu.",
        )
        rental.refresh_from_db()
        self.assertEqual(services.finance_summary(rental)["balance_due_vnd"], 50_000)
        original = rental.finance_entries.get(kind=Kind.DEPOSIT_RECEIPT)
        with self.assertRaisesMessage(services.RentalError, "các giao dịch sử dụng"):
            services.post_finance_entry(
                self.manager,
                rental.pk,
                kind=Kind.REVERSAL,
                command_id=uuid4(),
                entry_id=original.pk,
                notes="Đảo khoản đã khấu trừ.",
            )
        reversal = services.post_finance_entry(
            self.manager,
            rental.pk,
            kind=Kind.REVERSAL,
            command_id=uuid4(),
            entry_id=applied.pk,
            notes="Khách thanh toán riêng phí sửa.",
        )
        self.assertEqual(reversal.reverses_id, applied.pk)
        self.assertTrue(rental.finance_entries.filter(pk=applied.pk).exists())
        self.cash(rental, Kind.RENT_RECEIPT, 100_000)
        self.cash(rental, Kind.DEPOSIT_REFUND, 50_000)
        self.assertEqual(services.finance_summary(rental)["balance_due_vnd"], 0)

    def test_cancelled_order_refunds_actual_rent_and_deposit(self):
        rental = self.book(pickup=self.tomorrow, end=self.tomorrow + timedelta(days=1))
        self.pay(rental)
        rental = services.cancel_rental(self.customer, rental.pk)
        summary = services.finance_summary(rental)
        self.assertEqual(summary["rent_to_refund_vnd"], 100_000)
        self.assertEqual(summary["deposit_to_refund_vnd"], 50_000)
        self.assertEqual(summary["rent_vnd"], 0)
        with self.assertRaisesMessage(services.RentalError, "vượt số dư"):
            self.cash(rental, Kind.DEPOSIT_REFUND, 50_001)
        self.cash(rental, Kind.RENT_REFUND, 100_000)
        self.cash(rental, Kind.DEPOSIT_REFUND, 50_000)
        self.assertEqual(services.finance_summary(rental)["deposit_held_vnd"], 0)

    def test_failed_pickup_preserves_cash_for_reschedule_and_no_show(self):
        rental = self.book(end=self.tomorrow + timedelta(days=1))
        self.pay(rental)
        with self.assertRaisesMessage(services.RentalError, "Chuẩn bị đủ mã kho"):
            services.pick_up_rental(self.clerk, rental.pk)
        self.assertEqual(rental.finance_entries.count(), 2)
        pickup = self.tomorrow + timedelta(days=2)
        end = pickup + timedelta(days=1)
        change = services.request_rental_change(
            self.customer,
            rental.pk,
            "RESCHEDULE",
            pickup,
            end,
            accepted_total_vnd=100_000,
        )
        services.review_rental_change(self.clerk, change.pk, True)
        rental.refresh_from_db()
        self.assertEqual(
            services.finance_summary(rental)["rent_to_refund_vnd"], 100_000
        )
        with self.assertRaisesMessage(services.RentalError, "chưa đủ điều kiện"):
            self.cash(rental, Kind.RENT_REFUND, 100_000)
        with patch("catalog.rentals.timezone.localdate", return_value=end):
            rental = services.mark_no_show(self.clerk, rental.pk)
        self.assertEqual(rental.cancellation_reason, "NO_SHOW")
        self.assertEqual(
            services.finance_summary(rental)["rent_to_refund_vnd"], 200_000
        )
        self.cash(rental, Kind.RENT_REFUND, 200_000)
        self.cash(rental, Kind.DEPOSIT_REFUND, 50_000)

    def test_confirmed_loss_supplies_charge_evidence_without_a_return_timestamp(self):
        rental = self.book()
        self.pay(rental)
        handover = self.prepare(rental)[0]
        services.pick_up_rental(self.clerk, rental.pk)
        case = services.report_incident(
            self.clerk,
            handover.asset_id,
            "LOST",
            "Không tìm thấy máy.",
            handover_id=handover.pk,
        )
        proposal = {
            "command_id": uuid4(),
            "reason": "LOST",
            "amount_vnd": 80_000,
            "notes": "Khoản bồi thường theo hồ sơ",
            "handover_id": handover.pk,
        }
        with self.assertRaisesMessage(services.RentalError, "xác nhận mất"):
            services.propose_finance_charge(self.clerk, rental.pk, **proposal)
        services.resolve_case(self.manager, case.pk, "RETIRED", "Đã xác nhận mất.")
        charge = services.propose_finance_charge(self.clerk, rental.pk, **proposal)
        self.assertEqual(charge.incident_id, case.pk)
        self.assertEqual(
            services.propose_finance_charge(self.clerk, rental.pk, **proposal).pk,
            charge.pk,
        )
        services.review_finance_charge(
            self.manager, rental.pk, charge.pk, approve=True, notes="Đã duyệt."
        )
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.CLOSED)
        self.assertIsNone(rental.returned_at)
        self.assertEqual(services.finance_summary(rental)["balance_due_vnd"], 80_000)
        self.assertTrue(services.finance_summary(rental)["can_settle"])

    def test_web_ledger_idempotency_owner_summary_and_manager_permission(self):
        rental = self.book()
        ledger = reverse("finance-ledger", args=[rental.pk])
        api_summary = reverse("api-finance-summary", args=[rental.pk])
        api = APIClient()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(ledger).status_code, 403)
        api.force_authenticate(self.customer)
        self.assertEqual(api.get(api_summary).data["deposit_required_vnd"], "50000")
        api.force_authenticate(get_user_model().objects.create_user("finance-outsider"))
        self.assertEqual(api.get(api_summary).status_code, 404)
        self.client.force_login(self.clerk)
        self.assertContains(self.client.get(ledger), "Sổ giao dịch")
        command = uuid4()
        values = {
            "action": "cash",
            "cash-command_id": command,
            "cash-kind": "RENT_RECEIPT",
            "cash-amount_vnd": 100_000,
            "cash-method": "TRANSFER",
            "cash-notes": "Giao dịch thử",
        }
        self.assertRedirects(self.client.post(ledger, values), ledger)
        self.assertRedirects(self.client.post(ledger, values), ledger)
        self.assertEqual(rental.finance_entries.count(), 1)
        api.force_authenticate(self.clerk)
        self.assertEqual(
            api.post(
                reverse("api-finance-deposit", args=[self.item.pk]),
                {
                    "amount_vnd": 1,
                },
            ).status_code,
            403,
        )
        api.force_authenticate(self.manager)
        self.assertEqual(
            api.post(
                reverse("api-finance-deposit", args=[self.item.pk]),
                {
                    "amount_vnd": 75_000,
                },
            ).data["deposit_vnd"],
            75_000,
        )
        self.assertEqual(
            services.finance_summary(rental)["deposit_required_vnd"], 50_000
        )


class FinanceMigrationTests(TransactionTestCase):
    def test_0006_upgrade_preserves_order_and_requires_legacy_evidence(self):
        previous_target = [("catalog", "0006_rental_operations")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(previous_target)
            previous = executor.loader.project_state(previous_target).apps
            old_user = previous.get_model("auth", "User").objects.create(
                username="pre-finance"
            )
            item = previous.get_model("catalog", "Equipment").objects.create(
                code="PRE-FIN",
                name="Máy cũ",
                total_stock=1,
                daily_rate_vnd=25_000,
            )
            today = timezone.localdate()
            rental = previous.get_model("catalog", "Rental").objects.create(
                equipment=item,
                customer=old_user,
                quantity=1,
                daily_rate_vnd=25_000,
                total_vnd=25_000,
                pickup_date=today,
                return_date=today + timedelta(days=1),
            )
            previous.get_model("catalog", "RentalLine").objects.create(
                equipment=item,
                rental=rental,
                quantity=1,
                daily_rate_vnd=25_000,
                total_vnd=25_000,
            )
            MigrationExecutor(connection).migrate(latest)
            restored = Rental.objects.get(pk=rental.pk)
            self.assertEqual(restored.total_vnd, 25_000)
            self.assertFalse(restored.finance_enabled)
            self.assertEqual(restored.finance_entries.count(), 0)
            self.assertTrue(services.finance_summary(restored)["legacy_pending"])
            staff = staff_with_groups("legacy-clerk", FINANCE_CLERK_GROUP)
            manager = staff_with_groups("legacy-manager", FINANCE_MANAGER_GROUP)
            self.assertEqual(
                services.pick_up_rental(staff, restored.pk).status,
                Rental.Status.PICKED_UP,
            )
            with self.assertRaisesMessage(services.RentalError, "quyền quản lý"):
                services.post_finance_entry(
                    staff,
                    restored.pk,
                    kind=Kind.RENT_RECEIPT,
                    method="CASH",
                    amount_vnd=25_000,
                    command_id=uuid4(),
                    notes="Chứng từ đã nhận",
                )
            services.post_finance_entry(
                manager,
                restored.pk,
                kind=Kind.RENT_RECEIPT,
                method="CASH",
                amount_vnd=25_000,
                command_id=uuid4(),
                notes="Chứng từ đã nhận",
            )
            services.post_finance_entry(
                manager,
                restored.pk,
                kind=Kind.RECONCILIATION,
                command_id=uuid4(),
                notes="Đã đối chiếu sổ quầy.",
            )
            self.assertFalse(services.finance_summary(restored)["legacy_pending"])
        finally:
            MigrationExecutor(connection).migrate(latest)


class FinanceConcurrencyTests(TransactionTestCase):
    def test_repeated_receipt_and_competing_refunds_hold_one_balance(self):
        clerk = staff_with_groups("race-clerk", FINANCE_CLERK_GROUP)
        customer = get_user_model().objects.create_user("finance-race")
        equipment = Equipment.objects.create(
            code="CASH-RACE",
            name="Máy test",
            daily_rate_vnd=100_000,
            deposit_vnd=50_000,
            total_stock=1,
        )
        pickup = timezone.localdate() + timedelta(days=1)
        rental = services.book_rental(
            customer, equipment.pk, pickup, pickup + timedelta(days=1), 1
        )

        def run_pair(kind, keys):
            barrier = Barrier(2)

            def post(key):
                close_old_connections()
                try:
                    actor = get_user_model().objects.get(pk=clerk.pk)
                    barrier.wait(timeout=10)
                    entry = services.post_finance_entry(
                        actor,
                        rental.pk,
                        kind=kind,
                        amount_vnd=50_000,
                        method="CASH",
                        command_id=key,
                    )
                    return 201, entry.pk
                except services.RentalError as error:
                    return error.status, None
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(post, keys))

        key = uuid4()
        receipts = run_pair(Kind.DEPOSIT_RECEIPT, (key, key))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(receipts[0][0], 201)
        self.assertEqual(rental.finance_entries.count(), 1)
        services.cancel_rental(customer, rental.pk)
        refunds = run_pair(Kind.DEPOSIT_REFUND, (uuid4(), uuid4()))
        self.assertCountEqual([status for status, _ in refunds], [201, 409])
        self.assertEqual(rental.finance_entries.count(), 2)
