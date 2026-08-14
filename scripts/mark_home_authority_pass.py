#!/usr/bin/env python3
"""Record a successful native Apple playback check from the home authority."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "scripts" / "algerian_top20_target.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()

    document = json.loads(REGISTRY.read_text())
    channel = next(
        item for item in document["channels"] if item["name"] == args.channel
    )
    if channel.get("health_authority") != "home_avplayer":
        raise SystemExit(f"{args.channel} is not owned by the home Apple authority")
    wrapper = ROOT / str(channel["health_authority_wrapper"])
    evidence_path = ROOT / str(channel["health_authority_evidence"])
    evidence_path.write_text(
        json.dumps(
            {
                "channel": channel["name"],
                "checked_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
                "evidence": args.evidence,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
