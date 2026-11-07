import csv
import io

from icalendar import Calendar, Event

from .models import Purchase

CSV_HEADERS = (
    "item_name",
    "store_name",
    "purchased_on",
    "return_by",
    "policy_url",
    "notes",
    "status",
)
FORMULA_PREFIXES = frozenset("=+-@＝＋－＠\t\r\n")


def spreadsheet_text(value: str) -> str:
    """Keep user text from becoming a spreadsheet formula when opened."""
    candidate = value.lstrip(" ")
    if candidate and candidate[0] in FORMULA_PREFIXES:
        return f"'{value}"
    return value


def purchases_csv(purchases: list[Purchase]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_HEADERS)
    for purchase in purchases:
        writer.writerow(
            (
                spreadsheet_text(purchase.item_name),
                spreadsheet_text(purchase.store_name),
                purchase.purchased_on.isoformat(),
                purchase.return_by.isoformat(),
                spreadsheet_text(purchase.policy_url),
                spreadsheet_text(purchase.notes),
                purchase.status,
            )
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def return_calendar(purchases: list[Purchase]) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//ReturnWindow//Return deadlines//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", "ReturnWindow deadlines")

    for purchase in purchases:
        event = Event()
        event.add("uid", f"purchase-{purchase.pk}@return-window.local")
        event.add("dtstamp", purchase.updated_at)
        event.add("dtstart", purchase.return_by)
        event.add("summary", f"Return deadline: {purchase.item_name}")
        event.add("description", _event_description(purchase))
        event.add("transp", "TRANSPARENT")
        calendar.add_component(event)
    return calendar.to_ical()


def _event_description(purchase: Purchase) -> str:
    details = [f"Store: {purchase.store_name}"]
    if purchase.policy_url:
        details.append(f"Policy reference: {purchase.policy_url}")
    if purchase.notes:
        details.append(f"Notes: {purchase.notes}")
    details.append("This deadline was entered by the record owner.")
    return "\n".join(details)
