#!/usr/bin/env python3
"""Smoke-test dynamic Algerian HLS manifests without exposing their URLs."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi.const import CurlHttpVersion
from curl_cffi import requests as browser_requests


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "algerian-tv-july-2026.m3u"
CHANNELS = ("Almagharibia TV", "Echorouk TV", "Ennahar TV")


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
            http_version=CurlHttpVersion.V1_1,
            allow_redirects=True,
            timeout=20,
        )
        response.raise_for_status()
        if not re.match(r"^\s*#EXTM3U", response.text):
            raise RuntimeError("response is not an HLS manifest")

        manifest = response.text
        manifest_url = str(response.url)
        if "#EXT-X-STREAM-INF" in manifest:
            variants = [
                line.strip()
                for line in manifest.splitlines()
                if line.strip() and not line.startswith("#")
            ]
            if not variants:
                raise RuntimeError("master manifest has no variants")
            media_response = browser_requests.get(
                urljoin(manifest_url, variants[-1]),
                impersonate="safari",
                http_version=CurlHttpVersion.V1_1,
                allow_redirects=True,
                timeout=20,
            )
            media_response.raise_for_status()
            if not re.match(r"^\s*#EXTM3U", media_response.text):
                raise RuntimeError("variant is not an HLS media manifest")
            manifest = media_response.text
            manifest_url = str(media_response.url)

        segments = [
            line.strip()
            for line in manifest.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not segments:
            raise RuntimeError("media manifest has no live segments")
        segment_response = browser_requests.get(
            urljoin(manifest_url, segments[-1]),
            impersonate="safari",
            http_version=CurlHttpVersion.V1_1,
            allow_redirects=True,
            timeout=20,
        )
        segment_response.raise_for_status()
        if len(segment_response.content) < 4096:
            raise RuntimeError("live media segment is unexpectedly small")

        print(f"{name}: PASS (manifest and live media segment)")
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
