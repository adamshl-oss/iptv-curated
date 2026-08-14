#!/usr/bin/env python3
"""Validate Algerian target identity, alias parity, and real playback."""

from __future__ import annotations

import concurrent.futures as futures
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "scripts" / "algerian_top20_target.json"
TEST = ROOT / "scripts" / "test_stream.sh"
PAGES_ROOT = "https://adamshl-oss.github.io/iptv-curated"
DEFAULT_PLAYLIST = f"{PAGES_ROOT}/algerian-tv-july-2026.m3u"
DEFAULT_ALIAS = f"{PAGES_ROOT}/algerian-tv-july-2026-v2.m3u"
RELAY_PREFIX = "https://algerian-tv-relay-2026.espiiem.chatgpt.site/"
# Each strict attempt reopens the public relay several times for probes, decode,
# and motion sampling. Bound shared-relay concurrency so the health check itself
# cannot manufacture 5xx/TLS timeouts as the published lineup grows.
RELAY_GATE = threading.Semaphore(2)
PLAYBACK_TEST_TIMEOUT_SECONDS = 105


def read(source: str) -> str:
    if source.startswith(("http://", "https://")):
        separator = "&" if "?" in source else "?"
        request = Request(
            f"{source}{separator}health={time.time_ns()}",
            headers={"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0"},
        )
        with urlopen(request, timeout=25) as response:
            return response.read().decode()
    return Path(source).read_text()


def entries(text: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        cursor = index + 1
        while cursor < len(lines) and (
            not lines[cursor] or lines[cursor].startswith("#")
        ):
            cursor += 1
        if cursor < len(lines) and lines[cursor].startswith(("http://", "https://")):
            result.append((line.rsplit(",", 1)[-1].strip(), lines[cursor].strip()))
    return result


def check(entry: tuple[str, str, int]) -> tuple[str, bool, str]:
    name, url, min_height = entry
    results: list[str] = []
    passed = 0
    for attempt in range(1, 4):
        try:
            relay_gate = RELAY_GATE if url.startswith(RELAY_PREFIX) else None
            if relay_gate is None:
                completed = subprocess.run(
                    [str(TEST), url],
                    capture_output=True,
                    text=True,
                    timeout=PLAYBACK_TEST_TIMEOUT_SECONDS,
                    check=False,
                )
            else:
                with relay_gate:
                    completed = subprocess.run(
                        [str(TEST), url],
                        capture_output=True,
                        text=True,
                        timeout=PLAYBACK_TEST_TIMEOUT_SECONDS,
                        check=False,
                    )
        except subprocess.TimeoutExpired:
            results.append(f"{attempt}:timeout")
        else:
            output = (completed.stdout or completed.stderr).strip()
            fields = output.split("|")
            if completed.returncode == 0 and fields and fields[0] == "PASS":
                media = " ".join(fields[3:5]) if len(fields) >= 5 else "decoded"
                try:
                    height = int(fields[4].split("x", 1)[1])
                except (IndexError, ValueError):
                    results.append(f"{attempt}:unreadable resolution ({media})")
                else:
                    if height < min_height:
                        results.append(
                            f"{attempt}:quality {height}p below {min_height}p"
                        )
                    else:
                        passed += 1
                        results.append(f"{attempt}:{media}, moving")
            else:
                detail = fields[2] if len(fields) > 2 else output or "unknown"
                results.append(f"{attempt}:{detail}")
        if attempt < 3:
            time.sleep(attempt)
    return name, passed == 3, f"{passed}/3; {'; '.join(results)}"


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    target_count = int(registry.get("target_count", 20))
    target = sorted(
        (
            channel
            for channel in registry["channels"]
            if int(channel.get("rank", 10_000)) <= target_count
        ),
        key=lambda channel: int(channel["rank"]),
    )
    published = sorted(
        (channel for channel in target if channel.get("publish") is True),
        key=lambda channel: int(channel["rank"]),
    )
    expected = [
        str(channel.get("playlist_name", channel["name"]))
        for channel in published
    ]
    if len(target) != target_count or [channel["rank"] for channel in target] != list(
        range(1, target_count + 1)
    ):
        print(f"FAIL\ttarget registry is not exactly ranks 1-{target_count}")
        return 1

    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYLIST
    alias = sys.argv[2] if len(sys.argv) > 2 else (
        DEFAULT_ALIAS if source == DEFAULT_PLAYLIST else None
    )
    actual = entries(read(source))
    names = [name for name, _ in actual]
    failed = names != expected
    if failed:
        print(f"FAIL\tidentity/order\texpected {expected!r}, found {names!r}")

    if alias:
        alias_entries = entries(read(alias))
        if alias_entries != actual:
            print("FAIL\talias parity\tidentity, order, or stream targets differ")
            failed = True
        else:
            print(f"PASS\talias parity\t{len(actual)} identical entries")

    minimums = {
        str(channel.get("playlist_name", channel["name"])): int(
            channel.get("min_height", 540)
        )
        for channel in published
    }
    checks = [(name, url, minimums[name]) for name, url in actual if name in minimums]
    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(check, checks))
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}\t{name}\t{detail}")
        failed = failed or not passed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
