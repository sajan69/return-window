from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .csv_import import CSVImportError, ImportRow, parse_csv
from .exports import purchases_csv, return_calendar
from .forms import CSVUploadForm, PurchaseForm
from .models import Purchase, PurchaseStatus


@login_required
def purchase_list(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status", PurchaseStatus.OPEN)
    allowed = {choice.value for choice in PurchaseStatus}
    if status not in allowed:
        status = PurchaseStatus.OPEN
    purchases = list(Purchase.objects.filter(owner=request.user, status=status))
    rows = [(purchase, purchase.deadline_state(date.today())) for purchase in purchases]
    return render(
        request,
        "purchases/list.html",
        {"rows": rows, "selected_status": status, "statuses": PurchaseStatus},
    )


@login_required
@transaction.atomic
def purchase_create(request: HttpRequest) -> HttpResponse:
    form = PurchaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        purchase = form.save(commit=False)
        purchase.owner = request.user
        purchase.full_clean()
        purchase.save()
        return redirect("purchase-list")
    return render(
        request, "purchases/form.html", {"form": form, "heading": "Add purchase"}
    )


@login_required
@transaction.atomic
def purchase_update(request: HttpRequest, pk: int) -> HttpResponse:
    purchase = get_object_or_404(Purchase, pk=pk, owner=request.user)
    form = PurchaseForm(request.POST or None, instance=purchase)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.version += 1
        updated.full_clean()
        updated.save()
        return redirect("purchase-list")
    return render(
        request, "purchases/form.html", {"form": form, "heading": "Edit purchase"}
    )


@login_required
@transaction.atomic
def purchase_transition(request: HttpRequest, pk: int, status: str) -> HttpResponse:
    if request.method != "POST" or status not in {
        PurchaseStatus.RETURNED,
        PurchaseStatus.KEPT,
        PurchaseStatus.ARCHIVED,
    }:
        return HttpResponse(status=405)
    purchase = get_object_or_404(Purchase, pk=pk, owner=request.user)
    purchase.status = status
    purchase.version += 1
    purchase.save(update_fields=["status", "version", "updated_at"])
    return redirect("purchase-list")


@login_required
def import_preview(request: HttpRequest) -> HttpResponse:
    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            rows = parse_csv(form.cleaned_data["csv_file"].read())
        except CSVImportError as error:
            form.add_error("csv_file", str(error))
        else:
            token = signing.dumps(
                [row.payload() for row in rows],
                salt="purchase-csv-import-v1",
                compress=True,
            )
            return render(
                request,
                "purchases/import_preview.html",
                {"rows": rows, "token": token},
            )
    return render(request, "purchases/import_upload.html", {"form": form})


@login_required
def import_confirm(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        payload = signing.loads(
            request.POST.get("token", ""),
            salt="purchase-csv-import-v1",
            max_age=15 * 60,
        )
        rows = [ImportRow(**row) for row in payload]
    except (signing.BadSignature, TypeError, ValueError):
        messages.error(
            request, "Import preview expired or was invalid. Upload the CSV again."
        )
        return redirect("purchase-import")

    fingerprints = [row.fingerprint for row in rows]
    if not rows or len(rows) > 100 or len(set(fingerprints)) != len(rows):
        messages.error(request, "Import preview was invalid. Upload the CSV again.")
        return redirect("purchase-import")
    if Purchase.objects.filter(
        owner=request.user, import_fingerprint__in=fingerprints
    ).exists():
        messages.error(
            request, "One or more purchases were already imported. Nothing was added."
        )
        return redirect("purchase-import")

    purchases = [
        Purchase(
            owner=request.user,
            item_name=row.item_name,
            store_name=row.store_name,
            purchased_on=date.fromisoformat(row.purchased_on),
            return_by=date.fromisoformat(row.return_by),
            policy_url=row.policy_url,
            notes=row.notes,
            import_fingerprint=row.fingerprint,
        )
        for row in rows
    ]
    for purchase in purchases:
        purchase.full_clean()
    try:
        with transaction.atomic():
            Purchase.objects.bulk_create(purchases)
    except IntegrityError:
        messages.error(
            request,
            "The import conflicted with purchases added at the same time. "
            "Nothing was added.",
        )
        return redirect("purchase-import")
    messages.success(request, f"Imported {len(purchases)} purchases.")
    return redirect("purchase-list")


@login_required
def export_csv(request: HttpRequest) -> HttpResponse:
    purchases = list(Purchase.objects.filter(owner=request.user))
    response = HttpResponse(
        purchases_csv(purchases), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = (
        'attachment; filename="return-window-purchases.csv"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def export_calendar(request: HttpRequest) -> HttpResponse:
    purchases = list(
        Purchase.objects.filter(owner=request.user, status=PurchaseStatus.OPEN)
    )
    response = HttpResponse(
        return_calendar(purchases), content_type="text/calendar; charset=utf-8"
    )
    response["Content-Disposition"] = (
        'attachment; filename="return-window-deadlines.ics"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
