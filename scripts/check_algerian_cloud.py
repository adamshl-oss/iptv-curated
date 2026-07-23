#!/usr/bin/env python3
"""Smoke-test the two dynamic Algerian HLS manifests without exposing URLs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from curl_cffi import requests as browser_requests


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "algerian-tv-july-2026.m3u"
CHANNELS = ("Almagharibia TV", "Ennahar TV")


def dynamic_urls() -> dict[str, str]:
    lines = PLAYLIST.read_text().splitlines()
    found: dict[str, str] = {}
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF") or index + 1 >= len(lines):
            continue
        name = line.rsplit(",", 1)[-1]
        for channel in CHANNELS:
            if name.startswith(channel):
                found[channel] = lines[index + 1].strip()
    return found


def smoke_test(name: str, url: str) -> bool:
    try:
        response = browser_requests.get(
            url,
            impersonate="safari",
            allow_redirects=True,
            timeout=20,
        )
        response.raise_for_status()
        if not re.match(r"^\s*#EXTM3U", response.text):
            raise RuntimeError("response is not an HLS manifest")
        print(f"{name}: PASS (live HLS manifest)")
        return True
    except Exception as exc:
        print(f"{name}: FAIL ({type(exc).__name__}: {exc})")
        return False


def main() -> int:
    urls = dynamic_urls()
    results = [
        smoke_test(name, urls[name]) if name in urls else False
        for name in CHANNELS
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
