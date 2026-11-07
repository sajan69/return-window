# ReturnWindow

ReturnWindow is a local web application for recording purchases and the return deadlines entered by their owner. It keeps the source date visible and groups open purchases into upcoming, due soon, due today and missed states. It does not fetch store policies or decide whether a return will be accepted.

## Current capabilities

- authenticated, owner-scoped purchase records;
- explicit purchase and last-return dates with a database constraint;
- open, returned, kept and archived lifecycle states;
- optimistic edit checks that preserve stale browser drafts instead of overwriting newer changes;
- responsive deadline list and create/edit workflow;
- reviewed UTF-8 CSV import with bounded files, strict validation and atomic confirmation;
- owner-scoped CSV export with spreadsheet-formula neutralisation;
- downloadable iCalendar events for open return deadlines;
- PostgreSQL CI plus a SQLite option for a quick local demonstration.

## Local setup

Requires Python 3.12 or newer.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python manage.py migrate
python manage.py createsuperuser
DJANGO_DEBUG=true python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the account you created. Set `DATABASE_URL` to a PostgreSQL URL to use PostgreSQL instead of the local SQLite demonstration database.

The import screen accepts the checked [example CSV](examples/purchases.csv). It shows
the parsed rows before anything is saved; confirm the preview to insert every row in
one transaction. The CSV and calendar actions on the purchase list download snapshots
of the signed-in owner's current records.

## Architecture

ReturnWindow is a server-rendered Django application. Django authentication owns the
session and CSRF boundaries, while every purchase query is scoped to the signed-in
owner. The `Purchase` model and PostgreSQL enforce date and import-identity constraints.
CSV parsing produces immutable reviewed rows; a short-lived signed preview carries
those rows to an atomic confirmation step. CSV and iCalendar exporters build downloads
from owner-scoped querysets without fetching policy URLs or calling external services.

## Checks

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py test
npm ci
npm run format:check
npm run links
```

The browser workflow is separate because it installs Chromium:

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
python manage.py test tests.browser_workflow
```

## Evaluation

The [CSV import benchmark](docs/BENCHMARK.md) records five fresh-process runs of the
documented 100-row limit on PostgreSQL, including raw phase timings, workload and
environment identity, and measurement limitations.

## Security and limitations

Purchase records and downloads are always queried through the authenticated owner. State changes require POST requests and Django CSRF protection. Edits compare the submitted record version atomically and return a conflict page with the unsaved draft when a newer change exists. A production deployment must supply a strong `DJANGO_SECRET_KEY`, configure allowed hosts, use HTTPS and operate PostgreSQL with backups. CSV imports require the exact header order shown in the interface, accept at most 100 rows and 256 KiB, and are rejected as a whole when validation or duplicate checks fail. Exported text that resembles a spreadsheet formula is prefixed with a single quote; applications differ in how they handle CSV, so inspect files before sharing them. Calendar files contain open deadlines only and do not create reminders or update themselves after download. Browser checks use Chromium only and do not establish full accessibility or cross-browser compatibility. The current interface has no registration flow, policy scraping, notifications or receipt processing. Dates are user-entered and ReturnWindow does not guarantee eligibility, refunds or store policy accuracy.

## Technical references

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Playwright for Python](https://playwright.dev/python/docs/intro)
- [OWASP CSV injection guidance](https://owasp.org/www-community/attacks/CSV_Injection)
