from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from . import services
from .api import OrderSerializer
from .finance_api import ChargeSerializer, EntrySerializer
from .models import Stocktake, StocktakeLine
from .operations_api import (
    HandoverSerializer,
    MaintenanceCaseSerializer,
    RentalChangeSerializer,
    StaffReservationSerializer,
    _operation,
    _validated,
)


class CanManageReporting(BasePermission):
    def has_permission(self, request, view):
        return services.can_manage_reporting(request.user)


class CanCountStock(BasePermission):
    def has_permission(self, request, view):
        return services.can_count_stock(request.user)


class PeriodInput(serializers.Serializer):
    first = serializers.DateField()
    last = serializers.DateField()


class OpenInput(serializers.Serializer):
    equipment_id = serializers.IntegerField(min_value=1)


class ObservationInput(serializers.Serializer):
    code = serializers.CharField(max_length=48)
    observed = serializers.ChoiceField(choices=services.OBSERVATIONS)
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    movement_id = serializers.IntegerField(min_value=1, required=False)


class ResolutionInput(serializers.Serializer):
    notes = serializers.CharField(max_length=2000)


class ReportSerializer(serializers.BaseSerializer):
    def to_representation(self, report):
        usage = report["usage"]
        return {
            "first": report["first"].isoformat(),
            "last": report["last"].isoformat(),
            "generated_at": report["generated_at"].isoformat(),
            "money": {
                key: str(value) if key.endswith("_vnd") else value
                for key, value in report["money"].items()
            },
            "counts": report["counts"],
            "outstanding": report["outstanding"],
            "usage": {key: value for key, value in usage.items() if key != "rows"},
            "stock": [
                {
                    "equipment_id": item.pk,
                    "code": item.code,
                    "available_now": item.available_now,
                    "outstanding": item.outstanding,
                }
                for item in report["stock"]
            ],
        }


class AuditSerializer(serializers.BaseSerializer):
    def to_representation(self, audit):
        return {
            "rental": OrderSerializer(audit["rental"]).data,
            "assignments": StaffReservationSerializer(
                audit["assignments"], many=True
            ).data,
            "handovers": HandoverSerializer(audit["handovers"], many=True).data,
            "changes": RentalChangeSerializer(audit["changes"], many=True).data,
            "incidents": MaintenanceCaseSerializer(audit["incidents"], many=True).data,
            "entries": EntrySerializer(audit["entries"], many=True).data,
            "charges": ChargeSerializer(audit["charges"], many=True).data,
        }


class StocktakeSerializer(serializers.ModelSerializer):
    equipment_id = serializers.IntegerField()
    opened_by = serializers.CharField(source="opened_by.username")
    closed_by = serializers.CharField(source="closed_by.username", allow_null=True)

    class Meta:
        model = Stocktake
        fields = (
            "id",
            "equipment_id",
            "opened_at",
            "opened_by",
            "closed_at",
            "closed_by",
        )


class StocktakeLineSerializer(serializers.ModelSerializer):
    counted_by = serializers.CharField(source="counted_by.username", allow_null=True)
    resolved_by = serializers.CharField(source="resolved_by.username", allow_null=True)

    class Meta:
        model = StocktakeLine
        fields = (
            "id",
            "code",
            "expected",
            "observed",
            "movement_id",
            "notes",
            "counted_at",
            "counted_by",
            "resolved_at",
            "resolved_by",
            "resolution_note",
        )


class StocktakeDetailSerializer(serializers.BaseSerializer):
    def to_representation(self, detail):
        return {
            "stocktake": StocktakeSerializer(detail["stocktake"]).data,
            "lines": StocktakeLineSerializer(detail["lines"], many=True).data,
            "movements": HandoverSerializer(detail["movements"], many=True).data,
        }


@api_view(["GET"])
@permission_classes([CanManageReporting])
def reports(request):
    form = PeriodInput(data=request.query_params)
    form.is_valid(raise_exception=True)
    return _operation(
        services.rental_report,
        request.user,
        serializer=ReportSerializer,
        **form.validated_data,
    )


@api_view(["GET"])
@permission_classes([CanManageReporting])
def audit(request, rental_id):
    return _operation(
        services.rental_audit, request.user, rental_id, serializer=AuditSerializer
    )


@api_view(["GET", "POST"])
@permission_classes([CanCountStock])
def stocktakes(request):
    if request.method == "GET":
        return Response(
            StocktakeSerializer(
                services.stocktake_history(request.user), many=True
            ).data
        )
    return _operation(
        services.open_stocktake,
        request.user,
        serializer=StocktakeSerializer,
        status=201,
        **_validated(OpenInput, request),
    )


@api_view(["GET"])
@permission_classes([CanCountStock])
def stocktake(request, stocktake_id):
    return _operation(
        services.stocktake_detail,
        request.user,
        stocktake_id,
        serializer=StocktakeDetailSerializer,
    )


@api_view(["POST"])
@permission_classes([CanCountStock])
def record_observation(request, stocktake_id):
    return _operation(
        services.record_stocktake_line,
        request.user,
        stocktake_id,
        serializer=StocktakeLineSerializer,
        **_validated(ObservationInput, request),
    )


@api_view(["POST"])
@permission_classes([CanManageReporting])
def resolve_discrepancy(request, stocktake_id, line_id):
    return _operation(
        services.resolve_stocktake_line,
        request.user,
        stocktake_id,
        line_id,
        serializer=StocktakeLineSerializer,
        **_validated(ResolutionInput, request),
    )


@api_view(["POST"])
@permission_classes([CanManageReporting])
def close_stocktake(request, stocktake_id):
    return _operation(
        services.close_stocktake,
        request.user,
        stocktake_id,
        serializer=StocktakeSerializer,
    )
