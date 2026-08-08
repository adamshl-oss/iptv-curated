#!/usr/bin/env python3
"""Measure whether a public HLS route stays smooth for a sustained interval."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = ROOT / "scripts" / "stream_health_policy.json"
APPLE_TV_USER_AGENT = (
    "AppleCoreMedia/1.0.0.21A329 (AppleTV; U; CPU OS 17_0 like Mac OS X)"
)
NETWORK_ERROR_PATTERN = re.compile(
    r"HTTP error|Server returned|Service Unavailable|Forbidden|Not Found|"
    r"Failed to reload playlist|Opening .* failed|Connection timed out|"
    r"Connection reset|I/O error|TLS|Unable to open resource",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SustainedResult:
    passed: bool
    reason: str
    media_seconds: float
    wall_seconds: float
    wall_lag_seconds: float
    freeze_events: int
    total_freeze_seconds: float
    longest_freeze_seconds: float
    network_errors: int
    returncode: int

    def summary(self) -> str:
        return (
            f"{self.reason}; media={self.media_seconds:.1f}s; "
            f"wall={self.wall_seconds:.1f}s; lag={self.wall_lag_seconds:.1f}s; "
            f"freezes={self.freeze_events}/{self.total_freeze_seconds:.1f}s/"
            f"max{self.longest_freeze_seconds:.1f}s; errors={self.network_errors}"
        )


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    document = json.loads(path.read_text())
    policy = document.get("sustained_playback")
    if not isinstance(policy, dict):
        raise ValueError("sustained_playback policy is missing")
    return policy


def _progress_media_seconds(stdout: str) -> float:
    # ffmpeg historically labels microseconds as both out_time_us and
    # out_time_ms. Prefer out_time=HH:MM:SS when available, then either integer.
    clock_values = re.findall(r"^out_time=(\d+):(\d+):(\d+(?:\.\d+)?)$", stdout, re.M)
    if clock_values:
        hours, minutes, seconds = clock_values[-1]
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raw_values = [
        int(value)
        for value in re.findall(r"^out_time_(?:us|ms)=(\d+)$", stdout, re.M)
    ]
    return max(raw_values, default=0) / 1_000_000


def _freeze_durations(stderr: str, media_seconds: float) -> tuple[int, list[float]]:
    starts = [
        float(value)
        for value in re.findall(r"freeze_start:\s*([0-9.]+)", stderr)
    ]
    durations = [
        float(value)
        for value in re.findall(r"freeze_duration:\s*([0-9.]+)", stderr)
    ]
    if len(starts) > len(durations) and starts:
        durations.append(max(0.0, media_seconds - starts[-1]))
    return len(starts), durations


def evaluate(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    wall_seconds: float,
    policy: dict[str, Any],
) -> SustainedResult:
    duration = float(policy["duration_seconds"])
    minimum_media = duration * float(policy["minimum_media_ratio"])
    media = _progress_media_seconds(stdout)
    lag = max(0.0, wall_seconds - media)
    freeze_events, freeze_durations = _freeze_durations(stderr, media)
    total_freeze = sum(freeze_durations)
    longest_freeze = max(freeze_durations, default=0.0)
    network_errors = sum(
        1 for line in stderr.splitlines() if NETWORK_ERROR_PATTERN.search(line)
    )

    failures: list[str] = []
    if returncode != 0:
        diagnostic = next(
            (
                line.strip()
                for line in reversed(stderr.splitlines())
                if line.strip()
                and re.search(r"error|failed|invalid|not found|unable", line, re.I)
            ),
            "",
        )
        diagnostic = re.sub(r"[|\r\n]+", ":", diagnostic)[:100]
        failures.append(
            f"ffmpeg_rc{returncode}{':' + diagnostic if diagnostic else ''}"
        )
    if media < minimum_media:
        failures.append(f"short_media_{media:.1f}s")
    if lag > float(policy["maximum_wall_lag_seconds"]):
        failures.append(f"buffering_{lag:.1f}s")
    if freeze_events > int(policy["maximum_freeze_events"]):
        failures.append(f"freeze_events_{freeze_events}")
    if longest_freeze > float(policy["maximum_single_freeze_seconds"]):
        failures.append(f"long_freeze_{longest_freeze:.1f}s")
    if total_freeze > float(policy["maximum_total_freeze_seconds"]):
        failures.append(f"total_freeze_{total_freeze:.1f}s")
    if network_errors > int(policy["maximum_network_errors"]):
        failures.append(f"network_errors_{network_errors}")

    return SustainedResult(
        passed=not failures,
        reason="sustained_ok" if not failures else ",".join(failures),
        media_seconds=media,
        wall_seconds=wall_seconds,
        wall_lag_seconds=lag,
        freeze_events=freeze_events,
        total_freeze_seconds=total_freeze,
        longest_freeze_seconds=longest_freeze,
        network_errors=network_errors,
        returncode=returncode,
    )


def command(url: str, user_agent: str, policy: dict[str, Any]) -> list[str]:
    freeze_seconds = float(policy["freeze_detection_seconds"])
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "info",
        "-user_agent",
        user_agent,
        "-rw_timeout",
        "15000000",
        "-re",
        "-live_start_index",
        "-1",
        "-i",
        url,
        "-t",
        str(int(policy["duration_seconds"])),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        f"freezedetect=n=-50dB:d={freeze_seconds:g}",
        "-f",
        "null",
        "-",
        "-progress",
        "pipe:1",
    ]


def run(
    url: str,
    user_agent: str,
    policy: dict[str, Any],
    *,
    runner: Any = subprocess.run,
) -> SustainedResult:
    timeout = int(policy["duration_seconds"]) + int(policy["process_grace_seconds"])
    started = time.monotonic()
    try:
        completed = runner(
            command(url, user_agent, policy),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        wall = time.monotonic() - started
        return evaluate(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            wall_seconds=wall,
            policy=policy,
        )
    except subprocess.TimeoutExpired as error:
        wall = time.monotonic() - started
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or ""
        return evaluate(
            returncode=124,
            stdout=stdout,
            stderr=stderr,
            wall_seconds=wall,
            policy=policy,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--user-agent", default=APPLE_TV_USER_AGENT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run(args.url, args.user_agent, load_policy(args.policy))
    status = "PASS" if result.passed else "FAIL"
    print(f"{status}|{args.url}|{result.summary()}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
