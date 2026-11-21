from django import forms
from django.utils import timezone

from .models import Equipment


class PeriodForm(forms.Form):
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
        label="Số lượng", min_value=1, max_value=2_147_483_647, initial=1
    )


class CatalogFilterForm(PeriodForm):
    field_order = ["search", "kind", "pickup_date", "return_date"]

    search = forms.CharField(
        label="Tên hoặc mã thiết bị", max_length=100, required=False
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
            "name",
            "kind",
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
            "specifications": "Thông số thiết bị",
            "is_active": "Đang nhận đặt thuê mới",
        }
        widgets = {"specifications": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["code"].disabled = True
