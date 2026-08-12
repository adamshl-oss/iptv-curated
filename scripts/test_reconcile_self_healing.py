#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("reconcile_self_healing.py")
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("reconcile_self_healing_tests", MODULE_PATH)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reconcile
SPEC.loader.exec_module(reconcile)


class PermanentPublicUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.original_root = reconcile.ROOT
        reconcile.ROOT = Path(self.temporary.name)
        self.addCleanup(setattr, reconcile, "ROOT", self.original_root)
        self.catalog = {
            "header": ["#EXTM3U"],
            "canonical": "canonical.m3u",
            "alias": "alias.m3u",
            "entries": [
                {
                    "name": "Fixture TV",
                    "extinf": '#EXTINF:-1 tvg-id="Fixture.test",Fixture TV',
                    "url": "https://relay.example.test/api/fixture/live.m3u8",
                }
            ],
        }

    def test_playlist_uses_permanent_route_not_candidate_upstream(self) -> None:
        channels = [
            {
                "name": "Fixture TV",
                "publish": True,
                "stream_url": "https://upstream.example.test/expiring.m3u8",
            }
        ]
        count = reconcile.write_playlist(
            "france", self.catalog, {"channels": channels}
        )
        body = (reconcile.ROOT / "canonical.m3u").read_text()
        self.assertEqual(count, 1)
        self.assertIn("https://relay.example.test/api/fixture/live.m3u8", body)
        self.assertNotIn("upstream.example.test", body)
        self.assertEqual(
            (reconcile.ROOT / "canonical.m3u").read_bytes(),
            (reconcile.ROOT / "alias.m3u").read_bytes(),
        )

    def test_published_channel_without_cloud_route_is_rejected(self) -> None:
        self.catalog["entries"][0]["url"] = ""
        with self.assertRaisesRegex(RuntimeError, "no permanent cloud URL"):
            reconcile.write_playlist(
                "france",
                self.catalog,
                {"channels": [{"name": "Fixture TV", "publish": True}]},
            )


