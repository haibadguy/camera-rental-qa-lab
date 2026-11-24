from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)

from . import services
from .models import (
    AssetHandover,
    AssetUnit,
    MaintenanceCase,
    Rental,
    RentalChangeRequest,
)

OPERATION_QUEUES = (
    ("all", "Tất cả"),
    ("risk", "Nguy cơ thiếu thiết bị"),
    ("overdue", "Quá hạn"),
)


class ChangePeriodForm(forms.Form):
    kind = forms.ChoiceField(
        choices=RentalChangeRequest.Kind.choices, widget=forms.HiddenInput
    )
    pickup_date = forms.DateField(
        label="Ngày nhận",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    return_date = forms.DateField(
        label="Ngày trả",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )


class ChangeConfirmationForm(ChangePeriodForm):
    accepted_total_vnd = forms.DecimalField(
        min_value=0, max_digits=26, decimal_places=0, widget=forms.HiddenInput
    )


class ReviewChangeForm(forms.Form):
    decision = forms.ChoiceField(choices=(("approve", "Duyệt"), ("reject", "Từ chối")))
    review_note = forms.CharField(required=False, max_length=2000)


class HandoverActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=(
            ("prepare", "Chuẩn bị"),
            ("pick_up", "Bàn giao"),
            ("receive", "Nhận trả"),
            ("inspect", "Kiểm tra"),
            ("lost", "Báo mất"),
        )
    )
    item_id = forms.IntegerField(min_value=1, required=False)
    result = forms.ChoiceField(choices=AssetHandover.Inspection.choices, required=False)
    notes = forms.CharField(required=False, max_length=2000)

    def clean(self):
        values = super().clean()
        action = values.get("action")
        if action and action != "pick_up" and not values.get("item_id"):
            self.add_error("item_id", "Chọn thiết bị cần xử lý.")
        if action == "inspect" and not values.get("result"):
            self.add_error("result", "Chọn kết quả kiểm tra.")
        if action == "lost" and not values.get("notes"):
            self.add_error("notes", "Ghi thông tin về thiết bị chưa tìm thấy.")
        return values


class AssetMaintenanceForm(forms.Form):
    asset = forms.ModelChoiceField(
        label="Mã kho",
        queryset=AssetUnit.objects.filter(equipment__tracks_assets=True)
        .exclude(status=AssetUnit.Status.RETIRED)
        .select_related("equipment")
        .order_by("code"),
    )
    notes = forms.CharField(
        label="Ghi chú", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )


