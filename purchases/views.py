from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PurchaseForm
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
