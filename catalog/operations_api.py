from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from . import services
from .api import PeriodSerializer
from .models import (
    AssetHandover,
    AssetReservation,
    MaintenanceCase,
    Rental,
    RentalChangeRequest,
)


class CanOperate(BasePermission):
    def has_permission(self, request, view):
        return services.can_operate(request.user)


class CanManage(BasePermission):
    def has_permission(self, request, view):
        return services.can_manage(request.user)


class ChangePeriodSerializer(PeriodSerializer):
    kind = serializers.ChoiceField(choices=RentalChangeRequest.Kind.choices)


class ChangeRequestSerializer(ChangePeriodSerializer):
    accepted_total_vnd = serializers.DecimalField(
        min_value=0, max_digits=26, decimal_places=0, required=False
    )


class ChangeQuoteSerializer(serializers.Serializer):
    old_total_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )
    total_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )
    consent_required = serializers.BooleanField()


class RentalChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalChangeRequest
        fields = (
            "id",
            "kind",
            "pickup_date",
            "return_date",
            "old_pickup_date",
            "old_return_date",
            "old_total_vnd",
            "quoted_total_vnd",
            "status",
            "requested_at",
            "reviewed_at",
        )
        read_only_fields = fields


class ChangeReviewSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    review_note = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )


class NotesSerializer(serializers.Serializer):
    notes = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )


class InspectionSerializer(NotesSerializer):
    result = serializers.ChoiceField(choices=AssetHandover.Inspection.choices)


class IncidentSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(
        choices=(
            MaintenanceCase.Kind.DAMAGE,
            MaintenanceCase.Kind.MISSING_ACCESSORY,
            MaintenanceCase.Kind.LOST,
        )
    )
    notes = serializers.CharField(max_length=2000)
    handover_id = serializers.IntegerField(min_value=1, required=False)


class MaintenancePlanSerializer(PeriodSerializer):
    asset_id = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=2000)


class MaintenanceRepairSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=2000)


class MaintenanceResolutionSerializer(MaintenanceRepairSerializer):
    resolution = serializers.ChoiceField(choices=MaintenanceCase.Resolution.choices)


class HandoverSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(read_only=True)
    reservation_id = serializers.IntegerField(read_only=True)
    asset_code = serializers.CharField(source="asset.code", read_only=True)

    class Meta:
        model = AssetHandover
        fields = (
            "id",
            "asset_id",
            "asset_code",
            "reservation_id",
            "expected_accessories",
            "prepared_at",
            "pickup_notes",
            "picked_up_at",
            "returned_at",
            "inspected_at",
            "inspection_result",
            "return_notes",
            "lost_at",
        )
        read_only_fields = fields


class StaffReservationSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(read_only=True)
    asset_code = serializers.CharField(source="asset.code", read_only=True)
    asset_status = serializers.CharField(source="asset.status", read_only=True)
    pickup_date = serializers.DateField(source="period.lower", read_only=True)
    return_date = serializers.DateField(source="period.upper", read_only=True)

    class Meta:
        model = AssetReservation
        fields = (
            "id",
            "asset_id",
            "asset_code",
            "asset_status",
            "pickup_date",
            "return_date",
        )
        read_only_fields = fields


class OperationsRentalSerializer(serializers.ModelSerializer):
    ops_at_risk = serializers.BooleanField(read_only=True)
    ops_waiting_inspection = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Rental
        fields = (
            "id",
            "pickup_date",
            "return_date",
            "status",
            "picked_up_at",
            "returned_at",
            "closed_at",
            "is_overdue",
            "ops_at_risk",
            "ops_waiting_inspection",
        )
        read_only_fields = fields


class MaintenanceCaseSerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(read_only=True)
    asset_code = serializers.CharField(source="asset.code", read_only=True)

    class Meta:
        model = MaintenanceCase
        fields = (
            "id",
            "asset_id",
            "asset_code",
            "kind",
            "state",
            "notes",
            "reported_at",
            "repair_notes",
            "repaired_at",
            "resolution",
            "resolution_notes",
            "resolved_at",
        )
        read_only_fields = fields


