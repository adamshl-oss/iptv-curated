#!/usr/bin/env python3
"""Promote a validated candidate manifest to the fixed IPTVX client aliases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from audit_client_playlist import identity, assess, assert_player_environment
from build_combined_playlist import entries
from reconcile_self_healing import HEALTH_POLICY_PATH


ROOT = Path(__file__).resolve().parent.parent
CANDIDATE = ROOT / "chaines-tv-candidate.m3u"
CLIENT_ALIASES = (ROOT / "iptvx.m3u", ROOT / "chaines-tv.m3u")


def passes(check: dict) -> bool:
    return bool(check.get("passed") and check.get("successes") == 3
                and check.get("apple_passed") is True
                and assess(dict(check)).get("passed"))


def durably_quarantined(key: str, url: str) -> bool:
    threshold = json.loads(HEALTH_POLICY_PATH.read_text()).get(
        "state_transitions", {}).get("quarantine_after_failed_gates", 3)
    history = ROOT / "releases" / "client-health.json"
    if history.exists():
        row = json.loads(history.read_text()).get("channels", {}).get(key, {}).get("sources", {}).get(url, {})
        if row.get("url") == url and row.get("failure_streak", 0) >= threshold:
            return True
    for filename in ("french_top20_target.json", "algerian_top20_target.json"):
        path = ROOT / "scripts" / filename
        if not path.exists():
            continue
        for channel in json.loads(path.read_text())["channels"]:
            if (channel.get("tvg_id") == key and channel.get("stream_url") == url
                    and channel.get("publish") is False
                    and channel.get("auto_healing", {}).get("failure_streak", 0) >= threshold):
                return True
    return False


def record_health(report: dict) -> None:
    if report.get("infrastructure_circuit_breaker", {}).get("open"):
        return
    path = ROOT / "releases" / "client-health.json"
    document = json.loads(path.read_text()) if path.exists() else {"channels": {}}
    for row in report["results"]:
        key = row["tvg_id"]
        sources = document["channels"].setdefault(key, {}).setdefault("sources", {})
        prior = sources.get(row["url"], {})
        if (prior.get("checked_at") and datetime.fromisoformat(report["checked_at"])
                <= datetime.fromisoformat(prior["checked_at"])):
            continue
        if prior.get("url") != row["url"]:
            prior = {}
        passed = passes(row)
        streak = 0 if passed else prior.get("failure_streak", 0) + (not row.get("audit_error", False))
        sources[row["url"]] = dict(
            url=row["url"], checked_at=report["checked_at"], failure_streak=streak,
            playback_passed=passed, quality_passed=row.get("quality_passed", False),
            details=row["details"])
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


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


def verified_entries(report: dict) -> list[tuple[str, str]]:
    if report.get("apple_required") is not True:
        raise ValueError("real Apple playback evidence is required")
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(report["checked_at"])).total_seconds()
    if not 0 <= age <= 7200:
        raise ValueError("playback evidence is stale or future-dated")
    if report.get("policy_sha256") != hashlib.sha256(HEALTH_POLICY_PATH.read_bytes()).hexdigest():
        raise ValueError("playback policy changed since audit")
    for path in (CANDIDATE, CLIENT_ALIASES[1]):
        if report.get("source_hashes", {}).get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"{path.name} changed since audit; retry against fresh snapshot")
    if CLIENT_ALIASES[0].read_bytes() != CLIENT_ALIASES[1].read_bytes():
        raise ValueError("client aliases disagree")
    evidence = {(r["tvg_id"], r["url"]): r for r in report["results"]}
    old = {identity(info): (info, url) for info, url in entries(CLIENT_ALIASES[1])}
    result = []
    seen = set()
    decisions = {"degraded_retained": [], "quality_degraded_retained": [],
                 "unproven_skipped": [], "quarantined": []}
    if report.get("infrastructure_circuit_breaker", {}).get("open"):
        # A shared relay/DNS failure is infrastructure evidence, not proof that
        # many independent channels died simultaneously. Freeze the client
        # release and preserve every prior channel until the control plane is
        # healthy again.
        decisions["degraded_retained"] = list(old)
        report["promotion_decisions"] = decisions
        return list(old.values())
    for info, url in entries(CANDIDATE):
        key = identity(info)
        if key in seen:
            raise ValueError("duplicate candidate identity")
        seen.add(key)
        check = evidence.get((key, url), {})
        is_existing = key in old and old[key][1] == url
        if passes(check) and (assess(dict(check)).get("quality_passed") or is_existing):
            result.append((info, url))
        elif key in old:
            result.append(old[key])
            if not passes(evidence.get((key, old[key][1]), {})):
                decisions["degraded_retained"].append(key)
        else:
            decisions["unproven_skipped"].append(key)
    for key, entry in old.items():
        if key in seen:
            continue
        check = evidence.get((key, entry[1]), {})
        if passes(check):
            result.append(entry)  # Never silently lose a healthy prior channel.
        elif (check.get("successes") == 0 and not check.get("audit_error")
              and len(check.get("details", [])) >= 3 and durably_quarantined(key, entry[1])):
            decisions["quarantined"].append(key)
        else:
            result.append(entry)
            decisions["degraded_retained"].append(key)
    if not result:
        raise ValueError("refusing empty release")
    for info, url in result:
        key = identity(info)
        check = evidence.get((key, url), {})
        if passes(check) and not assess(dict(check)).get("quality_passed"):
            decisions["quality_degraded_retained"].append(key)
    report["promotion_decisions"] = decisions
    return result


def promote(release: str, report_path: Path) -> int:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?", release):
        raise ValueError("release must be YYYY-MM-DD or YYYY-MM-DD-suffix")
    candidate = CANDIDATE.read_text()
    validate(candidate)
    report = json.loads(report_path.read_text())
    accepted = verified_entries(report)
    record_health(report)
    # Re-evaluate now that this distinct observed audit is in durable history.
    accepted = verified_entries(report)
    count = len(accepted)
    releases = ROOT / "releases"
    releases.mkdir(exist_ok=True)
    # The status service needs one stable, machine-readable pointer to the
    # newest real every-channel playback audit. Keep it current even when the
    # playlist itself is unchanged, so a green workflow is never mistaken for
    # proof that channels played.
    (releases / "latest-client-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("RELEASE_DECISIONS\t" + json.dumps(report["promotion_decisions"]))
    if accepted == entries(CLIENT_ALIASES[1]):
        print("UNCHANGED\tClient identities, order and URLs already match tested release")
        return count
    lines = ['#EXTM3U url-tvg="https://adamshl-oss.github.io/iptv-curated/epg.xml.gz" playlist-name="CHAINES TV"',
             f"# Release: {release}; per-channel playback evidence in release audit."]
    for info, url in accepted:
        lines.extend((info, url))
    body = "\n".join(lines) + "\n"
    if (releases / f"iptvx-{release}.m3u").exists():
        raise ValueError("release ID already exists; immutable releases cannot be overwritten")
    (releases / f"iptvx-{release}.m3u").write_text(body)
    (releases / f"iptvx-{release}-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for alias in CLIENT_ALIASES:
        alias.write_text(body)
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert_player_environment()
    print(f"PROCESSED\t{promote(args.release, args.report)} channels; see per-channel release decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
