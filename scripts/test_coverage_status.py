#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("coverage_status.py")
SPEC = importlib.util.spec_from_file_location("coverage_status", MODULE_PATH)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = coverage
SPEC.loader.exec_module(coverage)


class CoverageStatusTests(unittest.TestCase):
    def test_partial_lineup_is_degraded_not_complete(self) -> None:
        registry = {
            "channels": [
                {"rank": rank, "name": f"Channel {rank}", "publish": rank <= 7}
                for rank in range(1, 21)
            ]
        }
        status = coverage.country_status(registry)
        self.assertEqual(status["state"], "degraded")
        self.assertEqual(status["published_count"], 7)
        self.assertEqual(status["required_count"], 20)
        self.assertEqual(len(status["missing"]), 13)

    def test_only_full_exact_lineup_is_complete(self) -> None:
        registry = {
            "channels": [
                {"rank": rank, "name": f"Channel {rank}", "publish": True}
                for rank in range(1, 21)
            ]
        }
        status = coverage.country_status(registry)
        self.assertEqual(status["state"], "complete")
        self.assertEqual(status["published_count"], 20)
        self.assertEqual(status["missing"], [])

    def test_target_count_excludes_out_of_scope_archive_channels(self) -> None:
        registry = {
            "target_count": 2,
            "channels": [
                {"rank": 1, "name": "Target One", "publish": True},
                {"rank": 2, "name": "Target Two", "publish": False},
                {"rank": 3, "name": "Archived", "publish": True},
            ],
        }
        status = coverage.country_status(registry)
        self.assertEqual(status["required_count"], 2)
        self.assertEqual(status["published_names"], ["Target One"])
        self.assertEqual(status["missing"][0]["name"], "Target Two")

    def test_real_partial_french_registry_cannot_report_complete(self) -> None:
        status = coverage.build_status()["countries"]["france"]
        self.assertEqual(status["required_count"], 20)
        self.assertLess(status["published_count"], status["required_count"])
        self.assertEqual(status["state"], "degraded")


if __name__ == "__main__":
    unittest.main()
