from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from . import services
from .models import AssetHandover, Equipment


class ReportPeriodForm(forms.Form):
    first = forms.DateField(
        label="Từ ngày",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    last = forms.DateField(
        label="Đến ngày",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )


class OpenStocktakeForm(forms.Form):
    equipment = forms.ModelChoiceField(
        label="Mẫu thiết bị",
        queryset=Equipment.objects.filter(tracks_assets=True),
    )


class MovementChoice(forms.ModelChoiceField):
    def label_from_instance(self, handover):
        return f"#{handover.pk} · {handover.asset.code} · Đơn #{handover.reservation.line.rental_id}"


class ObservationForm(forms.Form):
    code = forms.CharField(label="Mã kho", max_length=48)
    observed = forms.ChoiceField(
        label="Tình trạng đối chiếu", choices=services.OBSERVATIONS
    )
    movement = MovementChoice(
        label="Lượt giao nhận liên quan",
        queryset=AssetHandover.objects.none(),
        required=False,
    )
    notes = forms.CharField(label="Ghi chú", required=False, max_length=2000)


class ResolutionForm(forms.Form):
    line_id = forms.IntegerField(min_value=1)
    notes = forms.CharField(max_length=2000)


def _require(permission, actor):
    if not permission(actor):
        raise PermissionDenied


@login_required
@require_safe
def reports(request):
    _require(services.can_manage_reporting, request.user)
    today = timezone.localdate()
    values = (
        request.GET
        if "first" in request.GET or "last" in request.GET
        else {
            "first": today.replace(day=1).isoformat(),
            "last": today.isoformat(),
        }
    )
    form = ReportPeriodForm(values)
    context = {"form": form}
    if form.is_valid():
        try:
            report = services.rental_report(request.user, **form.cleaned_data)
        except services.RentalError as error:
            form.add_error(None, str(error))
        else:
            context.update(
                {
                    "report": report,
                    "entries": Paginator(report["entries"], 15).get_page(
                        request.GET.get("cash_page")
                    ),
                    "orders": Paginator(report["orders"], 15).get_page(
                        request.GET.get("order_page")
                    ),
                    "areas": Paginator(report["usage"]["rows"], 20).get_page(
                        request.GET.get("usage_page")
                    ),
                }
            )
    return render(
        request,
        "catalog/manager/reports.html",
        context,
        status=400 if form.errors else 200,
    )


@login_required
@require_safe
def audit(request, rental_id):
    _require(services.can_manage_reporting, request.user)
    try:
        context = services.rental_audit(request.user, rental_id)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    return render(request, "catalog/manager/rental_audit.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def stocktakes(request):
    _require(services.can_count_stock, request.user)
    sessions = services.stocktake_history(request.user)
    form = OpenStocktakeForm(
        request.POST if request.method == "POST" else None,
        initial={"equipment": request.GET.get("equipment")},
    )
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                stocktake = services.open_stocktake(
                    request.user, form.cleaned_data["equipment"].pk
                )
            except ObjectDoesNotExist as error:
                raise Http404 from error
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
            else:
                messages.success(request, "Đã mở phiên và ghi nhận tình trạng kỳ vọng.")
                return redirect("stocktake-detail", stocktake_id=stocktake.pk)
    page = Paginator(sessions, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/staff/stocktakes.html",
        {"form": form, "page": page},
        status=status,
    )


def _apply_stocktake_action(request, stocktake_id, action, form):
    if action == "record":
        if not form.is_valid():
            raise services.RentalError(
                "Kiểm tra mã kho, tình trạng và giao nhận liên quan."
            )
        values = form.cleaned_data
        movement = values.pop("movement")
        services.record_stocktake_line(
            request.user,
            stocktake_id,
            **values,
            movement_id=movement.pk if movement else None,
        )
    elif action == "resolve":
        decision = ResolutionForm(request.POST)
        if not decision.is_valid():
            raise services.RentalError("Chọn dòng chênh lệch và ghi lý do.")
        services.resolve_stocktake_line(
            request.user, stocktake_id, **decision.cleaned_data
        )
    elif action == "close":
        services.close_stocktake(request.user, stocktake_id)
    else:
        raise services.RentalError("Chọn thao tác kiểm kê hợp lệ.")


@login_required
@require_http_methods(["GET", "POST"])
def stocktake(request, stocktake_id):
    _require(services.can_count_stock, request.user)
    try:
        context = services.stocktake_detail(request.user, stocktake_id)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    action = request.POST.get("action")
    form = ObservationForm(
        request.POST if action == "record" else None,
        initial={"code": request.GET.get("code")},
    )
    form.fields["movement"].queryset = context["movements"]
    status = 200
    if request.method == "POST":
        try:
            _apply_stocktake_action(request, stocktake_id, action, form)
        except ObjectDoesNotExist as error:
            raise Http404 from error
        except services.RentalError as error:
            if error.status == 403:
                raise PermissionDenied from error
            context["error"] = str(error)
            status = error.status
        else:
            messages.success(request, "Đã cập nhật phiên kiểm kê.")
            return redirect("stocktake-detail", stocktake_id=stocktake_id)
    context["form"] = form
    return render(request, "catalog/staff/stocktake.html", context, status=status)
