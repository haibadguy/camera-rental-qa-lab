from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .errors import RentalError
from .models import (
    AssetHandover,
    AssetReservation,
    AssetUnit,
    Equipment,
    Rental,
    RentalChangeRequest,
)
from .rentals import book_order, cancel_rental
from .roles import OPERATOR_GROUP
from .schedule_changes import (
    preview_rental_change,
    request_rental_change,
    review_rental_change,
)
from .services import pick_up_rental, prepare_asset, receive_asset
from .test_finance import fund_rental


def operator():
    staff = get_user_model().objects.create_user("schedule-staff", is_staff=True)
    group, _ = Group.objects.get_or_create(name=OPERATOR_GROUP)
    group.permissions.add(
        Permission.objects.get(
            content_type__app_label="catalog", codename="operate_rentals"
        )
    )
    staff.groups.add(group)
    return staff


def tracked_item(code, rate):
    item = Equipment.objects.create(
        code=code, name=code, daily_rate_vnd=rate, total_stock=1, tracks_assets=True
    )
    AssetUnit.objects.create(equipment=item, code=f"{code}-1")
    return item


def book(customer, start, end, *items):
    return book_order(
        customer,
        start,
        end,
        [{"equipment_id": item.pk, "quantity": 1} for item in items],
    )


class RentalChangeTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user("schedule-customer")
        self.staff = operator()
        self.camera = tracked_item("CAM-EDIT", 120_000)
        self.lens = tracked_item("LEN-EDIT", 80_000)
        self.start = timezone.localdate()
        self.end = self.start + timedelta(days=2)
        self.rental = book(self.customer, self.start, self.end, self.camera, self.lens)
        self.target_start = self.end
        self.target_end = self.target_start + timedelta(days=3)

    def propose(self, start=None, end=None, accepted=600_000):
        return request_rental_change(
            self.customer,
            self.rental.pk,
            RentalChangeRequest.Kind.RESCHEDULE,
            start or self.target_start,
            end or self.target_end,
            accepted,
        )

    def test_repricing_uses_original_rates_and_preserves_reservation_history(self):
        Equipment.objects.filter(pk=self.camera.pk).update(daily_rate_vnd=900_000)
        quote = preview_rental_change(
            self.customer,
            self.rental.pk,
            RentalChangeRequest.Kind.RESCHEDULE,
            self.target_start,
            self.target_end,
        )
        self.assertEqual(quote["total_vnd"], 600_000)
        self.assertTrue(quote["consent_required"])
        self.assertFalse(RentalChangeRequest.objects.exists())
        with self.assertRaises(RentalError):
            self.propose(accepted=None)
        with self.assertRaises(RentalError):
            self.propose(accepted=2_940_000)

        change = self.propose()
        unauthorized = get_user_model().objects.create_user(
            "other-staff", is_staff=True
        )
        with self.assertRaisesMessage(RentalError, "Chỉ nhân viên có quyền vận hành"):
            review_rental_change(unauthorized, change.pk, True)
        result = review_rental_change(self.staff, change.pk, True, "Đã kiểm lịch")
        self.assertEqual(result.status, RentalChangeRequest.Status.APPROVED)
        self.assertEqual(result.reviewed_by_id, self.staff.pk)
        self.assertEqual(result.old_total_vnd, 400_000)
        self.rental.refresh_from_db()
        self.assertEqual(
            (self.rental.pickup_date, self.rental.return_date, self.rental.total_vnd),
            (self.target_start, self.target_end, 600_000),
        )
        self.assertEqual(
            list(
                self.rental.lines.order_by("daily_rate_vnd").values_list(
                    "total_vnd", flat=True
                )
            ),
            [240_000, 360_000],
        )
        replacements = AssetReservation.objects.filter(
            line__rental=self.rental, released_at__isnull=True
        ).select_related("replaces")
        self.assertEqual(replacements.count(), 2)
        for hold in replacements:
            self.assertEqual(hold.changed_by_id, self.staff.pk)
            self.assertEqual(
                (hold.period.lower, hold.period.upper),
                (self.target_start, self.target_end),
            )
            self.assertEqual(
                (hold.replaces.period.lower, hold.replaces.period.upper),
                (self.start, self.end),
            )
            self.assertIsNotNone(hold.replaces.released_at)

    def test_stock_conflict_leaves_all_lines_reservations_and_price_intact(self):
        change = self.propose()
        book(self.customer, self.target_start, self.target_end, self.lens)
        prior = list(
            AssetReservation.objects.filter(line__rental=self.rental).values_list(
                "id", "period", "released_at"
            )
        )
        with self.assertRaisesMessage(RentalError, "Không đủ thiết bị cho kỳ mới"):
            review_rental_change(self.staff, change.pk, True)
        change.refresh_from_db()
        self.rental.refresh_from_db()
        self.assertEqual(change.status, RentalChangeRequest.Status.PENDING)
        self.assertEqual(
            (self.rental.pickup_date, self.rental.total_vnd), (self.start, 400_000)
        )
        self.assertEqual(
            list(
                AssetReservation.objects.filter(line__rental=self.rental).values_list(
                    "id", "period", "released_at"
                )
            ),
            prior,
        )

    def test_stale_reviews_never_overwrite_an_approved_change(self):
        other = get_user_model().objects.create_user("schedule-other")
        with self.assertRaises(Rental.DoesNotExist):
            preview_rental_change(
                other,
                self.rental.pk,
                RentalChangeRequest.Kind.RESCHEDULE,
                self.target_start,
                self.target_end,
            )
        first = self.propose()
        stale = self.propose(
            self.target_start + timedelta(days=1),
            self.target_end + timedelta(days=1),
        )
        review_rental_change(self.staff, first.pk, True)
        with self.assertRaisesMessage(RentalError, "Kỳ thuê hoặc giá đã thay đổi"):
            review_rental_change(self.staff, stale.pk, True)
        rejected = review_rental_change(self.staff, stale.pk, False, "Kỳ đã thay đổi")
        self.assertEqual(rejected.status, RentalChangeRequest.Status.REJECTED)
        with self.assertRaisesMessage(RentalError, "Yêu cầu đã được xử lý"):
            review_rental_change(self.staff, stale.pk, False)

    def test_extension_keeps_custody_and_denies_partial_return(self):
        holds = list(
            AssetReservation.objects.filter(line__rental=self.rental).order_by("pk")
        )
        for hold in holds:
            prepare_asset(self.staff, self.rental.pk, hold.pk)
        fund_rental(self.rental, self.staff)
        pick_up_rental(self.staff, self.rental.pk)
        first_handover = AssetHandover.objects.get(reservation=holds[0])
        actual_pickup = first_handover.picked_up_at

        kind = RentalChangeRequest.Kind.EXTEND
        new_end = self.end + timedelta(days=1)
        change = request_rental_change(
            self.customer, self.rental.pk, kind, self.start, new_end, 600_000
        )
        conflict = book(self.customer, self.end, new_end, self.lens)
        with self.assertRaisesMessage(RentalError, "có lịch xung đột"):
            review_rental_change(self.staff, change.pk, True)
        self.rental.refresh_from_db()
        self.assertEqual(self.rental.return_date, self.end)
        cancel_rental(self.customer, conflict.pk)
        review_rental_change(self.staff, change.pk, True)
        self.rental.refresh_from_db()
        self.assertEqual(
            (self.rental.return_date, self.rental.total_vnd), (new_end, 600_000)
        )
        self.assertEqual(
            AssetHandover.objects.get(reservation=holds[0]).picked_up_at, actual_pickup
        )

        change = request_rental_change(
            self.customer,
            self.rental.pk,
            kind,
            self.start,
            new_end + timedelta(days=1),
            800_000,
        )
        receive_asset(self.staff, self.rental.pk, first_handover.pk)
        with self.assertRaisesMessage(RentalError, "đã trả hoặc đóng ngoại lệ"):
            review_rental_change(self.staff, change.pk, True)
        for hold in holds:
            hold.refresh_from_db()
            self.assertEqual(hold.period.upper, new_end)


