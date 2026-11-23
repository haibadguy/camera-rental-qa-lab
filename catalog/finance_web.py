from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import services
from .models import Equipment, FinanceCharge, FinanceEntry, Rental

Kind = FinanceEntry.Kind


class CommandForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)


class CashForm(CommandForm):
    kind = forms.ChoiceField(label="Giao dịch")
    amount_vnd = forms.DecimalField(
        label="Số tiền (₫)", max_digits=26, decimal_places=0, min_value=1
    )
    method = forms.ChoiceField(label="Hình thức", choices=FinanceEntry.Method.choices)
    notes = forms.CharField(
        label="Ghi chú hoặc chứng từ", max_length=2000, required=False
    )


class ChargeForm(CommandForm):
    reason = forms.ChoiceField(label="Lý do", choices=FinanceCharge.Reason.choices)
    handover_id = forms.ChoiceField(
        label="Mã kho liên quan", required=False, choices=()
    )
    amount_vnd = forms.DecimalField(
        label="Số tiền đề xuất (₫)", max_digits=26, decimal_places=0, min_value=1
    )
    notes = forms.CharField(
        label="Căn cứ và lý do",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean_handover_id(self):
        value = self.cleaned_data["handover_id"]
        return int(value) if value else None


class AdjustmentForm(CommandForm):
    kind = forms.ChoiceField(
        label="Xử lý",
        choices=(
            (Kind.DEPOSIT_APPLIED, Kind.DEPOSIT_APPLIED.label),
            (Kind.WAIVER, Kind.WAIVER.label),
        ),
    )
    charge_id = forms.TypedChoiceField(
        label="Khoản thu đã duyệt", choices=(), coerce=int
    )
    amount_vnd = forms.DecimalField(
        label="Số tiền (₫)", max_digits=26, decimal_places=0, min_value=1
    )
    notes = forms.CharField(label="Lý do", max_length=2000)


class ReversalForm(CommandForm):
    entry_id = forms.TypedChoiceField(label="Giao dịch gốc", choices=(), coerce=int)
    notes = forms.CharField(label="Lý do đảo giao dịch", max_length=2000)


class ReconcileForm(CommandForm):
    notes = forms.CharField(label="Căn cứ đối soát", max_length=2000)


class ReviewChargeForm(forms.Form):
    decision = forms.ChoiceField(choices=(("approve", "Duyệt"), ("reject", "Từ chối")))
    notes = forms.CharField(max_length=2000)


class EquipmentDepositForm(forms.Form):
    amount_vnd = forms.IntegerField(
        label="Cọc mỗi thiết bị (₫)", min_value=0, max_value=2_147_483_647
    )


def _workspace(actor, rental_id):
    try:
        return services.finance_workspace(actor, rental_id)
    except Rental.DoesNotExist as error:
        raise Http404 from error
    except services.RentalError as error:
        if error.status == 403:
            raise PermissionDenied from error
        raise


def _forms(workspace, manager, action=None, data=None):
    def bind(form_class, key):
        return form_class(data if action == key else None, prefix=key)

    summary = workspace["summary"]
    rental = workspace["rental"]
    choices = []
    if rental.finance_enabled:
        if summary["balance_due_vnd"]:
            choices.append(Kind.RENT_RECEIPT)
        if summary["deposit_due_vnd"]:
            choices.append(Kind.DEPOSIT_RECEIPT)
    elif manager:
        choices.extend((Kind.RENT_RECEIPT, Kind.DEPOSIT_RECEIPT))
    if summary["can_settle"]:
        if summary["rent_to_refund_vnd"]:
            choices.append(Kind.RENT_REFUND)
        if summary["deposit_to_refund_vnd"]:
            choices.append(Kind.DEPOSIT_REFUND)
    # On a repeated submission the previous write may already have cleared the balance.
    # The service validates the command against the journal under lock.
    if action == "cash":
        choices = [
            Kind.RENT_RECEIPT,
            Kind.DEPOSIT_RECEIPT,
            Kind.RENT_REFUND,
            Kind.DEPOSIT_REFUND,
        ]
    result = {}
    if choices:
        cash = bind(CashForm, "cash")
        cash.fields["kind"].choices = [(kind, kind.label) for kind in choices]
        result["cash"] = cash
    if rental.picked_up_at:
        charge = bind(ChargeForm, "charge")
        charge.fields["handover_id"].choices = [("", "Đơn bàn giao nguyên đơn")] + [
            (handover.pk, handover.asset.code) for handover in workspace["handovers"]
        ]
        result["charge"] = charge
    if manager:
        approved = [
            (charge.pk, f"#{charge.pk} · {charge.get_reason_display()}")
            for charge in workspace["charges"]
            if charge.status == FinanceCharge.Status.APPROVED
        ]
        if approved:
            adjust = bind(AdjustmentForm, "adjust")
            adjust.fields["charge_id"].choices = approved
            result["adjust"] = adjust
        if workspace["reversible"] or action == "reverse":
            reverse = bind(ReversalForm, "reverse")
            entries = (
                workspace["entries"] if action == "reverse" else workspace["reversible"]
            )
            reverse.fields["entry_id"].choices = [
                (entry.pk, f"#{entry.pk} · {entry.get_kind_display()}")
                for entry in entries
            ]
            result["reverse"] = reverse
        if summary["legacy_pending"] or action == "reconcile":
            result["reconcile"] = bind(ReconcileForm, "reconcile")
    return result


def _move_money(actor, rental_id, action, values):
    if action == "charge":
        return services.propose_finance_charge(actor, rental_id, **values)
    if action == "reverse":
        values["kind"] = Kind.REVERSAL
    elif action == "reconcile":
        values["kind"] = Kind.RECONCILIATION
    return services.post_finance_entry(actor, rental_id, **values)


@login_required
@require_http_methods(["GET", "POST"])
def ledger(request, rental_id):
    workspace = _workspace(request.user, rental_id)
    manager = services.can_manage_finance(request.user)
    action = request.POST.get("action")
    status = 200
    form_set = _forms(workspace, manager, action, request.POST)
    error = ""
    if request.method == "POST":
        status = 400
        if action in ("adjust", "reverse", "reconcile") and not manager:
            raise PermissionDenied
        form = form_set.get(action)
        if form is None:
            error = "Chọn thao tác quyết toán hợp lệ."
        elif form.is_valid():
            try:
                _move_money(request.user, rental_id, action, form.cleaned_data)
            except ObjectDoesNotExist as missing:
                raise Http404 from missing
            except services.RentalError as failure:
                form.add_error(None, str(failure))
                status = failure.status
            else:
                messages.success(request, "Đã ghi nhận quyết toán.")
                return redirect("finance-ledger", rental_id=rental_id)
    return render(
        request,
        "catalog/staff/finance_ledger.html",
        {
            **workspace,
            "form_set": form_set,
            "active_action": action,
            "manager": manager,
            "error": error,
        },
        status=status,
    )


@login_required
@require_POST
def review_charge(request, rental_id, charge_id):
    if not services.can_manage_finance(request.user):
        raise PermissionDenied
    form = ReviewChargeForm(request.POST)
    if form.is_valid():
        try:
            services.review_finance_charge(
                request.user,
                rental_id,
                charge_id,
                approve=form.cleaned_data["decision"] == "approve",
                notes=form.cleaned_data["notes"],
            )
        except ObjectDoesNotExist as error:
            raise Http404 from error
        except services.RentalError as failure:
            messages.error(request, str(failure))
        else:
            messages.success(request, "Đã xử lý khoản thu đề xuất.")
    else:
        messages.error(request, "Chọn quyết định và ghi lý do tối đa 2.000 ký tự.")
    return redirect("finance-ledger", rental_id=rental_id)


@login_required
@require_http_methods(["GET", "POST"])
def equipment_deposit(request, equipment_id):
    if not services.can_manage_finance(request.user):
        raise PermissionDenied
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    form = EquipmentDepositForm(
        request.POST if request.method == "POST" else None,
        initial={"amount_vnd": equipment.deposit_vnd},
    )
    if form.is_valid():
        try:
            services.set_equipment_deposit(
                request.user, equipment_id, **form.cleaned_data
            )
        except Equipment.DoesNotExist as error:
            raise Http404 from error
        messages.success(request, "Đã cập nhật cọc cho đơn đặt mới.")
        return redirect("finance-deposit", equipment_id=equipment_id)
    return render(
        request,
        "catalog/staff/finance_deposit.html",
        {
            "equipment": equipment,
            "form": form,
        },
        status=400 if request.method == "POST" else 200,
    )
