#!/usr/bin/env python3
"""Promote a validated candidate manifest to the fixed IPTVX client aliases."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANDIDATE = ROOT / "chaines-tv-candidate.m3u"
CLIENT_ALIASES = (ROOT / "iptvx.m3u", ROOT / "chaines-tv.m3u")


def validate(body: str) -> int:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise ValueError("candidate has no M3U header")
    pending = False
    count = 0
    for line in lines[1:]:
        if line.startswith("#EXTINF:"):
            if pending:
                raise ValueError("candidate has an EXTINF without a URL")
            pending = True
        elif line.startswith("#"):
            continue
        else:
            if not pending or not re.match(r"^https://", line):
                raise ValueError("candidate contains a malformed stream URL")
            pending = False
            count += 1
    if pending or count == 0:
        raise ValueError("candidate has no complete channel entries")
    return count


def promote(release: str) -> int:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-[a-z0-9]+)?", release):
        raise ValueError("release must be YYYY-MM-DD or YYYY-MM-DD-suffix")
    candidate = CANDIDATE.read_text()
    count = validate(candidate)
    lines = candidate.splitlines()
    lines[0] = '#EXTM3U playlist-name="IPTVX — Stable Release"'
    lines.insert(1, f"# Release: {release}; promoted from validated candidate.")
    body = "\n".join(lines) + "\n"
    releases = ROOT / "releases"
    releases.mkdir(exist_ok=True)
    (releases / f"iptvx-{release}.m3u").write_text(body)
    for alias in CLIENT_ALIASES:
        alias.write_text(body)
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    args = parser.parse_args()
    print(f"PROMOTED\t{promote(args.release)} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
