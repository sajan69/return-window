from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class PurchaseStatus(models.TextChoices):
    OPEN = "open", "Open"
    RETURNED = "returned", "Returned"
    KEPT = "kept", "Kept"
    ARCHIVED = "archived", "Archived"


class Purchase(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases"
    )
    item_name = models.CharField(max_length=160)
    store_name = models.CharField(max_length=120)
    purchased_on = models.DateField()
    return_by = models.DateField(help_text="The last return date entered by the owner.")
    policy_url = models.URLField(max_length=500, blank=True)
    notes = models.TextField(max_length=2000, blank=True)
    import_fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=PurchaseStatus, default=PurchaseStatus.OPEN
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["return_by", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(return_by__gte=F("purchased_on")),
                name="purchase_return_not_before_purchase",
            ),
            models.UniqueConstraint(
                fields=["owner", "import_fingerprint"],
                condition=~Q(import_fingerprint=""),
                name="purchase_owner_import_fingerprint_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner", "status", "return_by"], name="purchase_due_idx"
            )
        ]

    def __str__(self) -> str:
        return self.item_name

    def clean(self) -> None:
        super().clean()
        if self.return_by and self.purchased_on and self.return_by < self.purchased_on:
            raise ValidationError(
                {"return_by": "Return deadline cannot be before purchase date."}
            )

    def deadline_state(self, today: date | None = None) -> str:
        if self.status != PurchaseStatus.OPEN:
            return self.status
        today = today or date.today()
        days = (self.return_by - today).days
        if days < 0:
            return "missed"
        if days == 0:
            return "due_today"
        if days <= 7:
            return "due_soon"
        return "upcoming"