class SustainedControllerTests(unittest.TestCase):
    def test_startup_success_cannot_hide_sustained_failure(self) -> None:
        channel = {"name": "Fixture TV", "min_height": 540}
        with (
            mock.patch.object(
                reconcile,
                "playback_attempt",
                return_value=(True, "h264/aac 1280x720, moving"),
            ) as startup,
            mock.patch.object(
                reconcile,
                "sustained_playback_attempt",
                return_value=(False, "buffering_21.0s"),
            ) as sustained,
            mock.patch.object(reconcile.time, "sleep"),
        ):
            result = reconcile.gate(
                channel,
                "https://relay.example.test/live.m3u8",
                3,
                Path("policy.json"),
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.successes, 3)
        self.assertFalse(result.sustained_passed)
        self.assertTrue(result.apple_passed)
        self.assertEqual(startup.call_count, 3)
        sustained.assert_called_once()
        self.assertIn("sustained:buffering_21.0s", result.details)

    def test_sustained_gate_is_skipped_when_startup_is_already_broken(self) -> None:
        channel = {"name": "Fixture TV", "min_height": 540}
        with (
            mock.patch.object(
                reconcile,
                "playback_attempt",
                side_effect=[
                    (True, "moving"),
                    (False, "http_503"),
                    (True, "moving"),
                ],
            ),
            mock.patch.object(
                reconcile, "sustained_playback_attempt"
            ) as sustained,
            mock.patch.object(reconcile.time, "sleep"),
        ):
            result = reconcile.gate(
                channel,
                "https://relay.example.test/live.m3u8",
                3,
                Path("policy.json"),
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.successes, 2)
        sustained.assert_not_called()
        self.assertIn("sustained:skipped_after_startup_failure", result.details)

    def test_real_apple_gate_is_required_when_requested(self) -> None:
        channel = {"name": "Fixture TV", "min_height": 540}
        with (
            mock.patch.object(
                reconcile,
                "playback_attempt",
                return_value=(True, "h264/aac 1280x720, moving"),
            ),
            mock.patch.object(
                reconcile,
                "sustained_playback_attempt",
                return_value=(True, "sustained_ok"),
            ),
            mock.patch.object(
                reconcile,
                "apple_playback_attempt",
                return_value=(False, "total_stall_18.0s"),
            ) as apple,
            mock.patch.object(reconcile.time, "sleep"),
        ):
            result = reconcile.gate(
                channel,
                "https://relay.example.test/live.m3u8",
                3,
                Path("policy.json"),
                require_apple=True,
            )

        self.assertFalse(result.passed)
        self.assertTrue(result.sustained_passed)
        self.assertFalse(result.apple_passed)
        apple.assert_called_once()
        self.assertIn("apple:total_stall_18.0s", result.details)

    def test_clean_apple_playback_overrides_platform_specific_ffmpeg_pacing(self) -> None:
        channel = {"name": "Fixture TV", "min_height": 540}
        with (
            mock.patch.object(
                reconcile,
                "playback_attempt",
                return_value=(True, "h264/aac 1280x720, moving"),
            ),
            mock.patch.object(
                reconcile,
                "sustained_playback_attempt",
                return_value=(False, "buffering_43.0s"),
            ),
            mock.patch.object(
                reconcile,
                "apple_playback_attempt",
                return_value=(True, "apple_ok; stalls=0"),
            ) as apple,
            mock.patch.object(reconcile.time, "sleep"),
        ):
            result = reconcile.gate(
                channel,
                "https://relay.example.test/live.m3u8",
                3,
                Path("policy.json"),
                require_apple=True,
            )

        self.assertTrue(result.passed)
        self.assertFalse(result.sustained_passed)
        self.assertTrue(result.apple_passed)
        apple.assert_called_once()
        self.assertIn("sustained:buffering_43.0s", result.details)
        self.assertIn("apple:apple_ok; stalls=0", result.details)

    def test_three_failures_quarantine_and_one_clean_apple_gate_restores(self) -> None:
        channel = {
            "name": "Fixture TV",
            "publish": True,
            "status": "verified_cloud",
            "reason": "Previously verified",
            "stream_url": "https://relay.example.test/live.m3u8",
            "auto_healing": {"enabled": True, "recovery_allowed": True},
        }
        failed = reconcile.GateResult(
            name="Fixture TV",
            passed=False,
            successes=3,
            sustained_passed=False,
            apple_passed=False,
            details=["sustained:buffering_21.0s"],
        )
        passed = reconcile.GateResult(
            name="Fixture TV",
            passed=True,
            successes=3,
            sustained_passed=True,
            apple_passed=True,
            details=["sustained:sustained_ok"],
        )
        public_url = "https://relay.example.test/live.m3u8"

        changed, transitions = reconcile.apply_gate_result(
            channel, failed, public_url, checked_at="2026-08-08T00:00:00Z"
        )
        self.assertTrue(changed)
        self.assertEqual(transitions, [])
        self.assertTrue(channel["publish"])
        self.assertEqual(channel["status"], "verified_cloud")
        self.assertEqual(channel["auto_healing"]["failure_streak"], 1)

        _, transitions = reconcile.apply_gate_result(
            channel, failed, public_url, checked_at="2026-08-08T00:30:00Z"
        )
        self.assertEqual(transitions, [])
        self.assertTrue(channel["publish"])
        self.assertEqual(channel["status"], "verified_cloud")
        self.assertEqual(channel["auto_healing"]["failure_streak"], 2)

        _, transitions = reconcile.apply_gate_result(
            channel, failed, public_url, checked_at="2026-08-08T01:00:00Z"
        )
        self.assertEqual(transitions, ["quarantined Fixture TV"])
        self.assertFalse(channel["publish"])
        self.assertEqual(channel["status"], "quarantined_automated")
        self.assertIn("buffering_21.0s", channel["reason"])

        _, transitions = reconcile.apply_gate_result(
            channel, passed, public_url, checked_at="2026-08-08T01:30:00Z"
        )
        self.assertEqual(transitions, ["recovered Fixture TV"])
        self.assertTrue(channel["publish"])
        self.assertEqual(channel["status"], "verified_cloud")
        self.assertEqual(channel["reason"], "Previously verified")


if __name__ == "__main__":
    unittest.main()
