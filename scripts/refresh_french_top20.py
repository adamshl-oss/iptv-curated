#!/usr/bin/env python3
"""Publish the exact, independently verified subset of France's audience top 20."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "scripts" / "french_top20_target.json"
TEST = ROOT / "scripts" / "test_stream.sh"
CANONICAL = ROOT / "french-tv-top20-july-2026.m3u"
CURRENT_IPTVX_ALIASES = (
    ROOT / "french-tv-july-2026-v5.m3u",
    ROOT / "french-tv-july-2026-v6.m3u",
)
TEST_TIMEOUT_SECONDS = 70


def resolve(channel: dict[str, object]) -> str:
    static = str(channel.get("stream_url", ""))
    refresh_wrapper = str(channel.get("refresh_wrapper", ""))
    if not refresh_wrapper and static.startswith(("http://", "https://")):
        return static

    resolver = channel.get("resolver")
    if not isinstance(resolver, dict) or resolver.get("type") != "yt_dlp":
        raise RuntimeError(f"{channel['name']}: no supported stream resolver")
    page_url = str(resolver.get("url", ""))
    completed = subprocess.run(
        [
            "yt-dlp",
            "--no-warnings",
            "--skip-download",
            "--get-url",
            "--socket-timeout",
            "20",
            page_url,
        ],
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )
    urls = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith(("http://", "https://"))
    ]
    if completed.returncode != 0 or not urls:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{channel['name']}: resolver failed: {detail}")
    resolved = urls[0]
    preferred_live_filename = str(resolver.get("preferred_live_filename", ""))
    if preferred_live_filename:
        resolved, replacements = re.subn(
            r"/live-[^/?]+\.m3u8",
            f"/{preferred_live_filename}",
            resolved,
            count=1,
        )
        if replacements != 1:
            raise RuntimeError(
                f"{channel['name']}: could not select preferred live rendition"
            )
    return resolved


def write_wrapper(relative_path: str, url: str) -> None:
    target = ROOT / relative_path
    rendered = "\n".join(
        [
            "#EXTM3U",
            "# Current official CNEWS Dailymotion 720p live rendition.",
            url,
            "",
        ]
    )
    if not target.exists() or target.read_text() != rendered:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        print(f"WRITE\t{target.relative_to(ROOT)}")


def playback_test(name: str, url: str, min_height: int) -> str:
    last_reason = "unknown failure"
    for attempt in range(1, 4):
        try:
            completed = subprocess.run(
                [str(TEST), url],
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_reason = f"attempt {attempt} timed out"
            if attempt < 3:
                time.sleep(attempt * 2)
            continue
        output = (completed.stdout or completed.stderr).strip()
        fields = output.split("|")
        if completed.returncode == 0 and fields and fields[0] == "PASS":
            codec = fields[3] if len(fields) > 3 else "unknown"
            resolution = fields[4] if len(fields) > 4 else "unknown"
            try:
                height = int(resolution.rsplit("x", 1)[-1])
            except (ValueError, IndexError):
                raise RuntimeError(
                    f"{name}: could not verify resolution: {resolution}"
                )
            if height < min_height:
                raise RuntimeError(
                    f"{name}: decoded at {resolution}; minimum is {min_height}p"
                )
            return f"{codec} {resolution}"
        last_reason = fields[2] if len(fields) > 2 else output or last_reason
        if attempt < 3:
            time.sleep(attempt * 2)
    raise RuntimeError(
        f"{name}: playback validation failed after 3 attempts: {last_reason}"
    )


def render(channels: list[dict[str, object]], urls: dict[str, str]) -> str:
    lines = [
        "#EXTM3U",
        "# France audience top 20 audited individually on 2026-07-25.",
        "# Only exact linear channels that pass cloud-independent playback are published.",
    ]
    for channel in channels:
        name = str(channel["name"])
        attributes = [
            f'tvg-id="{channel["tvg_id"]}"',
            f'tvg-chno="{channel["rank"]}"',
            f'group-title="France Top 20 — Verified"',
        ]
        logo = str(channel.get("logo", ""))
        if logo:
            attributes.append(f'tvg-logo="{logo}"')
        lines.append(f'#EXTINF:-1 {" ".join(attributes)},{name}')
        lines.append(urls[name])
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = json.loads(REGISTRY.read_text())
    all_channels = payload["channels"]
    if len(all_channels) != 20:
        raise RuntimeError(f"Target registry has {len(all_channels)} channels, expected 20")
    if [channel["rank"] for channel in all_channels] != list(range(1, 21)):
        raise RuntimeError("Target registry ranks must be exactly 1 through 20")

    published = [channel for channel in all_channels if channel.get("publish") is True]
    if not published:
        raise RuntimeError("No top-20 channels are approved for publication")

    urls: dict[str, str] = {}
    for channel in published:
        name = str(channel["name"])
        url = resolve(channel)
        detail = playback_test(name, url, int(channel.get("min_height", 540)))
        refresh_wrapper = str(channel.get("refresh_wrapper", ""))
        if refresh_wrapper:
            write_wrapper(refresh_wrapper, url)
            public_url = str(channel.get("stream_url", ""))
            if not public_url.startswith(("http://", "https://")):
                raise RuntimeError(f"{name}: dynamic wrapper has no public relay URL")
            urls[name] = public_url
        else:
            urls[name] = url
        print(f"PASS\t#{channel['rank']}\t{name}\t{detail}")

    rendered = render(published, urls)
    for target in (CANONICAL, *CURRENT_IPTVX_ALIASES):
        if not target.exists() or target.read_text() != rendered:
            target.write_text(rendered)
            print(f"WRITE\t{target.name}")
    print(f"Published {len(published)} verified exact channels from the audited top 20")


if __name__ == "__main__":
    main()
