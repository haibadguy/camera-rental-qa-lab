from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import services
from .models import CashShift


class OpenForm(forms.Form):
    opening_cash_vnd = forms.DecimalField(label="Tiền mặt đầu ca (₫)", max_digits=32, decimal_places=0, min_value=0)


class SubmitForm(forms.Form):
    counted_cash_vnd = forms.DecimalField(label="Tiền mặt đếm được (₫)", max_digits=32, decimal_places=0, min_value=0)
    confirmed_transfer_vnd = forms.DecimalField(label="Chuyển khoản ròng đối chiếu (₫)", max_digits=32, decimal_places=0)
    discrepancy_note = forms.CharField(label="Lý do chênh lệch", max_length=2000, required=False)


class CloseForm(forms.Form):
    resolution = forms.CharField(label="Cách xử lý chênh lệch", max_length=2000, required=False)


def _require_clerk(request):
    if not services.can_record_finance(request.user):
        raise PermissionDenied


@login_required
@require_http_methods(["GET", "POST"])
def shifts(request):
    _require_clerk(request)
    history = services.shift_history(request.user)
    active = history.filter(status=CashShift.Status.OPEN).first()
    form = OpenForm(request.POST if request.method == "POST" else None)
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                shift = services.open_shift(request.user, **form.cleaned_data)
            except services.RentalError as error:
                form.add_error(None, str(error))
                status = error.status
                active = history.filter(status=CashShift.Status.OPEN).first()
            else:
                return redirect("cash-shift-detail", shift_id=shift.pk)
    return render(request, "catalog/staff/cash_shifts.html", {
        "active": active, "form": form,
        "page": Paginator(history, 24).get_page(request.GET.get("page")),
    }, status=status)


@login_required
@require_http_methods(["GET", "POST"])
def shift_detail(request, shift_id):
    _require_clerk(request)
    try:
        shift, expected = services.cash_shift_detail(request.user, shift_id)
    except CashShift.DoesNotExist as error:
        raise Http404 from error
    manager = services.can_manage_finance(request.user)
    form = None
    operation = None
    if shift.status == CashShift.Status.OPEN:
        form, operation = SubmitForm, services.submit_shift
    elif shift.status == CashShift.Status.SUBMITTED and manager:
        form, operation = CloseForm, services.close_shift
    if request.method == "POST" and form is None:
        raise PermissionDenied
    bound = form(request.POST if request.method == "POST" else None) if form else None
    status = 200
    if request.method == "POST":
        status = 400
        if bound.is_valid():
            try:
                operation(request.user, shift.pk, **bound.cleaned_data)
            except services.RentalError as error:
                bound.add_error(None, str(error))
                status = error.status
            else:
                messages.success(request, "Đã cập nhật đối soát ca.")
                return redirect("cash-shift-detail", shift_id=shift.pk)
    entries = shift.entries.select_related("recorded_by", "reverses")
    return render(request, "catalog/staff/cash_shift.html", {
        "shift": shift, "expected": expected, "form": bound,
        "page": Paginator(entries, 24).get_page(request.GET.get("page")),
    }, status=status)
