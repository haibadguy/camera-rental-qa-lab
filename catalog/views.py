from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)

from . import services
from .forms import (
    AssetForm,
    BookingForm,
    CatalogFilterForm,
    EquipmentForm,
    OrderForm,
    PeriodForm,
)
from .models import AssetReservation, Equipment, Rental


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("equipment-list")
    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            if (
                not get_user_model()
                .objects.filter(username=form.cleaned_data["username"])
                .exists()
            ):
                raise
            form.add_error("username", "Tên đăng nhập đã được sử dụng.")
        else:
            messages.success(request, "Đã tạo tài khoản. Bạn có thể đăng nhập ngay.")
            next_url = request.GET.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(reverse("login", query={"next": next_url}))
            return redirect("login")
    return render(
        request,
        "catalog/form.html",
        {
            "title": "Đăng ký tài khoản khách hàng",
            "form": form,
            "submit_label": "Đăng ký",
        },
        status=400 if request.method == "POST" else 200,
    )


@require_safe
def equipment_list(request):
    form = CatalogFilterForm(request.GET or None)
    filters_are_valid = form.is_valid()
    filters = form.cleaned_data if form.is_bound else {}
    equipment = services.catalog_items(
        search=filters.get("search", ""),
        kind=filters.get("kind", ""),
        brand=filters.get("brand", ""),
    )
    if filters_are_valid:
        pickup, dropoff = filters["pickup_date"], filters["return_date"]
        if pickup and dropoff:
            try:
                availability = services.catalog_availability(equipment, pickup, dropoff)
            except services.RentalError as error:
                form.add_error(None, str(error))
            else:
                for item in equipment:
                    item.available_stock = availability[item.pk]
        elif pickup or dropoff:
            form.add_error(
                None, "Chọn cả ngày nhận và ngày trả để kiểm tra lịch trống."
            )
    return render(
        request,
        "catalog/equipment_list.html",
        {"equipment": equipment, "form": form, "brands": services.catalog_brands()},
    )


