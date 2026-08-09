#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_combined_playlist.py")
SPEC = importlib.util.spec_from_file_location("combined_playlist_tests", MODULE_PATH)
assert SPEC and SPEC.loader
combined = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combined)


class CombinedPlaylistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_source(self, name: str, entries: list[tuple[str, str]]) -> Path:
        path = self.root / name
        lines = ["#EXTM3U", "# controller metadata"]
        for extinf, url in entries:
            lines.extend((extinf, url))
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_combines_verified_country_outputs_in_order(self) -> None:
        france = self.write_source(
            "france.m3u",
            [
                (
                    '#EXTINF:-1 tvg-id="TF1.fr" group-title="France",TF1',
                    "https://relay.example/france/tf1",
                )
            ],
        )
        algeria = self.write_source(
            "algeria.m3u",
            [
                (
                    '#EXTINF:-1 tvg-id="TV1.dz" group-title="Algeria",TV1',
                    "https://relay.example/algeria/tv1",
                )
            ],
        )
        output = self.root / "chaines-tv.m3u"

        count = combined.build((france, algeria), output)
        body = output.read_text()

        self.assertEqual(count, 2)
        self.assertTrue(body.startswith('#EXTM3U playlist-name="CHAINES TV"\n'))
        self.assertLess(body.index("TF1.fr"), body.index("TV1.dz"))
        self.assertEqual(body.count("#EXTINF:"), 2)

    def test_rejects_non_https_streams(self) -> None:
        source = self.write_source(
            "bad.m3u",
            [("#EXTINF:-1,Bad TV", "http://relay.example/bad")],
        )
        with self.assertRaisesRegex(ValueError, "not HTTPS"):
            combined.build((source,), self.root / "out.m3u")

    def test_rejects_duplicate_channel_identity(self) -> None:
        identity = '#EXTINF:-1 tvg-id="Same.tv" group-title="Test"'
        one = self.write_source(
            "one.m3u", [(identity + ",Same One", "https://relay.example/one")]
        )
        two = self.write_source(
            "two.m3u", [(identity + ",Same Two", "https://relay.example/two")]
        )
        with self.assertRaisesRegex(ValueError, "duplicate channel identity"):
            combined.build((one, two), self.root / "out.m3u")


if __name__ == "__main__":
    unittest.main()
