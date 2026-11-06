from django import forms

from .models import Purchase


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            "item_name",
            "store_name",
            "purchased_on",
            "return_by",
            "policy_url",
            "notes",
        ]
        widgets = {
            "purchased_on": forms.DateInput(attrs={"type": "date"}),
            "return_by": forms.DateInput(attrs={"type": "date"}),
        }
