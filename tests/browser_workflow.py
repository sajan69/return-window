from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    sync_playwright,
)

from purchases.models import Purchase

SCREENSHOTS = Path("artifacts/browser")


class BrowserWorkflowTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        cls.playwright: Playwright = sync_playwright().start()
        cls.browser: Browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="browser-owner", password="browser-password"
        )
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.sign_in(self.page)

    def tearDown(self) -> None:
        self.context.close()

    def sign_in(self, page: Page) -> None:
        page.goto(f"{self.live_server_url}/accounts/login/")
        page.get_by_label("Username").fill("browser-owner")
        page.get_by_label("Password").fill("browser-password")
        page.get_by_role("button", name="Sign in").click()
        page.get_by_role("heading", name="Return deadlines").wait_for()

    def make_purchase(self, **changes: object) -> Purchase:
        values = {
            "owner": self.user,
            "item_name": "Desk lamp",
            "store_name": "Example Home",
            "purchased_on": date(2026, 11, 1),
            "return_by": date(2026, 11, 30),
        }
        values.update(changes)
        return Purchase.objects.create(**values)

    def test_desktop_create_edit_transition_and_filter(self) -> None:
        self.page.get_by_role("link", name="Add purchase").click()
        self.page.get_by_label("Item name").fill("Travel backpack")
        self.page.get_by_label("Store name").fill("Example Outdoors")
        self.page.get_by_label("Purchased on").fill("2026-11-01")
        self.page.get_by_label("Return by").fill("2026-11-30")
        self.page.get_by_role("button", name="Save purchase").click()
        self.page.get_by_role("heading", name="Travel backpack").wait_for()

        self.page.get_by_role("link", name="Edit").click()
        self.page.get_by_label("Item name").fill("Carry-on backpack")
        self.page.get_by_role("button", name="Save purchase").click()
        self.page.get_by_role("heading", name="Carry-on backpack").wait_for()

        self.page.get_by_role("button", name="Returned").click()
        self.page.locator("nav.filters a", has_text="Returned").click()
        self.page.get_by_role("heading", name="Carry-on backpack").wait_for()
        self.page.screenshot(path=SCREENSHOTS / "desktop.png", full_page=True)

    def test_stale_draft_import_and_downloads(self) -> None:
        purchase = self.make_purchase()
        self.page.reload()
        self.page.get_by_role("link", name="Edit").click()
        Purchase.objects.filter(pk=purchase.pk).update(
            item_name="Newer saved lamp", version=2
        )
        self.page.get_by_label("Item name").fill("Unsaved lamp draft")
        self.page.get_by_role("button", name="Save purchase").click()
        self.page.get_by_role("alert").wait_for()
        self.assertEqual(
            self.page.get_by_label("Item name").input_value(), "Unsaved lamp draft"
        )
        self.page.get_by_role("link", name="Reload saved version").click()
        self.assertEqual(
            self.page.get_by_label("Item name").input_value(), "Newer saved lamp"
        )

        self.page.goto(self.live_server_url)
        self.page.get_by_role("link", name="Import CSV").click()
        self.page.get_by_label("Csv file").set_input_files(
            {
                "name": "purchases.csv",
                "mimeType": "text/csv",
                "buffer": (
                    b"item_name,store_name,purchased_on,return_by,policy_url,notes\n"
                    b"Rain jacket,Example Outdoors,2026-11-02,2026-12-02,,Packable\n"
                ),
            }
        )
        self.page.get_by_role("button", name="Review import").click()
        self.page.get_by_role("heading", name="Confirm 1 purchases").wait_for()
        self.page.get_by_role("button", name="Import all purchases").click()
        self.page.get_by_role("heading", name="Rain jacket").wait_for()

        with self.page.expect_download() as csv_info:
            self.page.get_by_role("link", name="Export CSV").click()
        csv_download = csv_info.value
        self.assertEqual(csv_download.suggested_filename, "return-window-purchases.csv")
        self.assertIn(b"Rain jacket", csv_download.path().read_bytes())

        with self.page.expect_download() as calendar_info:
            self.page.get_by_role("link", name="Download calendar").click()
        calendar_download = calendar_info.value
        self.assertEqual(
            calendar_download.suggested_filename, "return-window-deadlines.ics"
        )
        self.assertIn(b"BEGIN:VCALENDAR", calendar_download.path().read_bytes())

    def test_mobile_layout_has_no_horizontal_overflow(self) -> None:
        self.context.close()
        self.context = self.browser.new_context(
            accept_downloads=True, viewport={"width": 390, "height": 844}
        )
        self.page = self.context.new_page()
        self.sign_in(self.page)
        self.page.get_by_role("link", name="Add purchase").click()
        self.assertTrue(
            self.page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
        )
        self.page.screenshot(path=SCREENSHOTS / "mobile.png", full_page=True)
