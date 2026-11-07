from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    sync_playwright,
)

SCREENSHOTS = Path("artifacts/browser")


class BrowserWorkflowTests(StaticLiveServerTestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="browser-owner", password="browser-password"
        )
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        self.playwright: Playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch()
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.sign_in(self.page)

    def tearDown(self) -> None:
        self.context.close()
        self.browser.close()
        self.playwright.stop()

    def sign_in(self, page: Page) -> None:
        page.goto(f"{self.live_server_url}/accounts/login/")
        page.get_by_label("Username").fill("browser-owner")
        page.get_by_label("Password").fill("browser-password")
        page.get_by_role("button", name="Sign in").click()
        page.get_by_role("heading", name="Return deadlines").wait_for()

    def create_purchase(self, page: Page, item_name: str) -> None:
        page.get_by_role("link", name="Add purchase").click()
        page.get_by_label("Item name").fill(item_name)
        page.get_by_label("Store name").fill("Example Home")
        page.get_by_label("Purchased on").fill("2026-11-01")
        page.get_by_label("Return by").fill("2026-11-30")
        page.get_by_role("button", name="Save purchase").click()
        page.get_by_role("heading", name=item_name).wait_for()

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
        self.create_purchase(self.page, "Desk lamp")
        self.page.get_by_role("link", name="Edit").click()

        newer_context = self.browser.new_context()
        newer_page = newer_context.new_page()
        self.sign_in(newer_page)
        newer_page.get_by_role("link", name="Edit").click()
        newer_page.get_by_label("Item name").fill("Newer saved lamp")
        newer_page.get_by_role("button", name="Save purchase").click()
        newer_page.get_by_role("heading", name="Newer saved lamp").wait_for()
        newer_context.close()

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
