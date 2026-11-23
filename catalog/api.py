from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import Equipment, Rental, RentalLine


class PeriodSerializer(serializers.Serializer):
    pickup_date = serializers.DateField()
    return_date = serializers.DateField()


class BookingLineSerializer(serializers.Serializer):
    equipment_id = serializers.IntegerField(
        min_value=1, max_value=9_223_372_036_854_775_807
    )
    quantity = serializers.IntegerField(
        min_value=services.MIN_RENTAL_QUANTITY,
        max_value=services.MAX_RENTAL_QUANTITY,
    )


class BookingSerializer(PeriodSerializer, BookingLineSerializer):
    pass


class OrderBookingSerializer(PeriodSerializer):
    lines = BookingLineSerializer(many=True, allow_empty=False)


class CatalogQuerySerializer(serializers.Serializer):
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)
    kind = serializers.ChoiceField(
        choices=Equipment.Kind.choices, required=False, allow_blank=True
    )


class EquipmentSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(required=False)

    class Meta:
        model = Equipment
        fields = (
            "id",
            "code",
            "name",
            "kind",
            "specifications",
            "daily_rate_vnd",
            "available_stock",
        )


class RentalSerializer(serializers.ModelSerializer):
    equipment_id = serializers.IntegerField()
    is_overdue = serializers.BooleanField(read_only=True)
    was_returned_late = serializers.BooleanField(read_only=True)
    total_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )

    class Meta:
        model = Rental
        fields = (
            "id",
            "equipment_id",
            "pickup_date",
            "return_date",
            "quantity",
            "daily_rate_vnd",
            "total_vnd",
            "status",
            "picked_up_at",
            "returned_at",
            "cancellation_reason",
            "is_overdue",
            "was_returned_late",
        )


class RentalLineSerializer(serializers.ModelSerializer):
    equipment_id = serializers.IntegerField()
    total_vnd = serializers.DecimalField(
        max_digits=26, decimal_places=0, coerce_to_string=True
    )

    class Meta:
        model = RentalLine
        fields = ("equipment_id", "quantity", "daily_rate_vnd", "total_vnd")


class OrderSerializer(RentalSerializer):
    lines = RentalLineSerializer(many=True, read_only=True)

    class Meta(RentalSerializer.Meta):
        fields = (
            "id",
            "pickup_date",
            "return_date",
            "lines",
            "total_vnd",
            "status",
            "picked_up_at",
            "returned_at",
            "cancellation_reason",
            "is_overdue",
            "was_returned_late",
        )


class OrderDetailSerializer(OrderSerializer):
    receipt = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = (*OrderSerializer.Meta.fields, "closed_at", "receipt")

    def get_receipt(self, rental):
        return services.receipt_summary(rental) if rental.picked_up_at else None


def _rental_response(
    operation, *args, success_status=200, serializer=RentalSerializer, **kwargs
):
    try:
        rental = operation(*args, **kwargs)
    except (Rental.DoesNotExist, Equipment.DoesNotExist) as error:
        raise Http404 from error
    except services.RentalError as error:
        return Response({"detail": str(error)}, status=error.status)
    return Response(serializer(rental).data, status=success_status)


@api_view(["GET"])
def equipment_list(request):
    filters = CatalogQuerySerializer(data=request.query_params)
    filters.is_valid(raise_exception=True)
    equipment = list(services.catalog_items(**filters.validated_data))
    if "pickup_date" in request.query_params or "return_date" in request.query_params:
        period = PeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        try:
            availability = services.catalog_availability(
                equipment, **period.validated_data
            )
        except services.RentalError as error:
            return Response({"detail": str(error)}, status=error.status)
        for item in equipment:
            item.available_stock = availability[item.pk]
    return Response(EquipmentSerializer(equipment, many=True).data)


@api_view(["GET"])
def equipment_detail(request, equipment_id):
    equipment = get_object_or_404(services.catalog_items(), pk=equipment_id)
    return Response(EquipmentSerializer(equipment).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rentals(request):
    if request.method == "GET":
        return Response(
            RentalSerializer(
                services.customer_rentals(request.user, legacy_only=True), many=True
            ).data
        )
    if "lines" in request.data:
        return Response({"detail": "Đơn nhiều dòng dùng /api/v2/rentals/."}, status=400)
    booking = BookingSerializer(data=request.data)
    booking.is_valid(raise_exception=True)
    return _rental_response(
        services.book_rental, request.user, success_status=201, **booking.validated_data
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rental_detail(request, rental_id):
    rental = get_object_or_404(
        services.customer_rentals(request.user, legacy_only=True), pk=rental_id
    )
    return Response(RentalSerializer(rental).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel(request, rental_id):
    return _rental_response(
        services.cancel_rental, request.user, rental_id, legacy_only=True
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def pick_up(request, rental_id):
    return _rental_response(
        services.pick_up_rental, request.user, rental_id, legacy_only=True
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def no_show(request, rental_id):
    return _rental_response(
        services.mark_no_show, request.user, rental_id, legacy_only=True
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def record_return(request, rental_id):
    return _rental_response(
        services.return_rental, request.user, rental_id, legacy_only=True
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def orders(request):
    if request.method == "GET":
        orders = services.customer_rentals(request.user).prefetch_related("lines")
        return Response(OrderSerializer(orders, many=True).data)
    booking = OrderBookingSerializer(data=request.data)
    booking.is_valid(raise_exception=True)
    return _rental_response(
        services.book_order,
        request.user,
        serializer=OrderSerializer,
        success_status=201,
        **booking.validated_data,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, rental_id):
    rental = get_object_or_404(services.customer_rentals(request.user), pk=rental_id)
    return Response(OrderDetailSerializer(rental).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, rental_id):
    return _rental_response(
        services.cancel_rental, request.user, rental_id, serializer=OrderSerializer
    )
