#!/usr/bin/env python3
"""Persistent research memory for the channel discovery controller.

The live discovery workflow wakes frequently, but expensive research must not
repeat at that frequency.  This module turns each target/source-family pair
into a durable search task with an explicit cooldown and records candidate
fingerprints so an unchanged failed URL is not decoded again on every run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def add_hours(value: str, hours: int) -> str:
    return (
        parse_time(value) + timedelta(hours=hours)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def target_key(country: str, target_name: str) -> str:
    return f"{country}::{target_name}"


def family_specs(
    policy: dict[str, Any],
    country: str,
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return every distinct research path available for one exact target."""

    families: list[dict[str, Any]] = []
    official_url = str(target.get("official_url", ""))
    if official_url.startswith("https://"):
        families.extend(
            [
                {"key": "official:page", "kind": "official", "mode": "page"},
                {
                    "key": "official:assets",
                    "kind": "official",
                    "mode": "assets",
                },
                {
                    "key": "official:deep_assets",
                    "kind": "official",
                    "mode": "deep_assets",
                },
            ]
        )

    if str(target.get("tvg_id", "")):
        families.extend(
            [
                {"key": "github:tvg_id", "kind": "github", "mode": "tvg_id"},
                {
                    "key": "github:tvg_id_hls",
                    "kind": "github",
                    "mode": "tvg_id_hls",
                },
                {
                    "key": "github:exact_name_hls",
                    "kind": "github",
                    "mode": "exact_name_hls",
                },
                {
                    "key": "github:exact_name_live",
                    "kind": "github",
                    "mode": "exact_name_live",
                },
                {
                    "key": "github:country_name_hls",
                    "kind": "github",
                    "mode": "country_name_hls",
                },
                {
                    "key": "github:official_host",
                    "kind": "github",
                    "mode": "official_host",
                },
            ]
        )
        if target.get("aliases"):
            families.append(
                {
                    "key": "github:alias_hls",
                    "kind": "github",
                    "mode": "alias_hls",
                }
            )
        playlist_name = str(target.get("playlist_name", ""))
        if playlist_name and playlist_name != str(target.get("name", "")):
            families.append(
                {
                    "key": "github:playlist_name_hls",
                    "kind": "github",
                    "mode": "playlist_name_hls",
                }
            )
        for repository in policy.get("trusted_github_repositories", []):
            repository = str(repository)
            safe_key = repository.replace("/", "~")
            families.extend(
                [
                    {
                        "key": f"github-repo:{safe_key}:tvg_id",
                        "kind": "github",
                        "mode": "tvg_id",
                        "repository": repository,
                    },
                    {
                        "key": f"github-repo:{safe_key}:exact_name_hls",
                        "kind": "github",
                        "mode": "exact_name_hls",
                        "repository": repository,
                    },
                ]
            )

    for catalog in policy.get("catalogs", []):
        catalog_country = str(catalog.get("country", ""))
        if catalog_country not in {country, "all"}:
            continue
        families.append(
            {
                "key": f"catalog:{catalog['name']}",
                "kind": "catalog",
                "mode": str(catalog["name"]),
                "catalog": catalog,
            }
        )
    return families


def cooldown_hours(policy: dict[str, Any], family: dict[str, Any]) -> int:
    settings = policy.get("research_memory", {})
    cooldowns = settings.get("family_cooldown_hours", {})
    key = str(family["key"])
    if key in cooldowns:
        return int(cooldowns[key])
    return int(cooldowns.get(str(family["kind"]), 168))


def _legacy_family(key: str, patterns: Iterable[str]) -> bool:
    return any(key == pattern or (pattern.endswith("*") and key.startswith(pattern[:-1])) for pattern in patterns)


