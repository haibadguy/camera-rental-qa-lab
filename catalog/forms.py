from django import forms
from django.utils import timezone

from .models import Equipment
from .services import MAX_RENTAL_DAYS, MAX_RENTAL_QUANTITY, MIN_RENTAL_QUANTITY


class PeriodForm(forms.Form):
    max_rental_days = MAX_RENTAL_DAYS
    pickup_date = forms.DateField(
        label="Ngày nhận",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    return_date = forms.DateField(
        label="Ngày trả",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pickup_date"].widget.attrs["min"] = timezone.localdate().isoformat()


class BookingForm(PeriodForm):
    quantity = forms.IntegerField(
        label="Số lượng",
        min_value=MIN_RENTAL_QUANTITY,
        max_value=MAX_RENTAL_QUANTITY,
        initial=MIN_RENTAL_QUANTITY,
    )


class CatalogFilterForm(PeriodForm):
    field_order = ["search", "kind", "pickup_date", "return_date"]

    search = forms.CharField(
        label="Tên hoặc mã thiết bị",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nhập từ khóa"}),
    )
    kind = forms.ChoiceField(
        label="Loại thiết bị",
        choices=[("", "Tất cả thiết bị"), *Equipment.Kind.choices],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("pickup_date", "return_date"):
            self.fields[name].required = False


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = (
            "code",
            "kind",
            "name",
            "specifications",
            "daily_rate_vnd",
            "total_stock",
            "is_active",
        )
        labels = {
            "code": "Mã thiết bị",
            "name": "Tên thiết bị",
            "daily_rate_vnd": "Giá thuê mỗi ngày (₫)",
            "total_stock": "Tổng tồn kho",
            "kind": "Loại thiết bị",
            "specifications": "Thông số và phụ kiện đi kèm",
            "is_active": "Đang nhận đặt thuê mới",
        }
        help_texts = {
            "specifications": "Ghi rõ thiết bị và phụ kiện thực tế có trong bộ thuê."
        }
        widgets = {"specifications": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["code"].disabled = True
