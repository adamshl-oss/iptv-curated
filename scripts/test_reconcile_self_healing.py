#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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
        count = reconcile.write_playlist("france", self.catalog, channels)
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
                [{"name": "Fixture TV", "publish": True}],
            )


if __name__ == "__main__":
    unittest.main()
