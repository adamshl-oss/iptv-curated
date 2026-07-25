#!/usr/bin/env python3
"""Decode-test every entry in the public or local French playlist."""

from __future__ import annotations

import concurrent.futures as futures
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAYLIST = (
    "https://adamshl-oss.github.io/iptv-curated/"
    "french-tv-july-2026-v3.m3u"
)
TEST = ROOT / "scripts" / "test_stream.sh"
EXPECTED_CHANNELS = 32
PARALLEL_TESTS = 6


def read_playlist(source: str) -> str:
    if source.startswith(("http://", "https://")):
        separator = "&" if "?" in source else "?"
        request = Request(
            f"{source}{separator}health={int(time.time())}",
            headers={"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0"},
        )
        with urlopen(request, timeout=25) as response:
            return response.read().decode()
    return Path(source).read_text()


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
        if cursor < len(lines) and lines[cursor].startswith(("http://", "https://")):
            entries.append((line.rsplit(",", 1)[-1].strip(), lines[cursor].strip()))
    return entries


def check(entry: tuple[str, str]) -> tuple[str, bool, str, str]:
    name, url = entry
    try:
        completed = subprocess.run(
            [str(TEST), url],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return name, False, "", "test_timeout"
    fields = (completed.stdout or completed.stderr).strip().split("|")
    if completed.returncode == 0 and fields and fields[0] == "PASS":
        codec = fields[3] if len(fields) > 3 else ""
        resolution = fields[4] if len(fields) > 4 else ""
        return name, True, f"{codec}\t{resolution}", "ok"
    reason = fields[2] if len(fields) > 2 else "unknown failure"
    return name, False, "", reason


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYLIST
    entries = parse_entries(read_playlist(source))
    failed = len(entries) != EXPECTED_CHANNELS
    if failed:
        print(
            f"FAIL\tplaylist count\tfound {len(entries)}, "
            f"expected {EXPECTED_CHANNELS}"
        )

    with futures.ThreadPoolExecutor(max_workers=PARALLEL_TESTS) as executor:
        results = list(executor.map(check, entries))

    for name, passed, media, reason in results:
        if passed:
            print(f"PASS\t{name}\t{media}\tok")
        else:
            failed = True
            print(f"FAIL\t{name}\t{reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
