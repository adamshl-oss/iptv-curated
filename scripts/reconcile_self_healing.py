#!/usr/bin/env python3
"""Audit, quarantine, recover, and rebuild one curated IPTV playlist."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "scripts" / "self_healing_catalog.json"
TEST = ROOT / "scripts" / "test_stream.sh"
TF1_GATE = threading.Semaphore(2)
ATTEMPT_TIMEOUT_SECONDS = 105


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    successes: int
    details: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def playback_attempt(url: str, min_height: int) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(TEST), url],
            capture_output=True,
            text=True,
            timeout=ATTEMPT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"

    output = (completed.stdout or completed.stderr).strip()
    fields = output.split("|")
    if completed.returncode != 0 or not fields or fields[0] != "PASS":
        return False, fields[2] if len(fields) > 2 else output or "unknown"
    try:
        height = int(fields[4].split("x", 1)[1])
    except (IndexError, ValueError):
        return False, "unreadable resolution"
    if height < min_height:
        return False, f"quality {height}p below {min_height}p"
    media = " ".join(fields[3:5]) if len(fields) >= 5 else "decoded"
    return True, f"{media}, moving"


def gate(channel: dict[str, Any], attempts: int) -> GateResult:
    name = str(channel["name"])
    url = str(channel["stream_url"])
    min_height = int(channel.get("min_height", 540))
    details: list[str] = []
    successes = 0
    lock = TF1_GATE if "/api/french/tf1/" in url else None
    for number in range(1, attempts + 1):
        if lock is None:
            passed, detail = playback_attempt(url, min_height)
        else:
            with lock:
                passed, detail = playback_attempt(url, min_height)
        if passed:
            successes += 1
        details.append(f"{number}:{detail}")
        if number < attempts:
            time.sleep(number)
    return GateResult(
        name=name,
        passed=successes == attempts,
        successes=successes,
        details=details,
    )


def write_playlist(
    country: str,
    catalog: dict[str, Any],
    channels: list[dict[str, Any]],
) -> int:
    by_name = {str(channel["name"]): channel for channel in channels}
    lines = list(catalog["header"])
    count = 0
    for entry in catalog["entries"]:
        channel = by_name.get(str(entry["name"]))
        if not channel or channel.get("publish") is not True:
            continue
        stream_url = channel.get("stream_url") or entry["url"]
        lines.extend([str(entry["extinf"]), str(stream_url)])
        count += 1
    lines.extend(catalog.get("footer", []))
    body = "\n".join(lines) + "\n"
    canonical = ROOT / str(catalog["canonical"])
    alias = ROOT / str(catalog["alias"])
    canonical.write_text(body)
    alias.write_text(body)
    if canonical.read_bytes() != alias.read_bytes():
        raise RuntimeError(f"{country} canonical and alias differ after rebuild")
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", required=True, choices=("france", "algeria"))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()

    all_catalogs = json.loads(CATALOG_PATH.read_text())
    catalog = all_catalogs[args.country]
    registry_path = ROOT / str(catalog["registry"])
    registry = json.loads(registry_path.read_text())
    channels = registry["channels"]
    by_name = {str(channel["name"]): channel for channel in channels}

    missing = [
        entry["name"]
        for entry in catalog["entries"]
        if entry["name"] not in by_name
    ]
    if missing:
        print(f"FAIL\tcatalog entries missing from registry\t{missing}")
        return 1

    if args.build_only:
        count = write_playlist(args.country, catalog, channels)
        print(f"PASS\t{args.country}\trebuilt {count} published channels")
        return 0

    candidates: list[dict[str, Any]] = []
    for entry in catalog["entries"]:
        channel = by_name[str(entry["name"])]
        healing = channel.get("auto_healing") or {}
        should_recover = (
            channel.get("publish") is not True
            and healing.get("enabled") is True
            and healing.get("recovery_allowed") is True
        )
        if channel.get("publish") is True or should_recover:
            if not channel.get("stream_url"):
                channel["stream_url"] = entry["url"]
            candidates.append(channel)

    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda item: gate(item, args.attempts), candidates)
        )

    result_by_name = {result.name: result for result in results}
    changed = False
    transitions: list[str] = []
    unhandled_failure = False
    for channel in candidates:
        name = str(channel["name"])
        result = result_by_name[name]
        print(
            f"{'PASS' if result.passed else 'FAIL'}\t{name}\t"
            f"{result.successes}/{args.attempts}; {'; '.join(result.details)}"
        )
        healing = dict(channel.get("auto_healing") or {})
        published = channel.get("publish") is True

        if published and result.passed:
            if healing.get("failure_streak", 0) != 0:
                healing["failure_streak"] = 0
                channel["auto_healing"] = healing
                changed = True
            continue

        if published:
            failure_streak = int(healing.get("failure_streak", 0)) + 1
            healing.update(
                {
                    "enabled": True,
                    "failure_streak": failure_streak,
                    "success_streak": 0,
                    "last_failure": utc_now(),
                    "last_evidence": "; ".join(result.details),
                }
            )
            healing.setdefault("recovery_allowed", True)
            if failure_streak >= 2:
                healing.setdefault("prior_status", channel.get("status"))
                healing.setdefault("prior_reason", channel.get("reason"))
                channel["publish"] = False
                channel["status"] = "quarantined_automated"
                channel["reason"] = (
                    "Automatically quarantined after two consecutive complete "
                    f"cloud playback gates failed: {'; '.join(result.details)}"
                )
                transitions.append(f"quarantined {name}")
            else:
                unhandled_failure = True
            channel["auto_healing"] = healing
            changed = True
            continue

        if result.passed:
            success_streak = int(healing.get("success_streak", 0)) + 1
            healing["success_streak"] = success_streak
            healing["failure_streak"] = 0
            if success_streak >= 2:
                channel["publish"] = True
                channel["status"] = healing.get("prior_status", "verified_cloud")
                if healing.get("prior_reason"):
                    channel["reason"] = healing["prior_reason"]
                healing["last_recovery"] = utc_now()
                transitions.append(f"recovered {name}")
            channel["auto_healing"] = healing
            changed = True
        elif healing.get("success_streak", 0) != 0:
            healing["success_streak"] = 0
            channel["auto_healing"] = healing
            changed = True

    count = write_playlist(args.country, catalog, channels)
    registry.setdefault("self_healing", {})
    registry["self_healing"].update(
        {
            "controller": "scripts/reconcile_self_healing.py",
            "quarantine_after_failed_gates": 2,
            "recover_after_successful_gates": 2,
            "attempts_per_gate": args.attempts,
            "published_count": count,
        }
    )
    if args.apply and changed:
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")

    print(
        f"PASS\t{args.country} controller\tpublished={count}; "
        f"changes={', '.join(transitions) if transitions else 'none'}"
    )
    return 1 if unhandled_failure else 0


if __name__ == "__main__":
    sys.exit(main())
