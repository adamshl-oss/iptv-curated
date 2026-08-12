#!/usr/bin/env python3
"""Build the durable coverage truth for the curated IPTV playlists.

Playback health and target coverage are intentionally separate.  A controller
can run correctly while a lineup is still incomplete; this file prevents that
operational success from being mistaken for completion of the channel goal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = ROOT / "iptv-coverage-status.json"
REGISTRY_PATHS = {
    "france": ROOT / "scripts" / "french_top20_target.json",
    "algeria": ROOT / "scripts" / "algerian_top20_target.json",
}


def country_status(registry: dict[str, Any]) -> dict[str, Any]:
    target_count = registry.get("target_count")
    channels = sorted(
        (
            channel
            for channel in registry["channels"]
            if target_count is None
            or int(channel.get("rank", 10_000)) <= int(target_count)
        ),
        key=lambda channel: int(channel.get("rank", 10_000)),
    )
    published = [
        str(channel["name"])
        for channel in channels
        if channel.get("publish") is True
    ]
    missing = [
        {
            "rank": int(channel.get("rank", 0)),
            "name": str(channel["name"]),
            "status": str(channel.get("status", "unresolved")),
        }
        for channel in channels
        if channel.get("publish") is not True
    ]
    required_count = len(channels)
    published_count = len(published)
    state = "complete" if published_count == required_count else "degraded"
    return {
        "state": state,
        "published_count": published_count,
        "required_count": required_count,
        "published_names": published,
        "missing": missing,
    }


def build_status(
    registry_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    paths = registry_paths or REGISTRY_PATHS
    countries: dict[str, Any] = {}
    for country, path in paths.items():
        countries[country] = country_status(json.loads(path.read_text()))
    return {
        "version": 1,
        "definition": (
            "complete means every exact ranked target is currently published; "
            "operational audits never override this coverage state"
        ),
        "countries": countries,
    }


def render(status: dict[str, Any]) -> str:
    return json.dumps(status, ensure_ascii=False, indent=2) + "\n"


def write_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    status = build_status()
    body = render(status)
    if not path.exists() or path.read_text() != body:
        path.write_text(body)
    return status


def print_status(status: dict[str, Any]) -> None:
    for country, coverage in status["countries"].items():
        marker = (
            "COVERAGE_COMPLETE"
            if coverage["state"] == "complete"
            else "COVERAGE_DEGRADED"
        )
        missing = ", ".join(item["name"] for item in coverage["missing"])
        detail = (
            f"published={coverage['published_count']}/"
            f"{coverage['required_count']}"
        )
        if missing:
            detail += f"; missing={missing}"
        print(f"{marker}\t{country}\t{detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    status = build_status()
    body = render(status)
    if args.check:
        if not STATUS_PATH.exists() or STATUS_PATH.read_text() != body:
            print("FAIL\tcoverage status is stale")
            return 1
    else:
        write_status()

    print_status(status)
    incomplete = any(
        coverage["state"] != "complete"
        for coverage in status["countries"].values()
    )
    return 2 if args.require_complete and incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