def _operation(function, *args, serializer=None, status=200, **kwargs):
    try:
        result = function(*args, **kwargs)
    except ObjectDoesNotExist as error:
        raise Http404 from error
    except services.RentalError as error:
        return Response({"detail": str(error)}, status=error.status)
    return Response(
        serializer(result).data if serializer is not None else None, status=status
    )


def _validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rental_changes(request, rental_id):
    if request.method == "GET":
        rental = get_object_or_404(
            services.customer_rentals(request.user), pk=rental_id
        )
        changes = rental.changes.order_by("-requested_at", "-pk")
        return Response(RentalChangeSerializer(changes, many=True).data)
    return _operation(
        services.request_rental_change,
        request.user,
        rental_id,
        serializer=RentalChangeSerializer,
        status=201,
        **_validated(ChangeRequestSerializer, request),
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_quote(request, rental_id):
    return _operation(
        services.preview_rental_change,
        request.user,
        rental_id,
        serializer=ChangeQuoteSerializer,
        **_validated(ChangePeriodSerializer, request),
    )


@api_view(["GET"])
@permission_classes([CanOperate])
def operations_queue(request):
    queue = request.query_params.get("queue", "all")
    if queue not in ("all", "risk", "overdue"):
        return Response({"detail": "Chọn hàng đợi all, risk hoặc overdue."}, status=400)
    rentals = services.ops_rentals(request.user, queue)
    return Response(OperationsRentalSerializer(rentals, many=True).data)


@api_view(["GET"])
@permission_classes([CanOperate])
def operations_order(request, rental_id):
    rental = get_object_or_404(Rental, pk=rental_id)
    holds = services.rental_asset_history(rental).filter(released_at__isnull=True)
    handovers = services.rental_handovers(rental)
    return Response(
        {
            "rental": OperationsRentalSerializer(rental).data,
            "reservations": StaffReservationSerializer(holds, many=True).data,
            "handovers": HandoverSerializer(handovers, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def prepare_asset(request, rental_id, reservation_id):
    return _operation(
        services.prepare_asset,
        request.user,
        rental_id,
        reservation_id,
        status=204,
        **_validated(NotesSerializer, request),
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def pick_up(request, rental_id):
    return _operation(
        services.pick_up_rental,
        request.user,
        rental_id,
        serializer=OperationsRentalSerializer,
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def receive_asset(request, rental_id, handover_id):
    return _operation(
        services.receive_asset, request.user, rental_id, handover_id, status=204
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def inspect_asset(request, rental_id, handover_id):
    return _operation(
        services.inspect_asset,
        request.user,
        rental_id,
        handover_id,
        status=204,
        **_validated(InspectionSerializer, request),
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def review_change(request, change_id):
    return _operation(
        services.review_rental_change,
        request.user,
        change_id,
        serializer=RentalChangeSerializer,
        **_validated(ChangeReviewSerializer, request),
    )


@api_view(["GET"])
@permission_classes([CanOperate])
def maintenance_cases(request):
    return Response(
        MaintenanceCaseSerializer(
            services.maintenance_cases(request.user), many=True
        ).data
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def plan_maintenance(request):
    return _operation(
        services.plan_maintenance,
        request.user,
        serializer=MaintenanceCaseSerializer,
        status=201,
        **_validated(MaintenancePlanSerializer, request),
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def report_incident(request):
    return _operation(
        services.report_incident,
        request.user,
        serializer=MaintenanceCaseSerializer,
        status=201,
        **_validated(IncidentSerializer, request),
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def start_repair(request, case_id):
    return _operation(
        services.start_repair,
        request.user,
        case_id,
        serializer=MaintenanceCaseSerializer,
        **_validated(MaintenanceRepairSerializer, request),
    )


@api_view(["POST"])
@permission_classes([CanManage])
def resolve_case(request, case_id):
    return _operation(
        services.resolve_case,
        request.user,
        case_id,
        serializer=MaintenanceCaseSerializer,
        **_validated(MaintenanceResolutionSerializer, request),
    )
