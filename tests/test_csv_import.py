from datetime import date

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from purchases.csv_import import CSVImportError, parse_csv
from purchases.models import Purchase

HEADER = b"item_name,store_name,purchased_on,return_by,policy_url,notes\n"


class CSVParserTests(TestCase):
    def test_utf8_bom_and_quoted_values_are_supported(self) -> None:
        rows = parse_csv(
            b"\xef\xbb\xbf"
            + HEADER
            + b'"Jacket, blue",Shop,2026-11-01,2026-11-30,'
            + b'https://example.com,"Gift, boxed"\n'
        )
        self.assertEqual(rows[0].item_name, "Jacket, blue")
        self.assertEqual(rows[0].notes, "Gift, boxed")

    def test_invalid_row_rejects_the_complete_file(self) -> None:
        with self.assertRaisesMessage(CSVImportError, "Row 3"):
            parse_csv(
                HEADER
                + b"Bag,Shop,2026-11-01,2026-11-30,,\n"
                + b"Shoes,Shop,bad,2026-11-30,,\n"
            )

    def test_duplicate_rows_are_rejected(self) -> None:
        row = b"Bag,Shop,2026-11-01,2026-11-30,,\n"
        with self.assertRaisesMessage(CSVImportError, "duplicate purchase"):
            parse_csv(HEADER + row + row)


class CSVImportViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="owner", password="correct horse battery staple"
        )
        self.client.force_login(self.user)

    def upload(self, content: bytes):
        return self.client.post(
            reverse("purchase-import"),
            {
                "csv_file": SimpleUploadedFile(
                    "purchases.csv", content, content_type="text/csv"
                )
            },
        )

    def test_preview_does_not_write_and_confirmation_imports_all_rows(self) -> None:
        response = self.upload(
            HEADER
            + b"Bag,Shop,2026-11-01,2026-11-30,,First\n"
            + b"Shoes,Store,2026-11-02,2026-12-01,,Second\n"
        )
        self.assertEqual(Purchase.objects.count(), 0)
        confirmed = self.client.post(
            reverse("purchase-import-confirm"), {"token": response.context["token"]}
        )
        self.assertRedirects(confirmed, reverse("purchase-list"))
        self.assertEqual(Purchase.objects.filter(owner=self.user).count(), 2)

    def test_existing_fingerprint_rejects_entire_confirmation(self) -> None:
        response = self.upload(
            HEADER
            + b"Bag,Shop,2026-11-01,2026-11-30,,\n"
            + b"Shoes,Store,2026-11-02,2026-12-01,,\n"
        )
        token = response.context["token"]
        first = signing.loads(token, salt="purchase-csv-import-v1")[0]
        Purchase.objects.create(
            owner=self.user,
            item_name=first["item_name"],
            store_name=first["store_name"],
            purchased_on=date.fromisoformat(first["purchased_on"]),
            return_by=date.fromisoformat(first["return_by"]),
            import_fingerprint=first["fingerprint"],
        )
        self.client.post(reverse("purchase-import-confirm"), {"token": token})
        self.assertEqual(Purchase.objects.count(), 1)

    def test_tampered_token_writes_nothing(self) -> None:
        response = self.client.post(
            reverse("purchase-import-confirm"), {"token": "tampered"}
        )
        self.assertRedirects(response, reverse("purchase-import"))
        self.assertEqual(Purchase.objects.count(), 0)
