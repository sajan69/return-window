from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("purchases", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="purchase",
            name="import_fingerprint",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddConstraint(
            model_name="purchase",
            constraint=models.UniqueConstraint(
                condition=models.Q(("import_fingerprint", ""), _negated=True),
                fields=("owner", "import_fingerprint"),
                name="purchase_owner_import_fingerprint_unique",
            ),
        ),
    ]
