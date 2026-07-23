#!/usr/bin/env python3
"""Refresh the two official Algerian feeds that do not have permanent HLS URLs.

The generated URLs are committed to the public playlist by GitHub Actions. A
previous URL is retained if a broadcaster is temporarily unavailable so one
failed refresh never deletes a channel from IPTVX.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

from curl_cffi import requests as browser_requests


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "algerian-tv-july-2026.m3u"
BEGIN = "#---ALGERIA-CLOUD-DYNAMIC-BEGIN---"
END = "#---ALGERIA-CLOUD-DYNAMIC-END---"

ALMAGHARIBIA_HOME_API = (
    "https://api.prd.awraas.tv/api/v1/"
    "54450f8d-22d7-4942-adc6-4d30505c24a8/1/home"
)
ENNAHAR_PLAYER = "https://live.dzsecurity.net/live/player/ennahartv"
ENNAHAR_REFERER = "https://www.ennaharonline.com/live/"


def current_urls(text: str) -> dict[str, str]:
    match = re.search(
        re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.DOTALL
    )
    if not match:
        return {}

    found: dict[str, str] = {}
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.startswith("#EXTINF") and index + 1 < len(lines):
            name = line.rsplit(",", 1)[-1]
            found[name.split(" (", 1)[0]] = lines[index + 1]
    return found


def url_expiry(url: str) -> int:
    youtube = re.search(r"/expire/(\d+)/", url)
    if youtube:
        return int(youtube.group(1))
    ennahar = re.search(r"[?&]e=(\d+)", url)
    if ennahar:
        return int(ennahar.group(1))
    return 0


def official_almagharibia_video_id() -> str:
    request = Request(
        ALMAGHARIBIA_HOME_API,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    embed = payload["stream"]["embed_code"]
    match = re.search(r"/embed/([A-Za-z0-9_-]{11})", embed)
    if not match:
        raise RuntimeError("Official Almagharibia app did not expose a live video")
    return match.group(1)


def resolve_almagharibia() -> str:
    video_id = official_almagharibia_video_id()
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-warnings",
            "--no-playlist",
            "--skip-download",
            "--js-runtimes",
            "node",
            "--remote-components",
            "ejs:github",
            "--format",
            "best[protocol*=m3u8]",
            "--get-url",
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    url = completed.stdout.strip().splitlines()[0]
    if not url.startswith("https://") or ".m3u8" not in url:
        raise RuntimeError("YouTube resolver did not return an HLS manifest")
    return url


def resolve_ennahar() -> str:
    response = browser_requests.get(
        ENNAHAR_PLAYER,
        headers={
            "Referer": ENNAHAR_REFERER,
            "Origin": "https://www.ennaharonline.com",
        },
        impersonate="safari",
        timeout=25,
    )
    response.raise_for_status()
    match = re.search(
        r"(?:https?:)?//hls-distrib-rlb1\.dzsecurity\.net/live/EnnaharTV/"
        r"playlist\.m3u8\?e=\d+(?:&|&amp;)token=[A-Za-z0-9_-]+",
        response.text,
    )
    if not match:
        raise RuntimeError("Official Ennahar player did not expose a signed HLS URL")

    url = html.unescape(match.group(0))
    if url.startswith("//"):
        url = "https:" + url
    if url_expiry(url) <= time.time() + 900:
        raise RuntimeError("Official Ennahar player returned an expiring URL")
    return url


def choose_url(
    channel: str,
    existing: str | None,
    resolver,
    minimum_remaining: int,
    force_refresh: bool = False,
) -> str:
    if (
        not force_refresh
        and existing
        and url_expiry(existing) > time.time() + minimum_remaining
    ):
        print(f"{channel}: retained current cloud URL")
        return existing
    try:
        resolved = resolver()
        print(f"{channel}: refreshed from official source")
        return resolved
    except Exception as exc:
        if existing:
            print(f"{channel}: refresh failed; retained previous URL ({exc})")
            return existing
        raise


def render(almagharibia: str, ennahar: str) -> str:
    return "\n".join(
        [
            BEGIN,
            '#EXTINF:-1 tvg-id="AlmagharibiaTV.uk" '
            'tvg-logo="https://i.imgur.com/XE6OWcb.png" '
            'group-title="Algeria — Cloud Verified",'
            "Almagharibia TV (Official Cloud Live)",
            almagharibia,
            '#EXTINF:-1 tvg-id="EnnaharTV.dz" '
            'tvg-logo="https://i.imgur.com/C0TCA1s.png" '
            'group-title="Algeria — Cloud Verified",'
            "Ennahar TV (Official Cloud Live)",
            ennahar,
            END,
        ]
    )


def main() -> None:
    text = PLAYLIST.read_text()
    existing = current_urls(text)
    force_refresh = os.environ.get("FORCE_REFRESH", "").lower() == "true"
    almagharibia = choose_url(
        "Almagharibia",
        existing.get("Almagharibia TV"),
        resolve_almagharibia,
        minimum_remaining=3600,
        force_refresh=force_refresh,
    )
    ennahar = choose_url(
        "Ennahar",
        existing.get("Ennahar TV"),
        resolve_ennahar,
        minimum_remaining=1200,
        force_refresh=force_refresh,
    )
    block = render(almagharibia, ennahar)
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError("Dynamic Algerian playlist markers are missing")
    PLAYLIST.write_text(pattern.sub(block, text))
    print("Updated algerian-tv-july-2026.m3u with 2 dynamic cloud channels")


if __name__ == "__main__":
    main()
