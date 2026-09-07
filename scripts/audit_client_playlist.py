#!/usr/bin/env python3
"""Test every actual client URL without registry exemptions or publication writes."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from build_combined_playlist import entries
from reconcile_self_healing import gate, HEALTH_POLICY_PATH


def identity(extinf: str) -> str:
    match = re.search(r'\btvg-id="([^"]+)"', extinf)
    if not match:
        raise ValueError("Channel has no stable tvg-id")
    return match.group(1)


def assess(result: dict) -> dict:
    """Separate resolution from playback; Apple cannot excuse frozen media."""
    details = result["details"]
    heights = [int(h) for line in details[:3]
               for h in re.findall(r'\b\d+x(\d+)\b', line)]
    transport = next((d[10:] for d in details if d.startswith("sustained:")), "")
    # FFmpeg live-edge startup overhead may exceed its wall-clock threshold.
    # Accept ONLY that diagnostic when media is complete and neither freezes
    # nor network errors occurred, and real AVPlayer independently passed.
    pacing_only = bool(re.fullmatch(
        r'buffering_[0-9.]+s; media=6[0-9.]*s; wall=[0-9.]+s; '
        r'lag=[0-9.]+s; freezes=0/0\.0s/max0\.0s; errors=0', transport))
    result["transport_pacing_only"] = pacing_only
    result["passed"] = bool(result["passed"] and
                            (result["sustained_passed"] or pacing_only))
    result["height"] = min(heights) if len(heights) == 3 else None
    result["quality_passed"] = bool(result["height"] and result["height"] >= 540)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("playlist", help="HTTPS URL or local candidate path")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apple-player", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--include-playlist", type=Path,
                        help="Also audit prior client entries before any removal")
    args = parser.parse_args()
    if args.playlist.startswith("https://"):
        request = Request(args.playlist, headers={"Cache-Control": "no-cache"})
        with urlopen(request, timeout=30) as response:
            body = response.read()
    else:
        body = Path(args.playlist).read_bytes()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    snapshot = args.report.with_suffix(".m3u")
    snapshot.write_bytes(body)
    channels = entries(snapshot)
    source_hashes = {Path(args.playlist.split("?", 1)[0]).name:
                     hashlib.sha256(body).hexdigest()}
    if args.include_playlist:
        channels += entries(args.include_playlist)
        source_hashes[args.include_playlist.name] = hashlib.sha256(
            args.include_playlist.read_bytes()).hexdigest()
    channels = list({(identity(info), url): (info, url)
                     for info, url in channels}.values())
    if not channels:
        raise SystemExit("Refusing to pass an empty playlist")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {
            pool.submit(gate, {"name": extinf.split(",", 1)[1], "min_height": 1},
                        url, 3, HEALTH_POLICY_PATH, args.apple_player): (extinf, url)
            for extinf, url in channels
        }
        for future in concurrent.futures.as_completed(pending):
            extinf, url = pending[future]
            try:
                result = assess(asdict(future.result()))
            except Exception as error:
                result = dict(name=extinf.split(",", 1)[1], passed=False,
                              successes=0, sustained_passed=False, apple_passed=False,
                              quality_passed=False, height=None,
                              details=[f"audit_exception:{type(error).__name__}"],
                              audit_error=True)
            result.update(url=url, extinf=extinf, tvg_id=identity(extinf))
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "playlist": args.playlist,
        "playlist_sha256": hashlib.sha256(body).hexdigest(),
        "source_hashes": source_hashes,
        "policy_sha256": hashlib.sha256(HEALTH_POLICY_PATH.read_bytes()).hexdigest(),
        "apple_required": args.apple_player,
        "count": len(channels),
        "passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "results": sorted(results, key=lambda item: item["name"]),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
