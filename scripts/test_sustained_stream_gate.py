#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("sustained_stream_gate.py")
SPEC = importlib.util.spec_from_file_location("sustained_stream_gate_tests", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


POLICY = {
    "duration_seconds": 60,
    "minimum_media_ratio": 0.95,
    "maximum_wall_lag_seconds": 12,
    "freeze_detection_seconds": 2,
    "maximum_single_freeze_seconds": 5,
    "maximum_total_freeze_seconds": 8,
    "maximum_freeze_events": 3,
    "maximum_network_errors": 0,
    "process_grace_seconds": 45,
}


def progress(seconds: float) -> str:
    return f"out_time=00:01:{seconds - 60:05.2f}\nprogress=end\n"


class SustainedEvaluationTests(unittest.TestCase):
    def test_clean_minute_passes(self) -> None:
        result = gate.evaluate(
            returncode=0,
            stdout=progress(60),
            stderr="",
            wall_seconds=65,
            policy=POLICY,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.reason, "sustained_ok")

    def test_buffering_fails_even_when_full_media_eventually_decodes(self) -> None:
        result = gate.evaluate(
            returncode=0,
            stdout=progress(60),
            stderr="",
            wall_seconds=81,
            policy=POLICY,
        )
        self.assertFalse(result.passed)
        self.assertIn("buffering_21.0s", result.reason)

    def test_repeated_and_long_freezes_fail(self) -> None:
        stderr = "\n".join(
            [
                "freeze_start: 2.0",
                "freeze_duration: 2.5",
                "freeze_end: 4.5",
                "freeze_start: 10.0",
                "freeze_duration: 2.2",
                "freeze_end: 12.2",
                "freeze_start: 20.0",
                "freeze_duration: 2.4",
                "freeze_end: 22.4",
                "freeze_start: 30.0",
                "freeze_duration: 6.0",
                "freeze_end: 36.0",
            ]
        )
        result = gate.evaluate(
            returncode=0,
            stdout=progress(60),
            stderr=stderr,
            wall_seconds=64,
            policy=POLICY,
        )
        self.assertFalse(result.passed)
        self.assertIn("freeze_events_4", result.reason)
        self.assertIn("long_freeze_6.0s", result.reason)
        self.assertIn("total_freeze_13.1s", result.reason)

    def test_short_decode_and_http_failure_fail(self) -> None:
        result = gate.evaluate(
            returncode=1,
            stdout="out_time=00:00:06.60\n",
            stderr="HTTP error 503 Service Unavailable",
            wall_seconds=20,
            policy=POLICY,
        )
        self.assertFalse(result.passed)
        self.assertIn("ffmpeg_rc1", result.reason)
        self.assertIn("short_media_6.6s", result.reason)
        self.assertIn("network_errors_1", result.reason)

    def test_cloud_gate_uses_only_portable_ffmpeg_options(self) -> None:
        command = gate.command(
            "https://relay.example.test/live.m3u8",
            gate.APPLE_TV_USER_AGENT,
            POLICY,
        )
        self.assertNotIn("-allowed_segment_extensions", command)
        self.assertNotIn("-extension_picky", command)
        self.assertIn("-rw_timeout", command)


if __name__ == "__main__":
    unittest.main()