class RentalChangeConcurrencyTests(TransactionTestCase):
    def test_booking_and_reschedule_cannot_both_win_the_last_asset(self):
        self.assertEqual(connection.vendor, "postgresql")
        staff = operator()
        customer = get_user_model().objects.create_user("schedule-race-customer")
        camera = tracked_item("CAM-CHANGE-RACE", 100_000)
        lens = tracked_item("LEN-CHANGE-RACE", 100_000)
        start = timezone.localdate()
        end = start + timedelta(days=1)
        requested_end = end + timedelta(days=1)
        rental = book(customer, start, end, camera, lens)
        change = request_rental_change(
            customer, rental.pk, RentalChangeRequest.Kind.RESCHEDULE, end, requested_end
        )
        barrier = Barrier(2, timeout=10)

        def race(operation):
            try:
                barrier.wait()
                operation()
            except RentalError as error:
                return error.status
            else:
                return 200
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(
                pool.map(
                    race,
                    (
                        lambda: review_rental_change(staff, change.pk, True),
                        lambda: book(customer, end, requested_end, lens, camera),
                    ),
                )
            )
        self.assertCountEqual(statuses, [200, 409])
        self.assertEqual(
            AssetReservation.objects.filter(
                released_at__isnull=True, period__overlap=(end, requested_end)
            ).count(),
            2,
        )
