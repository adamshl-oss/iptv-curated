#!/usr/bin/env python3
"""Refresh official Algerian feeds behind stable GitHub Pages HLS URLs.

IPTV clients cache the top-level M3U for days, while broadcaster signatures
often expire in hours. The top-level playlist therefore contains only stable
cloud relay URLs. This job refreshes signed child URLs inside the wrappers; it
must never rewrite playlist membership, which belongs exclusively to the
self-healing controller and its target registry.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from curl_cffi import requests as browser_requests


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "algerian-tv-july-2026.m3u"
PLAYLIST_ALIAS = ROOT / "algerian-tv-july-2026-v2.m3u"
STREAMS = ROOT / "streams"
BEGIN = "#---ALGERIA-CLOUD-DYNAMIC-BEGIN---"
END = "#---ALGERIA-CLOUD-DYNAMIC-END---"
PAGES_ROOT = "https://adamshl-oss.github.io/iptv-curated"
RELAY_ROOT = "https://algerian-tv-relay-2026.espiiem.chatgpt.site"

ALMAGHARIBIA_HOME_API = (
    "https://api.prd.awraas.tv/api/v1/"
    "54450f8d-22d7-4942-adc6-4d30505c24a8/1/home"
)
YOUTUBE_PLAYER_ENDPOINTS = (
    "https://www.youtube.com/youtubei/v1/player",
    "https://youtubei.googleapis.com/youtubei/v1/player",
    "https://music.youtube.com/youtubei/v1/player",
    "https://www.youtube-nocookie.com/youtubei/v1/player",
)
ENNAHAR_PLAYER = "https://live.dzsecurity.net/live/player/ennahartv"
ENNAHAR_REFERER = "https://www.ennaharonline.com/live/"
ENNAHAR_YOUTUBE_LIVE = "https://www.youtube.com/@ennahartvonline/live"
ECHOROUK_PLAYER = "https://live.dzsecurity.net/live/player/echorouktv"
ECHOROUK_REFERER = "https://www.echoroukonline.com/live-"


def current_wrapper_url(slug: str) -> str | None:
    path = STREAMS / f"{slug}.m3u8"
    if not path.exists():
        return None
    for line in reversed(path.read_text().splitlines()):
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


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


def resolve_youtube_hls(target: str) -> str:
    command = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--skip-download",
        "--js-runtimes",
        "node",
        "--remote-components",
        "ejs:github",
    ]
    if server_home := os.environ.get("BGUTIL_SERVER_HOME"):
        command.extend(
            [
                "--extractor-args",
                f"youtubepot-bgutilscript:server_home={server_home}",
            ]
        )
    command.extend(
        [
            "--format",
            "best[protocol*=m3u8]",
            "--get-url",
            target,
        ]
    )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    url = completed.stdout.strip().splitlines()[0]
    if not url.startswith("https://") or ".m3u8" not in url:
        raise RuntimeError("YouTube resolver did not return an HLS manifest")
    return url


def resolve_youtube_player_hls(video_id: str) -> str:
    body = json.dumps(
        {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "20.10.38",
                    "androidSdkVersion": 30,
                    "hl": "en",
                    "gl": "US",
                }
            },
        }
    ).encode()
    last_error = "YouTube player API did not return a live HLS manifest"
    for attempt in range(1, 9):
        try:
            request = Request(
                YOUTUBE_PLAYER_ENDPOINTS[
                    (attempt - 1) % len(YOUTUBE_PLAYER_ENDPOINTS)
                ],
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": (
                        "com.google.android.youtube/20.10.38 "
                        "(Linux; U; Android 11) gzip"
                    ),
                    "X-YouTube-Client-Name": "3",
                    "X-YouTube-Client-Version": "20.10.38",
                    "Origin": "https://www.youtube.com",
                    "Referer": "https://www.youtube.com/",
                },
            )
            with urlopen(request, timeout=8) as response:
                payload = json.load(response)
            url = payload.get("streamingData", {}).get("hlsManifestUrl", "")
            parsed = urlparse(url)
            host = parsed.hostname or ""
            if (
                payload.get("playabilityStatus", {}).get("status") == "OK"
                and parsed.scheme == "https"
                and (
                    host == "manifest.googlevideo.com"
                    or host.endswith(".googlevideo.com")
                )
                and url_expiry(url) > time.time() + 900
            ):
                return url
            last_error = (
                payload.get("playabilityStatus", {}).get("reason")
                or last_error
            )
        except Exception as error:
            last_error = str(error)
        if attempt < 8:
            time.sleep(attempt * 0.15)
    raise RuntimeError(last_error)


def resolve_almagharibia() -> str:
    video_id = official_almagharibia_video_id()
    try:
        return resolve_youtube_player_hls(video_id)
    except Exception as player_error:
        try:
            return resolve_youtube_hls(
                f"https://www.youtube.com/watch?v={video_id}"
            )
        except Exception as extractor_error:
            raise RuntimeError(
                "Official YouTube resolvers failed: "
                f"player={player_error}; yt-dlp={extractor_error}"
            ) from extractor_error


def resolve_dzsecurity_site(
    player_url: str,
    referer: str,
    channel_path: str,
) -> str:
    response = browser_requests.get(
        player_url,
        headers={
            "Referer": referer,
            "Origin": re.match(r"https?://[^/]+", referer).group(0),
        },
        impersonate="safari",
        timeout=25,
    )
    response.raise_for_status()
    match = re.search(
        r"(?:https?:)?//hls-distrib-[a-z0-9-]+\.dzsecurity\.net/live/"
        + re.escape(channel_path)
        + r"/"
        r"playlist\.m3u8\?e=\d+(?:&|&amp;)token=[A-Za-z0-9_-]+",
        response.text,
    )
    if not match:
        raise RuntimeError("Official player did not expose a signed HLS URL")

    url = html.unescape(match.group(0))
    if url.startswith("//"):
        url = "https:" + url
    if url_expiry(url) <= time.time() + 900:
        raise RuntimeError("Official player returned an expiring URL")

    # DZSecurity's rendezvous currently accepts this signed request over HTTP
    # and immediately redirects to an HTTPS edge session.  The HTTPS
    # rendezvous itself returns no response on cloud runners, so resolve only
    # that first hop here and publish the resulting encrypted edge URL.
    rendezvous_url = "http:" + url.removeprefix("https:")
    try:
        rendezvous = browser_requests.get(
            rendezvous_url,
            headers={"Referer": player_url},
            impersonate="safari",
            allow_redirects=False,
            timeout=25,
        )
        if rendezvous.status_code not in {301, 302, 307, 308}:
            raise RuntimeError(
                f"Official HLS rendezvous returned HTTP {rendezvous.status_code}"
            )
        edge_url = str(rendezvous.headers.get("location") or "")
    except Exception as browser_error:
        # curl_cffi intermittently receives an empty reply from the plain-HTTP
        # rendezvous on Linux runners. Standard HTTP/1.1 curl reaches the same
        # 302 reliably; capture only its headers and never expose the signed
        # source URL in workflow output.
        completed = subprocess.run(
            [
                "curl",
                "--http1.1",
                "--silent",
                "--show-error",
                "--max-time",
                "25",
                "--dump-header",
                "-",
                "--output",
                "/dev/null",
                "--referer",
                player_url,
                rendezvous_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Official HLS rendezvous failed ({browser_error})"
            ) from browser_error
        location = re.search(
            r"(?im)^location:\s*(https://[^\r\n]+)", completed.stdout
        )
        edge_url = location.group(1).strip() if location else ""
    parsed = urlparse(edge_url)
    host = parsed.hostname or ""
    if not (
        parsed.scheme == "https"
        and host.startswith("hls-distrib-")
        and host.endswith(".dzsecurity.net")
        and parsed.path == f"/live/{channel_path}/playlist.m3u8"
        and parsed.query.startswith("session=")
    ):
        raise RuntimeError("Official HLS rendezvous returned an invalid edge URL")
    return edge_url


def resolve_ennahar_site() -> str:
    return resolve_dzsecurity_site(
        ENNAHAR_PLAYER,
        ENNAHAR_REFERER,
        "EnnaharTV",
    )


def resolve_echorouk() -> str:
    return resolve_dzsecurity_site(
        ECHOROUK_PLAYER,
        ECHOROUK_REFERER,
        "EchoroukTV",
    )


def resolve_ennahar() -> str:
    """Prefer Ennahar's full linear channel, with official YouTube as fallback."""
    try:
        return resolve_ennahar_site()
    except Exception as site_error:
        try:
            return resolve_youtube_hls(ENNAHAR_YOUTUBE_LIVE)
        except Exception as youtube_error:
            raise RuntimeError(
                f"official site unavailable ({site_error}); "
                f"official YouTube unavailable ({youtube_error})"
            ) from youtube_error


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
        if existing and url_expiry(existing) > time.time() + 900:
            print(f"{channel}: refresh failed; retained still-valid URL ({exc})")
            return existing
        raise


