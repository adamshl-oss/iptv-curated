#!/usr/bin/env python3
"""Build the candidate CHAINES TV playlist.

The country playlists remain internal controller outputs. This candidate is
rebuilt after every quarantine or recovery. Client devices consume the frozen
``chaines-tv.m3u`` release, changed only by explicit promotion.
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCES = (
    ROOT / "french-tv-top20-july-2026.m3u",
    ROOT / "algerian-tv-july-2026.m3u",
)
OUTPUT = ROOT / "chaines-tv-candidate.m3u"
COUNTRY_GROUPS = ("France — CHAINES TV", "Algérie — CHAINES TV")
# Match the relay's viewer-facing order.  Recovered channels that are not yet
# listed here retain their source-controller order after the known services.
PREFERRED_IDENTITIES = (
    (
        "TF1.fr",
        "CNews.fr",
        "ARTE.fr",
        "TMC.fr",
        "BFMTV.fr",
        "LCI.fr",
        "TFX.fr",
        "RMCDecouverte.fr",
        "RMCStory.fr",
        "TF1SeriesFilms.fr",
        "LEquipe.fr",
        "CStar.fr",
        "RMCLife.fr",
    ),
    (
        "AL24News.dz",
        "TV1.dz",
        "TV2.dz",
        "TV3.dz",
        "EnnaharTV.dz",
        "EchoroukTV.dz",
        "EchoroukNews.dz",
        "ElHeddafTV.dz",
        "ElBilad.dz",
    ),
)
HEADER = (
    '#EXTM3U url-tvg="https://adamshl-oss.github.io/iptv-curated/epg.xml.gz" playlist-name="CHAINES TV"',
    "# Combined verified French and Algerian channels.",
    "# Candidate: rebuilt automatically after every quarantine or recovery.",
)


def entries(path: Path) -> list[tuple[str, str]]:
    """Return strict EXTINF/URL pairs while rejecting malformed inputs."""
    result: list[tuple[str, str]] = []
    pending: str | None = None
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") and not line.startswith("#EXTINF:"):
            continue
        if line.startswith("#EXTINF:"):
            if pending is not None:
                raise ValueError(f"{path}:{number}: EXTINF has no stream URL")
            pending = line
            continue
        if pending is None:
            raise ValueError(f"{path}:{number}: stream URL has no EXTINF")
        if not line.startswith("https://"):
            raise ValueError(f"{path}:{number}: stream URL is not HTTPS")
        result.append((pending, line))
        pending = None
    if pending is not None:
        raise ValueError(f"{path}: final EXTINF has no stream URL")
    return result


def combined_extinf(extinf: str, group_name: str) -> str:
    """Set the IPTVX country category while preserving channel metadata."""
    metadata, separator, name = extinf.partition(",")
    if not separator:
        raise ValueError("EXTINF has no channel name")
    group = f'group-title="{group_name}"'
    if re.search(r'\bgroup-title="[^"]*"', metadata):
        metadata = re.sub(r'\bgroup-title="[^"]*"', group, metadata, count=1)
    else:
        metadata = f"{metadata} {group}"
    return f"{metadata},{name}"


def identity(extinf: str) -> str:
    """Return the stable channel identity needed for country ordering."""
    match = re.search(r'\btvg-id="([^"]+)"', extinf)
    if not match:
        raise ValueError("EXTINF has no tvg-id")
    return match.group(1)


def ordered_entries(source_entries: list[tuple[str, str]], country_index: int) -> list[tuple[str, str]]:
    """Keep the published source complete while prioritizing the Relay order."""
    priorities = {
        channel_id: position
        for position, channel_id in enumerate(PREFERRED_IDENTITIES[country_index])
    }
    return [
        entry
        for _, entry in sorted(
            enumerate(source_entries),
            key=lambda item: (priorities.get(identity(item[1][0]), len(priorities)), item[0]),
        )
    ]


def build(sources: tuple[Path, ...] = SOURCES, output: Path = OUTPUT) -> int:
    lines = list(HEADER)
    seen_ids: set[str] = set()
    count = 0
    for country_index, source in enumerate(sources):
        source_entries = entries(source)
        group_name = (
            COUNTRY_GROUPS[country_index]
            if country_index < len(COUNTRY_GROUPS)
            else "CHAINES TV"
        )
        lines.append(f"# Source: {source.name}")
        for extinf, url in ordered_entries(source_entries, country_index):
            channel_identity = identity(extinf)
            if channel_identity in seen_ids:
                raise ValueError(f"duplicate channel identity: {channel_identity}")
            seen_ids.add(channel_identity)
            lines.extend((combined_extinf(extinf, group_name), url))
            count += 1

    body = "\n".join(lines) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", text=True
    )
    try:
        with os.fdopen(descriptor, "w") as temporary:
            temporary.write(body)
        os.replace(temporary_name, output)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        expected = OUTPUT.read_text() if OUTPUT.exists() else ""
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / OUTPUT.name
            count = build(SOURCES, candidate)
            if candidate.read_text() != expected:
                print("FAIL\tCHAINES TV candidate is stale")
                return 1
    else:
        count = build()
    print(f"PASS\tCHAINES TV\t{count} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
