import argparse
import csv
import hashlib
import io
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import uuid
from datetime import date, timedelta
from importlib.metadata import version
from pathlib import Path
from time import perf_counter_ns

WORKLOAD_ID = "csv-import-100-v1"
REPETITIONS = 5
ROW_COUNT = 100
PHASES = ("parse_ns", "model_validation_ns", "atomic_insert_ns", "verify_ns")


def build_workload() -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "item_name",
            "store_name",
            "purchased_on",
            "return_by",
            "policy_url",
            "notes",
        )
    )
    start = date(2026, 1, 1)
    for index in range(ROW_COUNT):
        purchased_on = start + timedelta(days=index)
        writer.writerow(
            (
                f"Benchmark item {index + 1:03d}",
                f"Example store {(index % 10) + 1:02d}",
                purchased_on.isoformat(),
                (purchased_on + timedelta(days=30)).isoformat(),
                f"https://example.com/policies/{(index % 10) + 1}",
                f"Synthetic benchmark note {index + 1:03d}",
            )
        )
    return output.getvalue().encode("utf-8")


def summarize(workers: list[dict[str, object]]) -> dict[str, object]:
    if len(workers) != REPETITIONS:
        raise ValueError(f"Expected {REPETITIONS} completed workers.")
    if [worker.get("repetition") for worker in workers] != list(range(REPETITIONS)):
        raise ValueError("Workers must be ordered and complete without replacement.")

    phase_summary: dict[str, dict[str, int]] = {}
    for phase in (*PHASES, "measured_total_ns"):
        values = [worker.get(phase) for worker in workers]
        if not all(isinstance(value, int) and value > 0 for value in values):
            raise ValueError(f"Every {phase} observation must be a positive integer.")
        integer_values = [int(value) for value in values]
        phase_summary[phase] = {
            "min_ns": min(integer_values),
            "median_ns": int(statistics.median(integer_values)),
            "max_ns": max(integer_values),
        }
    return phase_summary


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value * 1024 if sys.platform.startswith("linux") else value)


def run_worker(repetition: int) -> dict[str, object]:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.db import connection, transaction

    from purchases.csv_import import parse_csv
    from purchases.models import Purchase

    content = build_workload()
    user = get_user_model().objects.create_user(
        username=f"csv-benchmark-{repetition}-{uuid.uuid4().hex}", password=None
    )
    try:
        started = perf_counter_ns()
        rows = parse_csv(content)
        parse_ns = perf_counter_ns() - started

        started = perf_counter_ns()
        purchases = [
            Purchase(
                owner=user,
                item_name=row.item_name,
                store_name=row.store_name,
                purchased_on=date.fromisoformat(row.purchased_on),
                return_by=date.fromisoformat(row.return_by),
                policy_url=row.policy_url,
                notes=row.notes,
                import_fingerprint=row.fingerprint,
            )
            for row in rows
        ]
        for purchase in purchases:
            purchase.full_clean()
        model_validation_ns = perf_counter_ns() - started

        started = perf_counter_ns()
        with transaction.atomic():
            Purchase.objects.bulk_create(purchases)
        atomic_insert_ns = perf_counter_ns() - started

        started = perf_counter_ns()
        inserted = Purchase.objects.filter(owner=user).count()
        verify_ns = perf_counter_ns() - started
        if inserted != ROW_COUNT:
            raise RuntimeError(f"Expected {ROW_COUNT} inserted rows, found {inserted}.")

        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            database_version = cursor.fetchone()[0]

        phases = {
            "parse_ns": parse_ns,
            "model_validation_ns": model_validation_ns,
            "atomic_insert_ns": atomic_insert_ns,
            "verify_ns": verify_ns,
        }
        return {
            "repetition": repetition,
            **phases,
            "measured_total_ns": sum(phases.values()),
            "inserted_rows": inserted,
            "peak_process_rss_bytes": _peak_rss_bytes(),
            "database_vendor": connection.vendor,
            "database_version": database_version,
        }
    finally:
        user.delete()


def build_record(workers: list[dict[str, object]]) -> dict[str, object]:
    content = build_workload()
    identities = {
        (worker["database_vendor"], worker["database_version"]) for worker in workers
    }
    if len(identities) != 1:
        raise ValueError("All workers must use the same database identity.")
    database_vendor, database_version = identities.pop()
    return {
        "schema_version": 1,
        "benchmark": WORKLOAD_ID,
        "completed": True,
        "method": {
            "repetitions": REPETITIONS,
            "process_model": "five sequential fresh Python worker processes",
            "replacement_policy": "no retries, replacements, or excluded workers",
            "measured_phases": list(PHASES),
            "excluded": [
                "Python and Django import/startup",
                "user creation and cleanup",
                "HTTP upload, authentication, signing, rendering, and network time",
                "database migration and dependency installation",
            ],
        },
        "workload": {
            "rows": ROW_COUNT,
            "csv_bytes": len(content),
            "csv_sha256": hashlib.sha256(content).hexdigest(),
            "data": "deterministic synthetic purchase records; no personal data",
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "django": version("Django"),
            "psycopg": version("psycopg"),
            "database_vendor": database_vendor,
            "database_version": database_version,
        },
        "workers": workers,
        "summary": summarize(workers),
        "limits": [
            "Shared CI runner observations are not production capacity or an SLO.",
            "The workload exercises the documented 100-row ceiling only.",
            (
                "Database caches are not dropped between workers; "
                "no cold-cache claim is made."
            ),
            (
                "Peak RSS is process-lifetime high-water memory, "
                "not an allocation by one phase."
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-index", type=int)
    args = parser.parse_args()
    if args.worker_index is not None:
        if not 0 <= args.worker_index < REPETITIONS:
            parser.error("worker index is outside the benchmark contract")
        print(json.dumps(run_worker(args.worker_index), sort_keys=True))
        return
    if args.output is None:
        parser.error("--output is required")

    workers: list[dict[str, object]] = []
    for repetition in range(REPETITIONS):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "purchases.csv_benchmark",
                "--worker-index",
                str(repetition),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        workers.append(json.loads(result.stdout))
    record = build_record(workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"completed {len(workers)} benchmark workers")


if __name__ == "__main__":
    main()
