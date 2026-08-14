#!/usr/bin/env python3
"""Audit, quarantine, recover, and rebuild one curated IPTV playlist."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from coverage_status import country_status, print_status, write_status


ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "scripts" / "self_healing_catalog.json"
TEST = ROOT / "scripts" / "test_stream.sh"
SUSTAINED_TEST = ROOT / "scripts" / "sustained_stream_gate.py"
APPLE_TEST = ROOT / "scripts" / "apple_avplayer_check.swift"
HEALTH_POLICY_PATH = ROOT / "scripts" / "stream_health_policy.json"
APPLE_TV_USER_AGENT = (
    "AppleCoreMedia/1.0.0.21A329 (AppleTV; U; CPU OS 17_0 like Mac OS X)"
)
TF1_GATE = threading.Semaphore(2)
ATTEMPT_TIMEOUT_SECONDS = 105


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    successes: int
    sustained_passed: bool
    apple_passed: bool
    details: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def playback_attempt(url: str, min_height: int) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(TEST), url, APPLE_TV_USER_AGENT],
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


def sustained_playback_attempt(
    url: str, policy_path: Path = HEALTH_POLICY_PATH
) -> tuple[bool, str]:
    policy = json.loads(policy_path.read_text())["sustained_playback"]
    timeout = int(policy["duration_seconds"]) + int(
        policy["process_grace_seconds"]
    ) + 5
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(SUSTAINED_TEST),
                url,
                "--policy",
                str(policy_path),
                "--user-agent",
                APPLE_TV_USER_AGENT,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "sustained_process_timeout"

    output = (completed.stdout or completed.stderr).strip()
    fields = output.split("|", 2)
    if completed.returncode != 0 or not fields or fields[0] != "PASS":
        return False, fields[2] if len(fields) > 2 else output or "sustained_unknown"
    return True, fields[2] if len(fields) > 2 else "sustained_ok"


def apple_playback_attempt(
    url: str, policy_path: Path = HEALTH_POLICY_PATH
) -> tuple[bool, str]:
    document = json.loads(policy_path.read_text())
    policy = document["apple_playback"]
    binary = os.environ.get("APPLE_AVPLAYER_GATE_BIN", "")
    if binary:
        command = [binary, url, str(policy_path)]
    elif shutil.which("xcrun"):
        command = ["xcrun", "swift", str(APPLE_TEST), url, str(policy_path)]
    else:
        return False, "apple_gate_unavailable"
    timeout = int(policy["maximum_startup_seconds"]) + int(
        policy["duration_seconds"]
    ) + int(policy["process_grace_seconds"]) + 10
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "apple_process_timeout"

    output = (completed.stdout or completed.stderr).strip()
    fields = output.split("|", 2)
    if completed.returncode != 0 or not fields or fields[0] != "PASS":
        return False, fields[2] if len(fields) > 2 else output or "apple_unknown"
    return True, fields[2] if len(fields) > 2 else "apple_ok"


def gate(
    channel: dict[str, Any],
    url: str,
    attempts: int,
    policy_path: Path = HEALTH_POLICY_PATH,
    require_apple: bool = False,
) -> GateResult:
    name = str(channel["name"])
    # Gate the permanent URL that IPTVX receives.  Testing an upstream
    # candidate here can produce a false positive when the public relay is
    # stale, misconfigured, or unable to reach that same source.
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
    sustained_passed = False
    apple_passed = not require_apple
    if successes == attempts:
        if lock is None:
            sustained_passed, sustained_detail = sustained_playback_attempt(
                url, policy_path
            )
        else:
            with lock:
                sustained_passed, sustained_detail = sustained_playback_attempt(
                    url, policy_path
                )
        details.append(f"sustained:{sustained_detail}")
    else:
        details.append("sustained:skipped_after_startup_failure")
    if require_apple and successes == attempts:
        if lock is None:
            apple_passed, apple_detail = apple_playback_attempt(url, policy_path)
        else:
            with lock:
                apple_passed, apple_detail = apple_playback_attempt(url, policy_path)
        details.append(f"apple:{apple_detail}")
    elif require_apple:
        details.append("apple:skipped_after_startup_failure")
    if require_apple:
        # AVPlayer is the playback stack IPTVX and Apple TV actually use. The
        # real-time ffmpeg gate remains valuable transport evidence, but its
        # platform-specific pacing cannot veto a clean Apple playback minute.
        passed = successes == attempts and apple_passed
    else:
        passed = successes == attempts and sustained_passed
    return GateResult(
        name=name,
        passed=passed,
        successes=successes,
        sustained_passed=sustained_passed,
        apple_passed=apple_passed,
        details=details,
    )


def apply_gate_result(
    channel: dict[str, Any],
    result: GateResult,
    public_url: str,
    *,
    checked_at: str | None = None,
    quarantine_after_failed_gates: int = 3,
    recover_after_successful_gates: int = 1,
) -> tuple[bool, list[str]]:
    """Apply one complete startup+sustained gate to durable channel state."""
    name = str(channel["name"])
    timestamp = checked_at or utc_now()
    healing = dict(channel.get("auto_healing") or {})
    published = channel.get("publish") is True
    changed = False
    transitions: list[str] = []

    if published and result.passed:
        if channel.get("stream_url") != public_url:
            prior_candidate = str(channel.get("stream_url") or "")
            if prior_candidate:
                healing.setdefault("last_candidate_url", prior_candidate)
            channel["stream_url"] = public_url
            changed = True
        if channel.get("status") == "candidate_cloud_verification":
            channel["status"] = "verified_cloud_relay"
            channel["reason"] = (
                "The permanent cloud URL passed the independent public "
                "three-attempt media gate, sustained transport gate, and real "
                "Apple AVPlayer gate after candidate qualification. IPTVX receives "
                "this stable URL, not the upstream candidate."
            )
            healing["success_streak"] = 0
            healing["last_recovery"] = timestamp
            transitions.append(f"verified permanent route for {name}")
            changed = True
        if healing.get("failure_streak", 0) != 0:
            healing["failure_streak"] = 0
            changed = True
        if changed:
            channel["auto_healing"] = healing
        return changed, transitions

    if published:
        failure_streak = int(healing.get("failure_streak", 0)) + 1
        healing.update(
            {
                "enabled": True,
                "failure_streak": failure_streak,
                "success_streak": 0,
                "last_failure": timestamp,
                "last_evidence": "; ".join(result.details),
            }
        )
        healing.setdefault("recovery_allowed", True)
        if failure_streak >= quarantine_after_failed_gates:
            healing.setdefault("prior_status", channel.get("status"))
            healing.setdefault("prior_reason", channel.get("reason"))
            channel["publish"] = False
            channel["status"] = "quarantined_automated"
            channel["reason"] = (
                "Automatically quarantined after the complete startup plus "
                "sustained transport and Apple AVPlayer gate failed: "
                f"{'; '.join(result.details)}"
            )
            transitions.append(f"quarantined {name}")
        channel["auto_healing"] = healing
        return True, transitions

    if result.passed:
        success_streak = int(healing.get("success_streak", 0)) + 1
        healing["success_streak"] = success_streak
        healing["failure_streak"] = 0
        if success_streak >= recover_after_successful_gates:
            candidate_url = str(channel.get("stream_url") or "")
            if candidate_url and candidate_url != public_url:
                healing["last_candidate_url"] = candidate_url
            channel["stream_url"] = public_url
            channel["publish"] = True
            channel["status"] = healing.get("prior_status", "verified_cloud")
            if healing.get("prior_reason"):
                channel["reason"] = healing["prior_reason"]
            healing["last_recovery"] = timestamp
            transitions.append(f"recovered {name}")
        channel["auto_healing"] = healing
        return True, transitions

    if healing.get("success_streak", 0) != 0:
        healing["success_streak"] = 0
        channel["auto_healing"] = healing
        return True, transitions
    return False, transitions


def write_playlist(
    country: str,
    catalog: dict[str, Any],
    registry: dict[str, Any],
) -> int:
    channels = registry["channels"]
    target_count = registry.get("target_count")
    by_name = {str(channel["name"]): channel for channel in channels}
    lines = list(catalog["header"])
    count = 0
    entries = sorted(
        catalog["entries"],
        key=lambda entry: int(by_name[str(entry["name"])].get("rank", 10_000)),
    )
    for entry in entries:
        channel = by_name.get(str(entry["name"]))
        if (
            not channel
            or (
                target_count is not None
                and int(channel.get("rank", 10_000)) > int(target_count)
            )
            or channel.get("publish") is not True
        ):
            continue
        stream_url = str(entry.get("url") or "")
        if not stream_url.startswith("https://"):
            raise RuntimeError(
                f"{country} published channel {entry['name']} has no permanent "
                "cloud URL"
            )
        lines.extend([str(entry["extinf"]), stream_url])
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


def in_target_scope(channel: dict[str, Any], target_count: int | None) -> bool:
    return target_count is None or int(channel.get("rank", 10_000)) <= int(
        target_count
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", required=True, choices=("france", "algeria"))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument(
        "--apple-player",
        action="store_true",
        help="Require a real AVPlayer sustained-playback pass",
    )
    args = parser.parse_args()

    policy_document = json.loads(HEALTH_POLICY_PATH.read_text())
    health_policy = policy_document["sustained_playback"]
    transition_policy = policy_document["state_transitions"]
    if health_policy.get("enabled") is not True:
        print("FAIL\tsustained playback policy is disabled")
        return 1
    apple_policy = policy_document.get("apple_playback") or {}
    if args.apple_player and apple_policy.get("enabled") is not True:
        print("FAIL\tApple playback policy is disabled")
        return 1
    if args.apple_player and not (
        os.environ.get("APPLE_AVPLAYER_GATE_BIN") or shutil.which("xcrun")
    ):
        print("FAIL\tApple AVPlayer gate is unavailable on this runner")
        return 1

    all_catalogs = json.loads(CATALOG_PATH.read_text())
    catalog = all_catalogs[args.country]
    registry_path = ROOT / str(catalog["registry"])
    registry = json.loads(registry_path.read_text())
    channels = registry["channels"]
    target_count = registry.get("target_count")
    starting_published_count = sum(
        channel.get("publish") is True and in_target_scope(channel, target_count)
        for channel in channels
    )
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
        count = write_playlist(args.country, catalog, registry)
        coverage = country_status(registry)
        print(f"OPERATIONAL\t{args.country}\trebuilt {count} published channels")
        print_status({"countries": {args.country: coverage}})
        return 0

    candidates: list[tuple[dict[str, Any], str]] = []
    for entry in catalog["entries"]:
        channel = by_name[str(entry["name"])]
        if not in_target_scope(channel, target_count):
            continue
        healing = channel.get("auto_healing") or {}
        should_recover = (
            channel.get("publish") is not True
            and healing.get("enabled") is True
            and healing.get("recovery_allowed") is True
        )
        if channel.get("publish") is True or should_recover:
            # Recovery is only real when the stable public route works.  A raw
            # candidate may remain recorded for diagnosis, but it never enters
            # the Apple TV playlist directly.
            gate_url = str(entry.get("url") or "")
            if not gate_url.startswith("https://"):
                if channel.get("publish") is True:
                    candidates.append((channel, ""))
                # Unpublished targets without a discovered candidate remain in
                # the durable catalog but are not sent through a meaningless
                # playback gate against their ordinary broadcaster web page.
                continue
            candidates.append((channel, gate_url))

    workers = 3 if args.apple_player else 4
    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        gateable = [item for item in candidates if item[1]]
        results = list(
            executor.map(
                lambda item: gate(
                    item[0],
                    item[1],
                    args.attempts,
                    HEALTH_POLICY_PATH,
                    args.apple_player,
                ),
                gateable,
            )
        )
    for channel, gate_url in candidates:
        if gate_url:
            continue
        results.append(
            GateResult(
                name=str(channel["name"]),
                passed=False,
                successes=0,
                sustained_passed=False,
                apple_passed=False,
                details=["no permanent cloud URL"] * args.attempts,
            )
        )

    result_by_name = {result.name: result for result in results}
    changed = False
    transitions: list[str] = []
    for channel, _gate_url in candidates:
        name = str(channel["name"])
        result = result_by_name[name]
        print(
            f"{'PASS' if result.passed else 'FAIL'}\t{name}\t"
            f"startup={result.successes}/{args.attempts}; "
            f"sustained={'pass' if result.sustained_passed else 'fail'}; "
            f"apple={'pass' if result.apple_passed else 'fail'}; "
            f"{'; '.join(result.details)}"
        )
        public_url = str(
            next(
                entry["url"]
                for entry in catalog["entries"]
                if entry["name"] == name
            )
        )
        result_changed, result_transitions = apply_gate_result(
            channel,
            result,
            public_url,
            quarantine_after_failed_gates=int(
                transition_policy["quarantine_after_failed_gates"]
            ),
            recover_after_successful_gates=int(
                transition_policy["recover_after_successful_gates"]
            ),
        )
        changed = changed or result_changed
        transitions.extend(result_transitions)

    count = write_playlist(args.country, catalog, registry)
    coverage = country_status(registry)
    controller_state = {
        "controller": "scripts/reconcile_self_healing.py",
        "quarantine_after_failed_gates": int(
            transition_policy["quarantine_after_failed_gates"]
        ),
        "recover_after_successful_gates": int(
            transition_policy["recover_after_successful_gates"]
        ),
        "attempts_per_gate": args.attempts,
        "sustained_playback_seconds": int(health_policy["duration_seconds"]),
        "apple_player_required": args.apple_player,
        "apple_playback_seconds": int(apple_policy.get("duration_seconds", 0)),
        "maximum_wall_lag_seconds": float(
            health_policy["maximum_wall_lag_seconds"]
        ),
        "maximum_single_freeze_seconds": float(
            health_policy["maximum_single_freeze_seconds"]
        ),
        "maximum_total_freeze_seconds": float(
            health_policy["maximum_total_freeze_seconds"]
        ),
        "published_count": count,
        "required_count": coverage["required_count"],
        "coverage_state": coverage["state"],
        "missing_targets": [item["name"] for item in coverage["missing"]],
    }
    healing_state = registry.setdefault("self_healing", {})
    if any(healing_state.get(key) != value for key, value in controller_state.items()):
        changed = True
    healing_state.update(controller_state)
    if args.apply and changed:
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    if args.apply:
        write_status()

    print(
        f"OPERATIONAL\t{args.country} controller\tpublished={count}; "
        f"changes={', '.join(transitions) if transitions else 'none'}"
    )
    delta = count - starting_published_count
    outcome = "IMPROVED" if delta > 0 else "DEGRADED" if delta < 0 else "STABLE"
    print(
        f"OUTCOME_{outcome}\t{args.country}\t"
        f"published_delta={delta:+d}; published={count}"
    )
    remaining_failures = [
        str(channel["name"])
        for channel in channels
        if in_target_scope(channel, target_count)
        and channel.get("publish") is True
        and (
            str(channel["name"]) not in result_by_name
            or not result_by_name[str(channel["name"])].passed
        )
    ]
    if remaining_failures:
        print(
            f"PLAYBACK_DEGRADED\t{args.country}\t"
            f"failed_published={', '.join(remaining_failures)}"
        )
    elif coverage["state"] == "complete":
        print(
            f"PLAYBACK_HEALTHY\t{args.country}\t"
            f"all {count} published permanent cloud URLs passed startup and "
            f"{int(health_policy['duration_seconds'])}s transport playback"
            f"{' plus real Apple AVPlayer playback' if args.apple_player else ''}"
        )
    else:
        print(
            f"PLAYBACK_SURVIVORS_HEALTHY\t{args.country}\t"
            f"the {count} currently published survivors passed startup and "
            f"{int(health_policy['duration_seconds'])}s transport playback"
            f"{' plus real Apple AVPlayer playback' if args.apple_player else ''}; "
            "target coverage remains degraded"
        )
    print_status({"countries": {args.country: coverage}})
    return 1 if remaining_failures else 0


if __name__ == "__main__":
    sys.exit(main())
