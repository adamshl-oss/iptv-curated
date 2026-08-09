#!/usr/bin/env python3
"""Build the single IPTVX-facing CHAINES TV playlist.

The country playlists remain internal controller outputs.  This file is the
only playlist the user subscribes to, and is rebuilt in the same commit as
every country-level quarantine or recovery.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCES = (
    ROOT / "french-tv-top20-july-2026.m3u",
    ROOT / "algerian-tv-july-2026.m3u",
)
OUTPUT = ROOT / "chaines-tv.m3u"
HEADER = (
    '#EXTM3U playlist-name="CHAINES TV"',
    "# Combined verified French and Algerian channels.",
    "# Rebuilt automatically after every quarantine or recovery.",
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


def build(sources: tuple[Path, ...] = SOURCES, output: Path = OUTPUT) -> int:
    lines = list(HEADER)
    seen_ids: set[str] = set()
    count = 0
    for source in sources:
        source_entries = entries(source)
        lines.append(f"# Source: {source.name}")
        for extinf, url in source_entries:
            identity = extinf.split(",", 1)[0]
            if identity in seen_ids:
                raise ValueError(f"duplicate channel identity: {identity}")
            seen_ids.add(identity)
            lines.extend((extinf, url))
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
                print("FAIL\tCHAINES TV is stale")
                return 1
    else:
        count = build()
    print(f"PASS\tCHAINES TV\t{count} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
