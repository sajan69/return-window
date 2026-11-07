from unittest import TestCase

from purchases.csv_benchmark import (
    PHASES,
    REPETITIONS,
    ROW_COUNT,
    build_workload,
    summarize,
)
from purchases.csv_import import parse_csv


class CSVBenchmarkTests(TestCase):
    def test_workload_is_stable_and_uses_the_import_ceiling(self) -> None:
        content = build_workload()
        self.assertEqual(build_workload(), content)
        self.assertEqual(len(parse_csv(content)), ROW_COUNT)
        self.assertEqual(ROW_COUNT, 100)

    def test_summary_preserves_all_five_raw_workers(self) -> None:
        workers = []
        for repetition in range(REPETITIONS):
            worker = {phase: (repetition + 1) * 10 for phase in PHASES}
            workers.append(
                {
                    "repetition": repetition,
                    **worker,
                    "measured_total_ns": sum(worker.values()),
                }
            )
        summary = summarize(workers)
        self.assertEqual(
            summary["parse_ns"], {"min_ns": 10, "median_ns": 30, "max_ns": 50}
        )

    def test_summary_refuses_missing_or_replaced_workers(self) -> None:
        worker = {phase: 1 for phase in PHASES}
        workers = [
            {"repetition": repetition, **worker, "measured_total_ns": len(PHASES)}
            for repetition in range(REPETITIONS)
        ]
        with self.assertRaisesRegex(ValueError, "ordered and complete"):
            summarize([*workers[:-1], {**workers[-1], "repetition": 3}])
