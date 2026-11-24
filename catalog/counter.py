from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction

from .custody import lock_rental, prepare_locked, receive_locked, sync_rental_return
from .errors import RentalError
from .models import AssetReservation, CounterCommand, Rental
from .rentals import book_order
from .roles import can_book_for_customer, can_operate

MAX_SCAN_CODES = 30


def _command(actor, command_id, action, payload):
    try:
        command_id = UUID(str(command_id))
    except (ValueError, TypeError) as error:
        raise RentalError("Mã yêu cầu không hợp lệ.") from error
    command, new = CounterCommand.objects.get_or_create(
        actor=actor, command_id=command_id, defaults={"action": action, "payload": payload}
    )
    if not new and (command.action != action or command.payload != payload):
        raise RentalError("Mã yêu cầu đã được dùng cho thao tác khác.", 409)
    return command, new


@transaction.atomic
def book_for_customer(actor, username, pickup_date, return_date, lines, command_id):
    if not can_book_for_customer(actor):
        raise RentalError("Cần quyền tạo đơn hộ khách.", 403)
    payload = {
        "username": username, "pickup_date": pickup_date.isoformat(),
        "return_date": return_date.isoformat(),
        "lines": sorted(lines, key=lambda line: line["equipment_id"]),
    }
    command, new = _command(actor, command_id, CounterCommand.Action.BOOK, payload)
    if not new:
        return command.rental
    customer = get_user_model().objects.filter(
        username=username, is_active=True, is_staff=False, is_superuser=False
    ).first()
    if customer is None:
        raise RentalError("Không tìm thấy tài khoản khách đang hoạt động.", 404)
    command.rental = book_order(customer, pickup_date, return_date, lines)
    command.save(update_fields=["rental"])
    return command.rental


@transaction.atomic
def scan_assets(actor, rental_id, action, codes, command_id):
    if not can_operate(actor):
        raise RentalError("Cần quyền vận hành cho thuê.", 403)
    if action not in (CounterCommand.Action.PREPARE, CounterCommand.Action.RECEIVE):
        raise RentalError("Chọn thao tác chuẩn bị hoặc nhận trả.")
    if not isinstance(codes, (list, tuple)) or not 1 <= len(codes) <= MAX_SCAN_CODES:
        raise RentalError("Nhập từ 1 đến 30 mã kho.")
    if any(not isinstance(code, str) or not 1 <= len(code.strip()) <= 48 for code in codes):
        raise RentalError("Mã kho không hợp lệ.")
    codes = [code.strip() for code in codes]
    if len(codes) != len(set(codes)):
        raise RentalError("Có mã kho trùng trong lượt quét.")
    command, new = _command(
        actor, command_id, action, {"rental_id": rental_id, "codes": sorted(codes)}
    )
    if not new:
        return command

    rental, _ = lock_rental(Rental.objects.all(), rental_id)
    reservations = {
        hold.asset.code: hold
        for hold in AssetReservation.objects.filter(
            line__rental=rental, released_at__isnull=True, asset__code__in=codes
        ).select_related("asset", "line__equipment", "handover")
    }
    for code in codes:
        hold = reservations.get(code)
        if hold is None:
            raise RentalError(f"Mã {code} không thuộc lượt giữ đang dùng của đơn.", 409)
        if action == CounterCommand.Action.PREPARE:
            prepare_locked(actor, rental, hold)
        else:
            handover = getattr(hold, "handover", None)
            if handover is None:
                raise RentalError(f"Mã {code} chưa được bàn giao.", 409)
            receive_locked(actor, rental, handover)
    if action == CounterCommand.Action.RECEIVE:
        sync_rental_return(rental)
    command.rental = rental
    command.save(update_fields=["rental"])
    return command
