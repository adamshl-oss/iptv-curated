#!/usr/bin/env python3
"""Reject French playlists that substitute unrelated channels.

The target file is the source of truth. A production playlist passes only
when it contains exactly those 30 channels, exactly once, in target order.
Playback validation remains a separate gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "scripts" / "french_top30_target.json"


def parse_entries(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    entries: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        cursor = index + 1
        while cursor < len(lines) and (
            not lines[cursor] or lines[cursor].startswith("#")
        ):
            cursor += 1
        url = lines[cursor].strip() if cursor < len(lines) else ""
        entries.append((line.rsplit(",", 1)[-1].strip(), url))
    return entries


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_french_top30.py PLAYLIST.m3u", file=sys.stderr)
        return 2

    target_payload = json.loads(TARGET.read_text())
    target_channels = target_payload["channels"]
    target_names = [channel["name"] for channel in target_channels]
    positions = [channel["position"] for channel in target_channels]

    failures: list[str] = []
    if positions != list(range(1, 31)):
        failures.append("target positions must be the integers 1 through 30")
    if len(set(target_names)) != 30:
        failures.append("target channel names must be unique")

    playlist = Path(sys.argv[1])
    entries = parse_entries(playlist.read_text())
    actual_names = [name for name, _ in entries]

    if len(entries) != 30:
        failures.append(f"playlist has {len(entries)} entries; expected 30")
    if len(set(actual_names)) != len(actual_names):
        failures.append("playlist contains duplicate channel names")

    missing = [name for name in target_names if name not in actual_names]
    unexpected = [name for name in actual_names if name not in target_names]
    if missing:
        failures.append("missing: " + ", ".join(missing))
    if unexpected:
        failures.append("unexpected substitutions: " + ", ".join(unexpected))
    if not missing and not unexpected and actual_names != target_names:
        failures.append("channels are not in target order")

    invalid_urls = [
        name for name, url in entries if not url.startswith(("https://", "http://"))
    ]
    if invalid_urls:
        failures.append("invalid or absent stream URL: " + ", ".join(invalid_urls))

    if failures:
        for failure in failures:
            print(f"FAIL\t{failure}")
        return 1

    print("PASS\tFrench playlist exactly matches the France Top 30 target")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
