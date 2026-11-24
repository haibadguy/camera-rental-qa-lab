from django.core.paginator import InvalidPage, Paginator
from django.http import Http404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from . import services
from .api import CatalogQuerySerializer, EquipmentSerializer, OrderBookingSerializer, OrderSerializer
from .finance_api import EntrySerializer
from .management_api import CanManageReporting, PeriodInput, ReportSummarySerializer
from .operations_api import CanOperate, _operation
from .models import CounterCommand


class PageInput(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=60, default=24)


class CatalogInput(CatalogQuerySerializer, PageInput):
    pickup_date = serializers.DateField(required=False)
    return_date = serializers.DateField(required=False)

    def validate(self, data):
        if ("pickup_date" in data) != ("return_date" in data):
            raise serializers.ValidationError("Chọn cả ngày nhận và ngày trả.")
        return data


class StaffOrderInput(OrderBookingSerializer):
    command_id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)


class ScanInput(serializers.Serializer):
    command_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=[
        CounterCommand.Action.PREPARE, CounterCommand.Action.RECEIVE
    ])
    codes = serializers.ListField(
        child=serializers.CharField(max_length=48), min_length=1, max_length=services.MAX_SCAN_CODES
    )


def _page(items, page, page_size):
    try:
        return Paginator(items, page_size).page(page)
    except InvalidPage as error:
        raise Http404 from error


def _response(page, data):
    return Response({
        "count": page.paginator.count,
        "page": page.number,
        "page_size": page.paginator.per_page,
        "next_page": page.next_page_number() if page.has_next() else None,
        "results": data,
    })


@api_view(["GET"])
def catalog(request):
    form = CatalogInput(data=request.query_params)
    form.is_valid(raise_exception=True)
    filters = dict(form.validated_data)
    page_number, page_size = filters.pop("page"), filters.pop("page_size")
    dates = {field: filters.pop(field) for field in ("pickup_date", "return_date") if field in filters}
    items = services.catalog_items(**filters).order_by("name", "pk")
    page = _page(items, page_number, page_size)
    equipment = list(page)
    if dates:
        try:
            stock = services.catalog_availability(equipment, **dates)
        except services.RentalError as error:
            return Response({"detail": str(error)}, status=error.status)
        for item in equipment:
            item.available_stock = stock[item.pk]
    return _response(page, EquipmentSerializer(equipment, many=True).data)


@api_view(["GET"])
@permission_classes([CanManageReporting])
def summary(request):
    form = PeriodInput(data=request.query_params)
    form.is_valid(raise_exception=True)
    return _operation(
        services.rental_report, request.user, summary=True,
        serializer=ReportSummarySerializer, **form.validated_data,
    )


@api_view(["GET"])
@permission_classes([CanManageReporting])
def report_detail(request, section):
    if section not in ("orders", "entries", "stock", "out_assets", "usage"):
        raise Http404
    form = PageInput(data=request.query_params)
    period = PeriodInput(data=request.query_params)
    form.is_valid(raise_exception=True)
    period.is_valid(raise_exception=True)
    try:
        items = services.report_detail(request.user, section, **period.validated_data)
    except services.RentalError as error:
        return Response({"detail": str(error)}, status=error.status)
    page = _page(items, **form.validated_data)
    if section == "orders":
        data = OrderSerializer(page, many=True).data
    elif section == "entries":
        data = EntrySerializer(page, many=True).data
    elif section == "stock":
        data = [
            {"equipment_id": row.pk, "code": row.code, "available_now": row.available_now,
             "outstanding": row.outstanding} for row in page
        ]
    elif section == "out_assets":
        data = [{"asset_code": row.asset.code, "rental_id": row.line.rental_id} for row in page]
    else:
        data = [row | {"asset": row["asset"].code} for row in page]
    return _response(page, data)


@api_view(["POST"])
def counter_order(request):
    if not services.can_book_for_customer(request.user):
        return Response({"detail": "Cần quyền tạo đơn hộ khách."}, status=403)
    form = StaffOrderInput(data=request.data)
    form.is_valid(raise_exception=True)
    return _operation(
        services.book_for_customer, request.user,
        serializer=OrderSerializer, status=201, **form.validated_data,
    )


@api_view(["POST"])
@permission_classes([CanOperate])
def scan(request, rental_id):
    form = ScanInput(data=request.data)
    form.is_valid(raise_exception=True)
    return _operation(services.scan_assets, request.user, rental_id, status=204, **form.validated_data)
