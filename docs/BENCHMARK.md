# CSV import benchmark

ReturnWindow measures its maximum documented CSV import size with the deterministic
`csv-import-100-v1` workload. The workload contains 100 synthetic purchases in an
11,871-byte UTF-8 CSV. Its SHA-256 digest is
`578f8dc9a8e7a5f95ab25ac9c05a67d82bfadc9b4f8d3532d093849aec499f1a`.

## Method

Five sequential fresh Python worker processes use the same PostgreSQL service. Every
worker creates a new owner, then measures these phases with `perf_counter_ns`:

1. decode, parse and validate the CSV fields;
2. construct 100 Django models and run `full_clean()` on each, including database
   uniqueness checks;
3. insert all models with `bulk_create()` inside one transaction, including commit;
4. verify the owner's inserted row count.

There are no replacement runs or excluded workers. Dependency installation, database
migrations, Python and Django startup, owner creation and cleanup, authentication,
HTTP upload, signing, rendering and network time are outside the measured phases.
Database caches are not dropped, so this is not a cold-cache measurement.

Run it against a migrated PostgreSQL database:

```bash
DATABASE_URL=postgresql://user:password@127.0.0.1:5432/return_window \
DJANGO_SECRET_KEY=benchmark-only-key \
python -m purchases.csv_benchmark --output artifacts/csv-benchmark.json
```

The runner refuses a result unless all five ordered workers finish and each inserts
exactly 100 rows. Unit tests also lock the workload size and summary rules.

## Recorded result

The source record came from [GitHub Actions run
42404131781](https://github.com/sajan69/return-window/actions/runs/42404131781)
on 7 November 2026 UTC. It used CPython 3.12.16, Django 5.2.19, Psycopg 3.3.8 and
PostgreSQL 18.6 on an Ubuntu x86-64 shared runner.

| Phase                            |   Minimum |    Median |   Maximum |
| -------------------------------- | --------: | --------: | --------: |
| CSV parsing and field validation |  19.99 ms |  20.12 ms |  25.38 ms |
| Model and database validation    | 144.44 ms | 153.13 ms | 159.60 ms |
| Atomic bulk insert and commit    |   5.21 ms |   5.45 ms |   5.52 ms |
| Inserted-row verification        |   0.69 ms |   0.73 ms |   0.83 ms |
| Measured total                   | 170.59 ms | 179.55 ms | 191.19 ms |

Process-lifetime peak RSS ranged from 62,533,632 to 62,742,528 bytes. It includes
imports, Django setup and other process state, so it is not memory allocated by the
CSV pipeline or a memory ceiling.

The complete five raw observations, environment identity, workload identity and
summary are in [`examples/csv-benchmark.json`](../examples/csv-benchmark.json).

## Interpretation and limits

This result demonstrates that the bounded 100-row transaction completed correctly in
five fresh processes in one CI environment. It does not establish production
capacity, concurrent-user behavior, an HTTP response-time target or performance for
larger files. The application intentionally rejects imports above 100 rows rather
than extrapolating from this workload.
