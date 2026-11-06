import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Purchase",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("item_name", models.CharField(max_length=160)),
                ("store_name", models.CharField(max_length=120)),
                ("purchased_on", models.DateField()),
                (
                    "return_by",
                    models.DateField(
                        help_text="The last return date entered by the owner."
                    ),
                ),
                ("policy_url", models.URLField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True, max_length=2000)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("returned", "Returned"),
                            ("kept", "Kept"),
                            ("archived", "Archived"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["return_by", "id"]},
        ),
        migrations.AddConstraint(
            model_name="purchase",
            constraint=models.CheckConstraint(
                condition=models.Q(("return_by__gte", models.F("purchased_on"))),
                name="purchase_return_not_before_purchase",
            ),
        ),
        migrations.AddIndex(
            model_name="purchase",
            index=models.Index(
                fields=["owner", "status", "return_by"], name="purchase_due_idx"
            ),
        ),
    ]
