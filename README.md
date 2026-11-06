# ReturnWindow

ReturnWindow is a local web application for recording purchases and the return deadlines entered by their owner. It keeps the source date visible and groups open purchases into upcoming, due soon, due today and missed states. It does not fetch store policies or decide whether a return will be accepted.

## Current capabilities

- authenticated, owner-scoped purchase records;
- explicit purchase and last-return dates with a database constraint;
- open, returned, kept and archived lifecycle states;
- responsive deadline list and create/edit workflow;
- reviewed UTF-8 CSV import with bounded files, strict validation and atomic confirmation;
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

## Checks

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Security and limitations

Purchase records are always queried through the authenticated owner. State changes require POST requests and Django CSRF protection. A production deployment must supply a strong `DJANGO_SECRET_KEY`, configure allowed hosts, use HTTPS and operate PostgreSQL with backups. CSV imports require the exact header order shown in the interface, accept at most 100 rows and 256 KiB, and are rejected as a whole when validation or duplicate checks fail. The current interface has no registration flow, policy scraping, notifications, receipt processing, CSV export or calendar export. Dates are user-entered and ReturnWindow does not guarantee eligibility, refunds or store policy accuracy.
