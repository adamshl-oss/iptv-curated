#!/usr/bin/env python3
"""Validate recent playback evidence produced by the home Apple media stack."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def evaluate_home_authority(
    channel: dict[str, Any], now: datetime | None = None, root: Path | None = None
) -> tuple[bool, str] | None:
    if channel.get("health_authority") != "home_avplayer":
        return None
    wrapper = str(channel.get("health_authority_wrapper") or "")
    evidence_path_value = str(channel.get("health_authority_evidence") or "")
    authority_root = root or Path(__file__).resolve().parent.parent
    wrapper_path = authority_root / wrapper
    evidence_path = authority_root / evidence_path_value
    if not wrapper or not evidence_path_value or not wrapper_path.is_file():
        return False, "home Apple AVPlayer evidence has no bound wrapper digest"
    try:
        evidence_document = json.loads(evidence_path.read_text())
    except (OSError, ValueError):
        return False, "home Apple AVPlayer evidence sidecar is missing or malformed"
    expected_digest = str(evidence_document.get("wrapper_sha256") or "")
    actual_digest = hashlib.sha256(wrapper_path.read_bytes()).hexdigest()
    if actual_digest != expected_digest:
        return False, "home Apple AVPlayer evidence does not match this wrapper"
    if evidence_document.get("channel") != channel.get("name"):
        return False, "home Apple AVPlayer evidence names another channel"
    checked_at = str(evidence_document.get("checked_at") or "")
    maximum_age = int(channel.get("health_authority_max_age_seconds", 2100))
    try:
        observed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError
    except ValueError:
        return False, "home Apple AVPlayer evidence is missing or malformed"
    current = now or datetime.now(timezone.utc)
    age = int((current - observed).total_seconds())
    if age < -300:
        return False, "home Apple AVPlayer evidence is from the future"
    age = max(0, age)
    evidence = str(evidence_document.get("evidence") or "")
    metrics = re.search(
        r"^apple_ok; startup=(\d+(?:\.\d+)?)s; observed=(\d+(?:\.\d+)?)s; "
        r"advancing=(\d+(?:\.\d+)?)s/(\d+(?:\.\d+)?); waiting=(\d+(?:\.\d+)?)s; "
        r"stalls=(\d+)/(\d+(?:\.\d+)?)s/max(\d+(?:\.\d+)?)s; discontinuities=(\d+)$",
        evidence,
    )
    if not metrics:
        return False, "home Apple AVPlayer evidence metrics are malformed"
    observed_seconds = float(metrics.group(2))
    advancing_ratio = float(metrics.group(4))
    stall_events = int(metrics.group(6))
    if observed_seconds < 60 or advancing_ratio < 0.95 or stall_events != 0:
        return False, "home Apple AVPlayer evidence does not meet playback policy"
    if age > maximum_age:
        return False, f"home Apple AVPlayer evidence is stale ({age}s)"
    return True, f"home Apple AVPlayer evidence age={age}s; {evidence}"
