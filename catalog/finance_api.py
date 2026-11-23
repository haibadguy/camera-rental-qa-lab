from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import Equipment, FinanceCharge, FinanceEntry
from .operations_api import _operation, _validated


class CanRecordFinance(BasePermission):
    def has_permission(self, request, view):
        return services.can_record_finance(request.user)


class CanManageFinance(BasePermission):
    def has_permission(self, request, view):
        return services.can_manage_finance(request.user)


class EntryInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=FinanceEntry.Kind.choices)
    command_id = serializers.UUIDField()
    amount_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, min_value=1, required=False
    )
    method = serializers.ChoiceField(
        choices=FinanceEntry.Method.choices, required=False
    )
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    charge_id = serializers.IntegerField(min_value=1, required=False)
    entry_id = serializers.IntegerField(min_value=1, required=False)


class ChargeInput(serializers.Serializer):
    command_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=FinanceCharge.Reason.choices)
    amount_vnd = serializers.DecimalField(max_digits=26, decimal_places=0, min_value=1)
    notes = serializers.CharField(max_length=2000)
    handover_id = serializers.IntegerField(min_value=1, required=False)


class ReviewInput(serializers.Serializer):
    approve = serializers.BooleanField()
    notes = serializers.CharField(max_length=2000)


class DepositInput(serializers.Serializer):
    amount_vnd = serializers.IntegerField(min_value=0, max_value=2_147_483_647)


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = ("id", "deposit_vnd")


class EntrySerializer(serializers.ModelSerializer):
    amount_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )
    recorded_by = serializers.CharField(source="recorded_by.username")

    class Meta:
        model = FinanceEntry
        fields = (
            "id",
            "kind",
            "amount_vnd",
            "method",
            "notes",
            "charge_id",
            "reverses_id",
            "recorded_at",
            "recorded_by",
            "command_id",
        )


class ChargeSerializer(serializers.ModelSerializer):
    amount_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )
    proposed_by = serializers.CharField(source="proposed_by.username")
    reviewed_by = serializers.CharField(source="reviewed_by.username", allow_null=True)

    class Meta:
        model = FinanceCharge
        fields = (
            "id",
            "reason",
            "amount_vnd",
            "notes",
            "handover_id",
            "incident_id",
            "status",
            "proposed_at",
            "proposed_by",
            "reviewed_at",
            "reviewed_by",
            "review_note",
        )


def _summary_data(summary):
    return {
        key: str(value) if key.endswith("_vnd") else value
        for key, value in summary.items()
    }


class LedgerSerializer(serializers.BaseSerializer):
    def to_representation(self, workspace):
        return {
            "summary": _summary_data(workspace["summary"]),
            "entries": EntrySerializer(workspace["entries"], many=True).data,
            "charges": ChargeSerializer(workspace["charges"], many=True).data,
        }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_summary(request, rental_id):
    rental = get_object_or_404(services.customer_rentals(request.user), pk=rental_id)
    return Response(_summary_data(services.finance_summary(rental)))


@api_view(["GET"])
@permission_classes([CanRecordFinance])
def ledger(request, rental_id):
    return _operation(
        services.finance_workspace, request.user, rental_id, serializer=LedgerSerializer
    )


@api_view(["POST"])
@permission_classes([CanRecordFinance])
def entry(request, rental_id):
    return _operation(
        services.post_finance_entry,
        request.user,
        rental_id,
        serializer=EntrySerializer,
        status=201,
        **_validated(EntryInput, request),
    )


@api_view(["POST"])
@permission_classes([CanRecordFinance])
def propose_charge(request, rental_id):
    return _operation(
        services.propose_finance_charge,
        request.user,
        rental_id,
        serializer=ChargeSerializer,
        status=201,
        **_validated(ChargeInput, request),
    )


@api_view(["POST"])
@permission_classes([CanManageFinance])
def review_charge(request, rental_id, charge_id):
    return _operation(
        services.review_finance_charge,
        request.user,
        rental_id,
        charge_id,
        serializer=ChargeSerializer,
        **_validated(ReviewInput, request),
    )


@api_view(["POST"])
@permission_classes([CanManageFinance])
def equipment_deposit(request, equipment_id):
    return _operation(
        services.set_equipment_deposit,
        request.user,
        equipment_id,
        serializer=DepositSerializer,
        **_validated(DepositInput, request),
    )
