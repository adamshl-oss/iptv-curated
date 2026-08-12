#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError


COVERAGE_MODULE_PATH = Path(__file__).with_name("coverage_status.py")
COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "coverage_status", COVERAGE_MODULE_PATH
)
assert COVERAGE_SPEC and COVERAGE_SPEC.loader
coverage = importlib.util.module_from_spec(COVERAGE_SPEC)
sys.modules[COVERAGE_SPEC.name] = coverage
COVERAGE_SPEC.loader.exec_module(coverage)

MODULE_PATH = Path(__file__).with_name("discover_channel_sources.py")
SPEC = importlib.util.spec_from_file_location("source_discovery", MODULE_PATH)
assert SPEC and SPEC.loader
discovery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = discovery
SPEC.loader.exec_module(discovery)


class DiscoveryPolicyTests(unittest.TestCase):
    def test_exact_tvg_id_is_stronger_than_display_noise(self) -> None:
        parsed = discovery.parse_m3u(
            '#EXTM3U\n#EXTINF:-1 tvg-id="France2.fr",France 2 HD\n'
            'https://official.example/live/france2.m3u8\n',
            "france",
            "fixture",
            True,
        )
        target = {"name": "France 2", "tvg_id": "France2.fr"}
        matched = discovery.match_candidate("france", target, parsed[0])
        self.assertIsNotNone(matched)
        self.assertEqual(matched.match_basis, "exact_tvg_id")

    def test_raw_ip_and_credentials_cannot_be_promoted(self) -> None:
        for url in (
            "https://203.0.113.4/live.m3u8",
            "https://user:pass@example.com/live.m3u8",
            "http://official.example/live.m3u8",
        ):
            safe, _ = discovery.safe_stream_url(url)
            self.assertFalse(safe, url)

    def test_signed_url_expiring_soon_is_not_stable(self) -> None:
        discovery.time.time = lambda: 1_000_000
        stable, reason = discovery.stable_stream_url(
            "https://official.example/live.m3u8?expires=1000300"
        )
        self.assertFalse(stable)
        self.assertIn("expires", reason)

    def test_vod_manifest_is_rejected(self) -> None:
        original = discovery.fetch_text
        discovery.fetch_text = lambda *_args, **_kwargs: (
            "#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-ENDLIST\n"
        )
        try:
            live, reason = discovery.live_manifest(
                "https://official.example/recording.m3u8"
            )
        finally:
            discovery.fetch_text = original
        self.assertFalse(live)
        self.assertIn("ended", reason)

    def test_en_clair_substitute_is_not_exact_canal_plus(self) -> None:
        candidate = discovery.Candidate(
            country="france",
            target="Canal+",
            target_tvg_id="CanalPlus.fr",
            candidate_name="CANAL+ EN CLAIR",
            candidate_tvg_id="CanalPlus.fr",
            url="https://official.example/canalplus.m3u8",
            source="fixture",
            trusted=True,
            match_basis="exact_tvg_id",
        )
        exact, _ = discovery.exact_channel_identity(candidate)
        self.assertFalse(exact)

    def test_opaque_official_page_stream_needs_identity_evidence(self) -> None:
        candidate = discovery.Candidate(
            country="france",
            target="France 2",
            target_tvg_id="France2.fr",
            candidate_name="France 2",
            candidate_tvg_id="France2.fr",
            url="https://cdn.example/opaque/abc123/live.m3u8",
            source="official-page:france.tv",
            trusted=True,
            match_basis="official_page",
        )
        exact, _ = discovery.exact_channel_identity(candidate)
        self.assertFalse(exact)

    def test_new_candidate_enters_second_gate_not_publication(self) -> None:
        target = {
            "name": "France 2",
            "status": "geo_restricted",
            "reason": "old evidence",
            "publish": False,
        }
        candidate = discovery.Candidate(
            country="france",
            target="France 2",
            target_tvg_id="France2.fr",
            candidate_name="France 2",
            candidate_tvg_id="France2.fr",
            url="https://official.example/france2/live.m3u8",
            source="official-page:example",
            trusted=True,
            match_basis="official_page",
        )
        discovery.apply_candidate(target, candidate, ["1:pass", "2:pass", "3:pass"])
        self.assertFalse(target["publish"])
        self.assertEqual(target["auto_healing"]["success_streak"], 1)
        self.assertTrue(target["auto_healing"]["recovery_allowed"])

    def test_github_rate_limit_is_retried_instead_of_skipping_target(self) -> None:
        original_fetch = discovery.fetch_text
        original_sleep = discovery.time.sleep
        calls = 0
        sleeps: list[int] = []
        headers = Message()
        headers["Retry-After"] = "1"

        def fake_fetch(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise HTTPError(
                    "https://api.github.com/search/code",
                    429,
                    "Too Many Requests",
                    headers,
                    None,
                )
            return '{"items": []}'

        discovery.fetch_text = fake_fetch
        discovery.time.sleep = sleeps.append
        try:
            candidates = discovery.github_candidates(
                "france",
                {"name": "France 2", "tvg_id": "France2.fr"},
                "token",
                set(),
                3,
            )
        finally:
            discovery.fetch_text = original_fetch
            discovery.time.sleep = original_sleep

        self.assertEqual(candidates, [])
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [10])

    def test_official_only_is_a_supported_command_line_mode(self) -> None:
        parser = discovery.argparse.ArgumentParser()
        self.assertIsNotNone(parser)
        self.assertIn("--official-only", MODULE_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
