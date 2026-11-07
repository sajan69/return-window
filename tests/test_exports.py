import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from icalendar import Calendar

from purchases.models import Purchase, PurchaseStatus


class PurchaseExportTests(TestCase):
    def setUp(self) -> None:
        users = get_user_model()
        self.owner = users.objects.create_user(username="owner", password="password")
        self.other = users.objects.create_user(username="other", password="password")
        self.client.force_login(self.owner)

    def make_purchase(self, **changes: object) -> Purchase:
        values = {
            "owner": self.owner,
            "item_name": "Trail shoes",
            "store_name": "Example Outfitters",
            "purchased_on": date(2026, 11, 1),
            "return_by": date(2026, 11, 30),
        }
        values.update(changes)
        return Purchase.objects.create(**values)

    def test_csv_contains_owner_records_and_neutralises_formula_like_text(self) -> None:
        self.make_purchase(
            item_name="=2+2",
            store_name="  @example",
            notes="+SUM(1,1)\nsecond line",
        )
        self.make_purchase(owner=self.other, item_name="Private item")

        response = self.client.get(reverse("purchase-export-csv"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_name"], "'=2+2")
        self.assertEqual(rows[0]["store_name"], "'  @example")
        self.assertEqual(rows[0]["notes"], "'+SUM(1,1)\nsecond line")
        self.assertNotIn(b"Private item", response.content)

    def test_calendar_has_only_owner_open_deadlines_as_all_day_events(self) -> None:
        open_purchase = self.make_purchase(notes="Keep the receipt")
        self.make_purchase(item_name="Already kept", status=PurchaseStatus.KEPT)
        self.make_purchase(owner=self.other, item_name="Private item")

        response = self.client.get(reverse("purchase-export-calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        calendar = Calendar.from_ical(response.content)
        events = [
            component for component in calendar.walk() if component.name == "VEVENT"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decoded("dtstart"), open_purchase.return_by)
        self.assertEqual(str(events[0]["summary"]), "Return deadline: Trail shoes")
        self.assertIn("Keep the receipt", str(events[0]["description"]))
        self.assertNotIn(b"Already kept", response.content)
        self.assertNotIn(b"Private item", response.content)

    def test_exports_require_authentication(self) -> None:
        self.client.logout()
        for name in ("purchase-export-csv", "purchase-export-calendar"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/accounts/login/", response.url)
