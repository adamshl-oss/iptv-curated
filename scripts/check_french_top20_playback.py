#!/usr/bin/env python3
"""Validate target identity, public count, and real playback for French top 20."""

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
REGISTRY = ROOT / "scripts" / "french_top20_target.json"
TEST = ROOT / "scripts" / "test_stream.sh"
DEFAULT_PLAYLIST = (
    "https://adamshl-oss.github.io/iptv-curated/"
    "french-tv-top20-july-2026.m3u"
)
DEFAULT_ALIAS = (
    "https://adamshl-oss.github.io/iptv-curated/"
    "french-tv-july-2026-v5.m3u"
)
TF1_RELAY_PREFIX = (
    "https://algerian-tv-relay-2026.espiiem.chatgpt.site/api/french/"
)
TF1_RELAY_GATE = threading.Lock()


def read(source: str) -> str:
    if source.startswith(("http://", "https://")):
        separator = "&" if "?" in source else "?"
        request = Request(
            f"{source}{separator}health={int(time.time())}",
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
            # A single playback test deliberately fetches the master several
            # times (curl, ffprobe, ffmpeg, re-probe, and motion decode).
            # Serialise this shared resolver family so the health check itself
            # cannot create a burst that upstream mistakes for abuse.
            relay_gate = TF1_RELAY_GATE if url.startswith(TF1_RELAY_PREFIX) else None
            if relay_gate is None:
                completed = subprocess.run(
                    [str(TEST), url],
                    capture_output=True,
                    text=True,
                    timeout=70,
                    check=False,
                )
            else:
                with relay_gate:
                    completed = subprocess.run(
                        [str(TEST), url],
                        capture_output=True,
                        text=True,
                        timeout=70,
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
    target = json.loads(REGISTRY.read_text())["channels"]
    expected = [str(channel["name"]) for channel in target if channel.get("publish") is True]
    if len(target) != 20 or [channel["rank"] for channel in target] != list(range(1, 21)):
        print("FAIL\ttarget registry is not exactly ranks 1-20")
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
        str(channel["name"]): int(channel.get("min_height", 540))
        for channel in target
        if channel.get("publish") is True
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