@require_safe
def equipment_detail(request, equipment_id):
    equipment = get_object_or_404(services.catalog_items(), pk=equipment_id)
    form = PeriodForm(request.GET or None)
    booking_url = reverse("book", args=[equipment.pk])
    availability = None
    if form.is_valid():
        try:
            availability = services.available_stock(equipment, **form.cleaned_data)
        except services.RentalError as error:
            form.add_error(None, str(error))
        else:
            booking_url += "?" + urlencode(form.cleaned_data)
    return render(
        request,
        "catalog/equipment_detail.html",
        {
            "item": equipment,
            "period_form": form,
            "availability": availability,
            "booking_url": booking_url,
            "rental_store": settings.RENTAL_STORE,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def book(request, equipment_id):
    equipment = get_object_or_404(services.catalog_items(), pk=equipment_id)
    initial_dates = {
        name: request.GET[name]
        for name in PeriodForm.base_fields
        if name in request.GET
    }
    form = BookingForm(
        request.POST if request.method == "POST" else None, initial=initial_dates
    )
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                rental = services.book_rental(
                    request.user, equipment.pk, **form.cleaned_data
                )
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                messages.success(request, "Đặt thuê thành công.")
                return redirect("rental-detail", rental_id=rental.pk)
    return render(
        request,
        "catalog/form.html",
        {
            "title": f"Đặt thuê {equipment.name}",
            "form": form,
            "submit_label": "Xác nhận đặt thuê",
            "booking_item": equipment,
            "rental_store": settings.RENTAL_STORE,
        },
        status=status,
    )


@login_required
@require_safe
def my_rentals(request):
    rentals = services.customer_rentals(request.user).prefetch_related(
        "lines__equipment"
    )
    return render(
        request,
        "catalog/rental_list.html",
        {"rentals": rentals, "title": "Đơn thuê của tôi"},
    )


def _rental_detail(request, rental, *, staff=False, error=None):
    today = timezone.localdate()
    handovers = services.rental_handovers(rental)
    item_pickup = bool(
        staff
        and rental.status == Rental.Status.CONFIRMED
        and rental.lines.filter(equipment__tracks_assets=True).exists()
    )
    item_return = bool(
        staff
        and rental.status == Rental.Status.PICKED_UP
        and handovers.filter(picked_up_at__isnull=False).exists()
    )
    context = {
        "rental": rental,
        "staff_view": staff,
        "can_cancel": not staff and services.can_cancel(rental, today),
        "can_pick_up": staff
        and not item_pickup
        and services.can_pick_up(rental, today),
        "can_mark_no_show": staff and services.can_mark_no_show(rental, today),
        "can_return": staff and not item_return and services.can_return(rental),
        "can_replace_asset": staff and services.can_replace_asset(rental, today),
        "error": error,
        "rental_store": settings.RENTAL_STORE,
    }
    if staff:
        context["asset_history"] = services.rental_asset_history(rental)
        context["show_operations"] = services.can_operate(request.user)
        context["requires_operations"] = item_pickup or item_return
    else:
        context["change_kind"] = services.change_kind(rental)
        context["changes"] = rental.changes.all()
        context["finance"] = services.finance_summary(rental)
        if rental.picked_up_at:
            context["receipt"] = services.receipt_summary(rental)
    return render(
        request,
        "catalog/rental_detail.html",
        context,
        status=error.status if error else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def book_order(request):
    equipment = list(services.catalog_items().filter(tracks_assets=True))
    initial = {
        key: request.GET[key] for key in PeriodForm.base_fields if key in request.GET
    }
    for item in equipment:
        if request.GET.get("equipment") == str(item.pk):
            initial[f"quantity_{item.pk}"] = 1
    form = OrderForm(
        request.POST if request.method == "POST" else None,
        equipment=equipment,
        initial=initial,
    )
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                rental = services.book_order(
                    request.user,
                    form.cleaned_data["pickup_date"],
                    form.cleaned_data["return_date"],
                    form.cleaned_data["lines"],
                )
            except Equipment.DoesNotExist:
                form.add_error(None, "Danh mục đã thay đổi. Chọn lại thiết bị.")
                status = 409
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                messages.success(request, "Đặt thuê thành công.")
                return redirect("rental-detail", rental_id=rental.pk)
    return render(
        request,
        "catalog/book_order.html",
        {
            "form": form,
            "rental_store": settings.RENTAL_STORE,
        },
        status=status,
    )


@login_required
@require_safe
def rental_detail(request, rental_id):
    return _rental_detail(
        request,
        get_object_or_404(services.customer_rentals(request.user), pk=rental_id),
    )


@login_required
@require_POST
def cancel(request, rental_id):
    try:
        services.cancel_rental(request.user, rental_id)
    except Rental.DoesNotExist as error:
        raise Http404 from error
    except services.RentalError as error:
        rental = get_object_or_404(
            services.customer_rentals(request.user), pk=rental_id
        )
        return _rental_detail(request, rental, error=error)
    messages.success(request, "Đã hủy đơn thuê.")
    return redirect("rental-detail", rental_id=rental_id)


@login_required
@require_safe
def staff_rentals(request):
    if not request.user.is_staff and not services.can_operate(request.user):
        raise PermissionDenied
    queues = services.StaffRentalQueue
    queue = request.GET.get("queue", queues.ALL)
    if queue not in queues.values:
        queue = queues.ALL
    return render(
        request,
        "catalog/rental_list.html",
        {
            "rentals": services.staff_rentals(queue),
            "title": "Quản lý đơn thuê",
            "staff_view": True,
            "queues": queues.choices,
            "active_queue": queue,
        },
    )


@login_required
@require_safe
def staff_rental_detail(request, rental_id):
    if not request.user.is_staff and not services.can_operate(request.user):
        raise PermissionDenied
    rental = get_object_or_404(
        Rental.objects.select_related("equipment", "customer"), pk=rental_id
    )
    return _rental_detail(request, rental, staff=True)


def _staff_rental_action(request, rental_id, operation):
    if not request.user.is_staff:
        raise PermissionDenied
    try:
        rental = operation(request.user, rental_id)
    except Rental.DoesNotExist as error:
        raise Http404 from error
    except services.RentalError as error:
        rental = get_object_or_404(Rental, pk=rental_id)
        return _rental_detail(request, rental, staff=True, error=error)
    messages.success(request, f"Đơn #{rental.pk}: {rental.get_status_display()}.")
    return redirect("staff-rental-detail", rental_id=rental_id)


@login_required
@require_POST
def pick_up(request, rental_id):
    return _staff_rental_action(request, rental_id, services.pick_up_rental)


@login_required
@require_POST
def no_show(request, rental_id):
    return _staff_rental_action(request, rental_id, services.mark_no_show)


@login_required
@require_POST
def record_return(request, rental_id):
    return _staff_rental_action(request, rental_id, services.return_rental)


@login_required
@require_POST
def replace_asset(request, rental_id, reservation_id):
    if not request.user.is_staff and not services.can_operate(request.user):
        raise PermissionDenied
    code = request.POST.get("replacement_code", "").strip()
    try:
        if not code or len(code) > 48:
            raise services.RentalError("Nhập mã kho hợp lệ.")
        services.replace_reserved_asset(request.user, rental_id, reservation_id, code)
    except (Rental.DoesNotExist, AssetReservation.DoesNotExist) as error:
        raise Http404 from error
    except services.RentalError as error:
        rental = get_object_or_404(Rental, pk=rental_id)
        return _rental_detail(request, rental, staff=True, error=error)
    messages.success(request, "Đã đổi thiết bị giữ cho đơn.")
    return redirect("staff-rental-detail", rental_id=rental_id)


@login_required
@require_http_methods(["GET", "POST"])
def staff_assets(request, equipment_id):
    if not request.user.is_staff:
        raise PermissionDenied
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    enabling = request.POST.get("action") == "enable"
    form = AssetForm(
        request.POST if request.method == "POST" and not enabling else None
    )
    status = 200
    activation_error = None
    if request.method == "POST":
        status = 400
        try:
            if enabling:
                services.enable_asset_tracking(request.user, equipment.pk)
                messages.success(request, "Đã bật giữ theo mã kho.")
                return redirect("staff-assets", equipment_id=equipment.pk)
            if form.is_valid():
                services.register_asset(request.user, equipment.pk, **form.cleaned_data)
                messages.success(request, "Đã đăng ký thiết bị vật lý.")
                return redirect("staff-assets", equipment_id=equipment.pk)
        except services.RentalError as error:
            if enabling:
                activation_error = str(error)
            else:
                form.add_error(None, str(error))
            status = error.status
    return render(
        request,
        "catalog/staff_assets.html",
        {
            "equipment": equipment,
            "form": form,
            "assets": equipment.assets.all(),
            "calendar": Paginator(services.asset_calendar(equipment), 30).get_page(
                request.GET.get("page")
            ),
            "unassigned": services.unassigned_legacy_rentals(equipment),
            "activation_error": activation_error,
        },
        status=status,
    )


@login_required
@require_safe
def staff_equipment(request):
    if not request.user.is_staff:
        raise PermissionDenied
    return render(
        request,
        "catalog/staff_equipment.html",
        {"equipment": services.equipment_with_physical_stock()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def manage_equipment(request, equipment_id=None):
    if not request.user.is_staff:
        raise PermissionDenied
    equipment = (
        get_object_or_404(Equipment, pk=equipment_id)
        if equipment_id is not None
        else None
    )
    form = EquipmentForm(
        request.POST if request.method == "POST" else None, instance=equipment
    )
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            values = form.cleaned_data.copy()
            try:
                if equipment is None:
                    services.create_equipment(request.user, **values)
                else:
                    del values["code"]
                    services.update_equipment(request.user, equipment.pk, **values)
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                messages.success(request, "Đã lưu thiết bị.")
                return redirect("staff-equipment")
    title = "Thêm thiết bị" if equipment is None else f"Sửa thiết bị {equipment.code}"
    return render(
        request, "catalog/form.html", {"title": title, "form": form}, status=status
    )
