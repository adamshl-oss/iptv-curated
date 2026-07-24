#!/usr/bin/env python3
"""Smoke-test the published Algerian HLS lineup and live media segments."""

from __future__ import annotations

import re
import sys
from urllib.parse import urljoin

from curl_cffi.const import CurlHttpVersion
from curl_cffi import requests as browser_requests


RELAY_ROOT = "https://algerian-tv-relay-2026.espiiem.chatgpt.site"
CHANNELS = {
    "AL24 News": f"{RELAY_ROOT}/api/free/al24",
    "TV1": f"{RELAY_ROOT}/api/free/tv1",
    "TV2": "http://185.9.2.18/chid_347/index.m3u8",
    "TV3": f"{RELAY_ROOT}/api/free/tv3",
    "TV4": f"{RELAY_ROOT}/api/free/tv4",
    "TV5": f"{RELAY_ROOT}/api/free/tv5",
    "TV6": f"{RELAY_ROOT}/api/free/tv6",
    "Echorouk News": f"{RELAY_ROOT}/api/free/echorouknews",
    "Ennahar TV": f"{RELAY_ROOT}/api/free/ennahar",
    "El Heddaf TV": f"{RELAY_ROOT}/api/free/elheddaf",
    "El Bilad TV": f"{RELAY_ROOT}/api/free/elbilad",
    "Amou Yazid TV": f"{RELAY_ROOT}/api/free/amouyazid",
    "Almagharibia TV": f"{RELAY_ROOT}/api/youtube/almagharibia",
}


def dynamic_urls() -> dict[str, str]:
    return CHANNELS


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
