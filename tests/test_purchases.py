from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from purchases.models import Purchase, PurchaseStatus


class PurchaseModelTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="owner", password="correct horse battery staple"
        )

    def make_purchase(self, **changes: object) -> Purchase:
        values = {
            "owner": self.user,
            "item_name": "Trail shoes",
            "store_name": "Example Outfitters",
            "purchased_on": date(2026, 11, 1),
            "return_by": date(2026, 11, 30),
        }
        values.update(changes)
        return Purchase.objects.create(**values)

    def test_deadline_states_are_explicit_at_boundaries(self) -> None:
        purchase = self.make_purchase(return_by=date(2026, 11, 7))
        self.assertEqual(purchase.deadline_state(date(2026, 11, 7)), "due_today")
        self.assertEqual(purchase.deadline_state(date(2026, 11, 1)), "due_soon")
        self.assertEqual(purchase.deadline_state(date(2026, 10, 30)), "upcoming")
        self.assertEqual(purchase.deadline_state(date(2026, 11, 8)), "missed")

    def test_closed_status_takes_precedence_over_date(self) -> None:
        purchase = self.make_purchase(
            return_by=date.today() - timedelta(days=1), status=PurchaseStatus.RETURNED
        )
        self.assertEqual(purchase.deadline_state(), PurchaseStatus.RETURNED)

    def test_return_deadline_before_purchase_is_rejected(self) -> None:
        purchase = Purchase(
            owner=self.user,
            item_name="Bag",
            store_name="Shop",
            purchased_on=date(2026, 11, 2),
            return_by=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            purchase.full_clean()


class PurchaseViewTests(TestCase):
    def setUp(self) -> None:
        users = get_user_model()
        self.owner = users.objects.create_user(
            username="owner", password="correct horse battery staple"
        )
        self.other = users.objects.create_user(
            username="other", password="correct horse battery staple"
        )
        self.purchase = Purchase.objects.create(
            owner=self.owner,
            item_name="Headphones",
            store_name="Audio Shop",
            purchased_on=date(2026, 11, 1),
            return_by=date(2026, 11, 20),
        )
        self.client.force_login(self.owner)

    def update_payload(self, **changes: object) -> dict[str, object]:
        values: dict[str, object] = {
            "item_name": self.purchase.item_name,
            "store_name": self.purchase.store_name,
            "purchased_on": self.purchase.purchased_on.isoformat(),
            "return_by": self.purchase.return_by.isoformat(),
            "policy_url": self.purchase.policy_url,
            "notes": self.purchase.notes,
            "version": self.purchase.version,
        }
        values.update(changes)
        return values

    def test_list_is_scoped_to_authenticated_owner(self) -> None:
        Purchase.objects.create(
            owner=self.other,
            item_name="Private item",
            store_name="Other",
            purchased_on=date(2026, 11, 1),
            return_by=date(2026, 11, 20),
        )
        response = self.client.get(reverse("purchase-list"))
        self.assertContains(response, "Headphones")
        self.assertNotContains(response, "Private item")

    def test_create_ignores_any_client_owner_field(self) -> None:
        response = self.client.post(
            reverse("purchase-create"),
            {
                "item_name": "Jacket",
                "store_name": "Clothing Shop",
                "purchased_on": "2026-11-01",
                "return_by": "2026-11-21",
                "policy_url": "",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("purchase-list"))
        self.assertEqual(Purchase.objects.get(item_name="Jacket").owner, self.owner)

    def test_other_users_purchase_cannot_be_edited(self) -> None:
        foreign = Purchase.objects.create(
            owner=self.other,
            item_name="Private",
            store_name="Other",
            purchased_on=date(2026, 11, 1),
            return_by=date(2026, 11, 20),
        )
        response = self.client.get(reverse("purchase-update", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_update_uses_the_version_rendered_with_the_form(self) -> None:
        response = self.client.get(reverse("purchase-update", args=[self.purchase.pk]))

        self.assertContains(response, 'name="version" value="1"', html=False)
        self.assertContains(
            response, 'name="purchased_on" value="2026-11-01"', html=False
        )
        self.assertContains(response, 'name="return_by" value="2026-11-20"', html=False)

        response = self.client.post(
            reverse("purchase-update", args=[self.purchase.pk]),
            self.update_payload(item_name="Updated headphones"),
        )
        self.assertRedirects(response, reverse("purchase-list"))
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.item_name, "Updated headphones")
        self.assertEqual(self.purchase.version, 2)

    def test_stale_update_preserves_draft_without_overwriting_saved_record(
        self,
    ) -> None:
        Purchase.objects.filter(pk=self.purchase.pk).update(
            item_name="Newer saved name", version=2
        )

        response = self.client.post(
            reverse("purchase-update", args=[self.purchase.pk]),
            self.update_payload(item_name="Unsaved browser draft"),
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Unsaved browser draft", status_code=409)
        self.assertContains(response, "changed after you opened it", status_code=409)
        self.assertContains(response, "Reload saved version", status_code=409)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.item_name, "Newer saved name")
        self.assertEqual(self.purchase.version, 2)

    def test_transition_requires_post_and_owner(self) -> None:
        url = reverse("purchase-transition", args=[self.purchase.pk, "returned"])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PurchaseStatus.RETURNED)
        self.assertEqual(self.purchase.version, 2)