def new_history(
    policy: dict[str, Any],
    registries: dict[str, dict[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    """Create memory and seed paths already exercised by the legacy loop."""

    now = now or utc_now()
    settings = policy.get("research_memory", {})
    baseline_at = str(settings.get("legacy_baseline_at") or now)
    legacy_patterns = settings.get(
        "legacy_families",
        ["official:page", "official:assets", "github:tvg_id", "catalog:*"],
    )
    history: dict[str, Any] = {
        "version": VERSION,
        "created_at": now,
        "updated_at": now,
        "run_count": 0,
        "targets": {},
        "runs": [],
    }
    for country, registry in registries.items():
        for target in registry.get("channels", []):
            key = target_key(country, str(target["name"]))
            target_state = {"families": {}, "candidates": {}}
            for family in family_specs(policy, country, target):
                if not _legacy_family(str(family["key"]), legacy_patterns):
                    continue
                target_state["families"][family["key"]] = {
                    "attempts": 1,
                    "last_attempted_at": baseline_at,
                    "next_eligible_at": add_hours(
                        baseline_at, cooldown_hours(policy, family)
                    ),
                    "outcome": "legacy_scan_completed",
                    "candidates_found": None,
                    "new_candidates": None,
                    "qualified": False,
                }
            history["targets"][key] = target_state
    return history


def load_history(
    path: Path,
    policy: dict[str, Any],
    registries: dict[str, dict[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    if not path.exists():
        return new_history(policy, registries, now)
    history = json.loads(path.read_text())
    if history.get("version") != VERSION:
        raise ValueError(
            f"unsupported discovery-memory version {history.get('version')!r}"
        )
    history.setdefault("targets", {})
    history.setdefault("runs", [])
    history.setdefault("run_count", 0)
    return history


def save_history(path: Path, history: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")


def _rotated(families: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    if not families:
        return families
    offset = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % len(families)
    return families[offset:] + families[:offset]


def plan_searches(
    history: dict[str, Any],
    policy: dict[str, Any],
    targets: dict[str, list[dict[str, Any]]],
    now: str | None = None,
    *,
    wide: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pick never-tried paths first, then only paths whose cooldown expired."""

    now = now or utc_now()
    now_dt = parse_time(now)
    settings = policy.get("research_memory", {})
    wide_settings = policy.get("wide_sweep", {})
    per_target = int(
        wide_settings.get("families_per_target", 4)
        if wide
        else settings.get("families_per_target_per_run", 1)
    )
    available: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for country, country_targets in targets.items():
        for target in country_targets:
            name = str(target["name"])
            key = target_key(country, name)
            state = history["targets"].setdefault(
                key, {"families": {}, "candidates": {}}
            )
            families = _rotated(family_specs(policy, country, target), key)
            due: list[dict[str, Any]] = []
            next_times: list[str] = []
            if wide:
                # A wide sweep ignores cooldowns but still advances through the
                # frontier instead of repeating the same first families on
                # every manual or scheduled sweep.
                families.sort(
                    key=lambda family: str(
                        state["families"]
                        .get(family["key"], {})
                        .get("last_attempted_at", "1970-01-01T00:00:00Z")
                    )
                )
            for family in families:
                attempt = state["families"].get(family["key"])
                if wide:
                    due.append(family)
                    continue
                if not attempt:
                    due.append(family)
                    continue
                eligible_at = str(attempt.get("next_eligible_at", ""))
                if not eligible_at or parse_time(eligible_at) <= now_dt:
                    due.append(family)
                else:
                    next_times.append(eligible_at)
            for family in due[:per_target]:
                available.append(
                    {
                        "country": country,
                        "target": name,
                        "target_data": target,
                        "family": family,
                        "last_task_at": state.get("last_task_at"),
                    }
                )
            if not due:
                deferred.append(
                    {
                        "country": country,
                        "target": name,
                        "next_eligible_at": min(next_times) if next_times else None,
                    }
                )
    # Spread work fairly: a channel that was not researched recently goes
    # before a channel that received a task on the preceding wake.
    available.sort(
        key=lambda task: (
            str(task.get("last_task_at") or "1970-01-01T00:00:00Z"),
            hashlib.sha256(
                target_key(str(task["country"]), str(task["target"])).encode()
            ).hexdigest(),
        )
    )
    limit = int(
        wide_settings.get("maximum_tasks", 60)
        if wide
        else settings.get("maximum_tasks_per_run", 4)
    )
    planned = available[:limit]
    for task in available[limit:]:
        deferred.append(
            {
                "country": task["country"],
                "target": task["target"],
                "next_eligible_at": now,
                "reason": "run_budget",
            }
        )
    return planned, deferred


def candidate_fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def redact_url(url: str) -> str:
    """Keep useful provenance without persisting signed query parameters."""

    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def candidate_is_due(
    history: dict[str, Any],
    country: str,
    target_name: str,
    url: str,
    now: str | None = None,
) -> tuple[bool, str]:
    now = now or utc_now()
    state = history.get("targets", {}).get(target_key(country, target_name), {})
    candidate = state.get("candidates", {}).get(candidate_fingerprint(url))
    if not candidate:
        return True, "new candidate"
    eligible_at = str(candidate.get("next_eligible_at", ""))
    if not eligible_at or parse_time(eligible_at) <= parse_time(now):
        return True, "candidate cooldown expired"
    return False, f"candidate cooling down until {eligible_at}"


def record_task(
    history: dict[str, Any],
    policy: dict[str, Any],
    task: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    qualified: bool,
    now: str,
) -> dict[str, Any]:
    key = target_key(str(task["country"]), str(task["target"]))
    state = history["targets"].setdefault(
        key, {"families": {}, "candidates": {}}
    )
    family = task["family"]
    family_state = state["families"].get(family["key"], {})
    known = set(state["candidates"])
    fingerprints = [candidate_fingerprint(str(item["url"])) for item in candidates]
    new_count = sum(fingerprint not in known for fingerprint in fingerprints)
    family_state.update(
        {
            "attempts": int(family_state.get("attempts", 0)) + 1,
            "last_attempted_at": now,
            "next_eligible_at": add_hours(
                now, cooldown_hours(policy, family)
            ),
            "outcome": (
                "qualified" if qualified else "candidates_found" if candidates else "none"
            ),
            "candidates_found": len(candidates),
            "new_candidates": new_count,
            "qualified": qualified,
        }
    )
    state["families"][family["key"]] = family_state
    state["last_task_at"] = now

    candidate_cooldown = int(
        policy.get("research_memory", {}).get("candidate_retry_cooldown_hours", 168)
    )
    for item, fingerprint in zip(candidates, fingerprints):
        candidate_state = state["candidates"].get(fingerprint, {})
        outcome = str(item.get("outcome", "discovered"))
        candidate_state.update(
            {
                "first_seen_at": candidate_state.get("first_seen_at", now),
                "last_seen_at": now,
                "next_eligible_at": (
                    now
                    if outcome == "not_evaluated_limit"
                    else add_hours(now, candidate_cooldown)
                ),
                "url": redact_url(str(item["url"])),
                "source": item.get("source"),
                "last_outcome": outcome,
            }
        )
        state["candidates"][fingerprint] = candidate_state
    return {
        "country": task["country"],
        "target": task["target"],
        "family": family["key"],
        "candidates_found": len(candidates),
        "new_candidates": new_count,
        "qualified": qualified,
        "next_eligible_at": family_state["next_eligible_at"],
    }


def finish_run(
    history: dict[str, Any],
    policy: dict[str, Any],
    now: str,
    task_summaries: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
) -> None:
    history["updated_at"] = now
    history["run_count"] = int(history.get("run_count", 0)) + 1
    history.setdefault("runs", []).append(
        {
            "at": now,
            "tasks": task_summaries,
            "deferred_targets": deferred,
        }
    )
    keep = int(policy.get("research_memory", {}).get("max_run_history", 200))
    history["runs"] = history["runs"][-keep:]