class PlanMaintenanceForm(AssetMaintenanceForm):
    pickup_date = forms.DateField(
        label="Ngày bắt đầu",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    return_date = forms.DateField(
        label="Ngày đưa về kho dự kiến",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    field_order = ["asset", "pickup_date", "return_date", "notes"]


class ReportIncidentForm(AssetMaintenanceForm):
    kind = forms.ChoiceField(
        label="Sự cố",
        choices=(
            (MaintenanceCase.Kind.DAMAGE, "Hỏng thiết bị"),
            (MaintenanceCase.Kind.MISSING_ACCESSORY, "Thiếu phụ kiện"),
            (MaintenanceCase.Kind.LOST, "Không tìm thấy thiết bị"),
        ),
    )
    field_order = ["asset", "kind", "notes"]


class MaintenanceActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=(("repair", "Ghi nhận sửa chữa"), ("resolve", "Kết thúc"))
    )
    resolution = forms.ChoiceField(
        choices=MaintenanceCase.Resolution.choices, required=False
    )
    notes = forms.CharField(max_length=2000)

    def clean(self):
        values = super().clean()
        if values.get("action") == "resolve" and not values.get("resolution"):
            self.add_error("resolution", "Chọn cách xử lý thiết bị.")
        return values


def _require_operator(user):
    if not services.can_operate(user):
        raise PermissionDenied


@login_required
@require_http_methods(["GET", "POST"])
def rental_change(request, rental_id):
    rental = get_object_or_404(services.customer_rentals(request.user), pk=rental_id)
    kind = services.change_kind(rental)
    if request.method == "GET" and kind is None:
        return redirect("rental-detail", rental_id=rental.pk)
    extending = rental.status == Rental.Status.PICKED_UP
    immutable_pickup = rental.pickup_date if extending else None
    data = request.POST if request.method == "POST" else None
    confirm = data is not None and data.get("action") == "send"
    form_class = ChangeConfirmationForm if confirm else ChangePeriodForm
    form = form_class(
        data,
        initial={
            "kind": kind,
            "pickup_date": rental.pickup_date,
            "return_date": rental.return_date,
        },
    )
    if extending:
        form.fields["pickup_date"].widget = forms.HiddenInput()
    quote = None
    status = 200
    period = None

    if request.method == "POST":
        status = 400
        if form.is_valid():
            period = form.cleaned_data
            try:
                if confirm:
                    services.request_rental_change(request.user, rental.pk, **period)
                else:
                    quote = services.preview_rental_change(
                        request.user, rental.pk, **period
                    )
            except ObjectDoesNotExist as error:
                raise Http404 from error
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                if confirm:
                    messages.success(
                        request,
                        "Đã gửi yêu cầu. Kỳ thuê hiện tại vẫn được giữ đến khi nhân viên duyệt.",
                    )
                    return redirect("rental-detail", rental_id=rental.pk)
                status = 200

    return render(
        request,
        "catalog/customer/rental_change.html",
        {
            "rental": rental,
            "form": form,
            "quote": quote,
            "period": period,
            "immutable_pickup": immutable_pickup,
            "extending": extending,
        },
        status=status,
    )


@login_required
@require_safe
def operations_queue(request):
    _require_operator(request.user)
    queue = request.GET.get("queue", "all")
    if queue not in dict(OPERATION_QUEUES):
        queue = "all"
    rentals = services.ops_rentals(request.user, queue)
    page = Paginator(rentals, 30).get_page(request.GET.get("page"))
    pending = RentalChangeRequest.objects.filter(
        status=RentalChangeRequest.Status.PENDING
    )
    pending = Paginator(pending.order_by("requested_at", "pk"), 15).get_page(
        request.GET.get("changes_page")
    )
    return render(
        request,
        "catalog/staff/operations_queue.html",
        {
            "page": page,
            "queues": OPERATION_QUEUES,
            "active_queue": queue,
            "pending_changes": pending,
        },
    )


def _handover_rows(rental):
    holds = services.rental_asset_history(rental).filter(released_at__isnull=True)
    holds = holds.select_related("asset__equipment", "handover")
    return [(hold, getattr(hold, "handover", None)) for hold in holds]


def _render_order(request, rental, *, error=None, status=200):
    rows = _handover_rows(rental)
    context = {
        "rental": rental,
        "rows": rows,
        "counter_booking": rental.counter_commands.filter(action="BOOK").select_related("actor").first(),
        "scan_form": ScanForm(
            request.POST if request.POST.get("action") == "scan" else None,
            initial={"mode": "PREPARE" if rental.status == Rental.Status.CONFIRMED else "RECEIVE"},
        ),
        "changes": rental.changes.select_related("reviewed_by"),
        "incidents": services.maintenance_cases(request.user).filter(
            handover__reservation__line__rental=rental
        ),
        "can_confirm_pickup": bool(rows)
        and services.can_pick_up(rental, timezone.localdate())
        and all(item and item.prepared_at for _, item in rows),
        "inspection_choices": AssetHandover.Inspection.choices,
        "error": error,
    }
    return render(
        request, "catalog/staff/operations_order.html", context, status=status
    )


class ScanForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    mode = forms.ChoiceField(label="Thao tác", choices=(("PREPARE", "Chuẩn bị"), ("RECEIVE", "Nhận trả")))
    codes = forms.CharField(
        label="Mã kho", max_length=1500,
        widget=forms.Textarea(attrs={"rows": 3, "data-scan-codes": "", "maxlength": 1500}),
    )

    def clean_codes(self):
        return [code.strip() for code in self.cleaned_data["codes"].splitlines() if code.strip()]


def _apply_handover(staff, rental, values):
    action = values["action"]
    item_id, notes = values["item_id"], values["notes"]
    if action == "prepare":
        services.prepare_asset(staff, rental.pk, item_id, notes)
        return "Đã xác nhận chuẩn bị thiết bị."
    if action == "pick_up":
        services.pick_up_rental(staff, rental.pk)
        return "Đã bàn giao toàn bộ thiết bị."
    if action == "receive":
        services.receive_asset(staff, rental.pk, item_id)
        return "Đã nhận thiết bị. Cần kiểm tra trước khi đưa về kho."
    if action == "inspect":
        services.inspect_asset(staff, rental.pk, item_id, values["result"], notes)
        return "Đã ghi kết quả kiểm tra."
    handover = get_object_or_404(services.rental_handovers(rental), pk=item_id)
    services.report_incident(
        staff, handover.asset_id, MaintenanceCase.Kind.LOST, notes, handover_id=item_id
    )
    return "Đã ghi sự cố để quản lý xử lý."


@login_required
@require_http_methods(["GET", "POST"])
def operations_order(request, rental_id):
    _require_operator(request.user)
    rental = get_object_or_404(Rental.objects.select_related("customer"), pk=rental_id)
    if request.method == "POST":
        if request.POST.get("action") == "scan":
            form = ScanForm(request.POST)
            if form.is_valid():
                values = form.cleaned_data
                try:
                    services.scan_assets(
                        request.user, rental.pk, values["mode"], values["codes"], values["command_id"]
                    )
                except services.RentalError as error:
                    return _render_order(request, rental, error=error, status=error.status)
                else:
                    messages.success(request, f"Đã ghi nhận {len(values['codes'])} mã kho.")
                    return redirect("operations-order", rental_id=rental.pk)
            return _render_order(request, rental, status=400)
        form = HandoverActionForm(request.POST)
        if not form.is_valid():
            return _render_order(
                request,
                rental,
                error="Kiểm tra thông tin thiết bị hoặc ghi chú.",
                status=400,
            )
        try:
            message = _apply_handover(request.user, rental, form.cleaned_data)
        except ObjectDoesNotExist as error:
            raise Http404 from error
        except services.RentalError as error:
            return _render_order(request, rental, error=error, status=error.status)
        messages.success(request, message)
        return redirect("operations-order", rental_id=rental.pk)
    return _render_order(request, rental)


@login_required
@require_POST
def review_change(request, rental_id, change_id):
    _require_operator(request.user)
    change = get_object_or_404(
        RentalChangeRequest.objects.select_related("rental"),
        pk=change_id,
        rental_id=rental_id,
    )
    form = ReviewChangeForm(request.POST)
    if not form.is_valid():
        return _render_order(
            request, change.rental, error="Kiểm tra lựa chọn và ghi chú.", status=400
        )
    values = form.cleaned_data
    try:
        services.review_rental_change(
            request.user,
            change.pk,
            values["decision"] == "approve",
            values["review_note"],
        )
    except ObjectDoesNotExist as error:
        raise Http404 from error
    except services.RentalError as error:
        return _render_order(request, change.rental, error=error, status=error.status)
    messages.success(request, "Đã xử lý yêu cầu thay đổi kỳ thuê.")
    return redirect("operations-order", rental_id=change.rental_id)


@login_required
@require_safe
def maintenance_list(request):
    _require_operator(request.user)
    cases = services.maintenance_cases(request.user)
    page = Paginator(cases, 30).get_page(request.GET.get("page"))
    return render(request, "catalog/staff/maintenance_list.html", {"page": page})


@login_required
@require_http_methods(["GET", "POST"])
def maintenance_new(request, *, planned=False):
    _require_operator(request.user)
    form_class = PlanMaintenanceForm if planned else ReportIncidentForm
    form = form_class(
        request.POST if request.method == "POST" else None,
        initial={"asset": request.GET.get("asset")},
    )
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            values = form.cleaned_data
            asset = values["asset"]
            try:
                if planned:
                    case = services.plan_maintenance(
                        request.user,
                        asset.pk,
                        values["pickup_date"],
                        values["return_date"],
                        values["notes"],
                    )
                else:
                    case = services.report_incident(
                        request.user, asset.pk, values["kind"], values["notes"]
                    )
            except ObjectDoesNotExist as error:
                raise Http404 from error
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                messages.success(
                    request,
                    "Đã ghi lịch bảo trì." if planned else "Đã ghi sự cố thiết bị.",
                )
                return redirect("maintenance-detail", case_id=case.pk)
    return render(
        request,
        "catalog/staff/maintenance_new.html",
        {"form": form, "planned": planned},
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def maintenance_detail(request, case_id):
    _require_operator(request.user)
    case = get_object_or_404(services.maintenance_cases(request.user), pk=case_id)
    manager = services.can_manage(request.user)
    photo_form = PhotoForm(
        request.POST if request.POST.get("action") == "photo" else None,
        request.FILES if request.POST.get("action") == "photo" else None,
    )
    error = None
    status = 200
    if request.method == "POST" and request.POST.get("action") == "photo":
        status = 400
        if photo_form.is_valid():
            try:
                services.attach_photo(request.user, case.pk, **photo_form.cleaned_data)
            except services.RentalError as failure:
                error = failure
                status = failure.status
            else:
                messages.success(request, "Đã lưu ảnh sự cố.")
                return redirect("maintenance-detail", case_id=case.pk)
    elif request.method == "POST":
        form = MaintenanceActionForm(request.POST)
        if not form.is_valid():
            error = "Kiểm tra trạng thái và ghi chú xử lý."
            status = 400
        else:
            values = form.cleaned_data
            try:
                if values["action"] == "repair":
                    services.start_repair(request.user, case.pk, values["notes"])
                elif manager:
                    services.resolve_case(
                        request.user, case.pk, values["resolution"], values["notes"]
                    )
                else:
                    raise PermissionDenied
            except ObjectDoesNotExist as missing:
                raise Http404 from missing
            except services.RentalError as failure:
                error = failure
                status = failure.status
            else:
                messages.success(request, "Đã cập nhật hồ sơ thiết bị.")
                return redirect("maintenance-detail", case_id=case.pk)
    return render(
        request,
        "catalog/staff/maintenance_detail.html",
        {
            "case": case,
            "photo_form": photo_form if case.kind in services.PHOTO_KINDS else None,
            "photos": case.photos.filter(expires_at__gt=timezone.now(), deleted_at__isnull=True).select_related("uploaded_by"),
            "can_manage": manager,
            "resolution_choices": MaintenanceCase.Resolution.choices,
            "error": error,
        },
        status=status,
    )


class PhotoForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    upload = forms.FileField(
        label="Ảnh sự cố",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )


@login_required
@require_safe
def incident_photo(request, case_id, photo_id):
    _require_operator(request.user)
    try:
        photo = services.open_photo(request.user, case_id, photo_id)
    except (ObjectDoesNotExist, FileNotFoundError) as error:
        raise Http404 from error
    response = FileResponse(photo, content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response
