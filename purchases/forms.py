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


class PurchaseEditForm(PurchaseForm):
    class Meta(PurchaseForm.Meta):
        fields = [*PurchaseForm.Meta.fields, "version"]
        widgets = {**PurchaseForm.Meta.widgets, "version": forms.HiddenInput()}


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        help_text="UTF-8 CSV, no more than 100 purchases or 256 KiB."
    )

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if upload.size > 256 * 1024:
            raise forms.ValidationError("CSV file must be 256 KiB or smaller.")
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Choose a .csv file.")
        return upload