def refresh_or_keep(
    channel: str,
    existing: str | None,
    resolver,
    minimum_remaining: int,
    force_refresh: bool,
) -> str | None:
    """Refresh one channel without preventing the others from publishing."""
    try:
        return choose_url(
            channel,
            existing,
            resolver,
            minimum_remaining,
            force_refresh,
        )
    except Exception as exc:
        print(f"::warning::{channel} refresh unavailable ({exc})")
        return existing


def write_wrapper(slug: str, target: str) -> None:
    STREAMS.mkdir(exist_ok=True)
    (STREAMS / f"{slug}.m3u8").write_text(
        "\n".join(
            [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                (
                    "#EXT-X-STREAM-INF:BANDWIDTH=2200000,"
                    'RESOLUTION=1280x720,CODECS="avc1.640029,mp4a.40.2"'
                ),
                target,
                "",
            ]
        )
    )


def main() -> None:
    force_refresh = os.environ.get("FORCE_REFRESH", "").lower() == "true"
    almagharibia = refresh_or_keep(
        "Almagharibia",
        current_wrapper_url("almagharibia"),
        resolve_almagharibia,
        minimum_remaining=3600,
        force_refresh=force_refresh,
    )
    echorouk = refresh_or_keep(
        "Echorouk TV",
        current_wrapper_url("echorouk"),
        resolve_echorouk,
        minimum_remaining=1800,
        force_refresh=force_refresh,
    )
    refreshed = {
        "almagharibia": almagharibia,
        "echorouk": echorouk,
    }
    for slug, target in refreshed.items():
        if target:
            write_wrapper(slug, target)
    print("Refreshed Algerian signed wrappers; playlist membership unchanged")


if __name__ == "__main__":
    main()
