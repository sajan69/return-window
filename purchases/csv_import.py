import csv
import hashlib
import io
from dataclasses import asdict, dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

HEADERS = (
    "item_name",
    "store_name",
    "purchased_on",
    "return_by",
    "policy_url",
    "notes",
)
MAX_ROWS = 100


class CSVImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportRow:
    item_name: str
    store_name: str
    purchased_on: str
    return_by: str
    policy_url: str
    notes: str
    fingerprint: str

    def payload(self) -> dict[str, str]:
        return asdict(self)


def _date(value: str, field: str, row_number: int) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CSVImportError(
            f"Row {row_number}: {field} must use YYYY-MM-DD."
        ) from error


def _bounded(value: str, field: str, limit: int, row_number: int) -> str:
    value = value.strip()
    if not value:
        raise CSVImportError(f"Row {row_number}: {field} is required.")
    if len(value) > limit:
        raise CSVImportError(
            f"Row {row_number}: {field} must be {limit} characters or fewer."
        )
    return value


def parse_csv(content: bytes) -> list[ImportRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVImportError("CSV must be valid UTF-8.") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != list(HEADERS):
        raise CSVImportError("CSV headers must exactly match the documented template.")

    rows: list[ImportRow] = []
    fingerprints: set[str] = set()
    for row_number, raw in enumerate(reader, start=2):
        if row_number > MAX_ROWS + 1:
            raise CSVImportError(f"CSV cannot contain more than {MAX_ROWS} purchases.")
        if None in raw:
            raise CSVImportError(f"Row {row_number}: too many columns.")

        item_name = _bounded(raw["item_name"], "item_name", 160, row_number)
        store_name = _bounded(raw["store_name"], "store_name", 120, row_number)
        purchased_on = _date(raw["purchased_on"].strip(), "purchased_on", row_number)
        return_by = _date(raw["return_by"].strip(), "return_by", row_number)
        if return_by < purchased_on:
            raise CSVImportError(
                f"Row {row_number}: return_by cannot be before purchased_on."
            )
        policy_url = raw["policy_url"].strip()
        if len(policy_url) > 500:
            raise CSVImportError(
                f"Row {row_number}: policy_url must be 500 characters or fewer."
            )
        if policy_url:
            try:
                URLValidator(schemes=["http", "https"])(policy_url)
            except ValidationError as error:
                raise CSVImportError(
                    f"Row {row_number}: policy_url must be an HTTP or HTTPS URL."
                ) from error
        notes = raw["notes"].strip()
        if len(notes) > 2000:
            raise CSVImportError(
                f"Row {row_number}: notes must be 2000 characters or fewer."
            )
        canonical = "\0".join(
            (
                item_name.casefold(),
                store_name.casefold(),
                purchased_on.isoformat(),
                return_by.isoformat(),
            )
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        if fingerprint in fingerprints:
            raise CSVImportError(f"Row {row_number}: duplicate purchase in this CSV.")
        fingerprints.add(fingerprint)
        rows.append(
            ImportRow(
                item_name,
                store_name,
                purchased_on.isoformat(),
                return_by.isoformat(),
                policy_url,
                notes,
                fingerprint,
            )
        )

    if not rows:
        raise CSVImportError("CSV must contain at least one purchase.")
    return rows
