#!/usr/bin/env python3
"""Discover and qualify replacement streams for the curated IPTV playlists.

The discovery job deliberately separates finding from publishing:

* official broadcaster pages, maintained public catalogs, and GitHub code are
  searched for exact target identities;
* unsafe, private-IP, DRM, VOD, low-quality, or expiring direct URLs cannot be
  promoted;
* a candidate must come from an official page or an allowlisted maintained
  resolver, match the exact tvg-id, and pass three real moving-media gates;
* a newly discovered source enters the existing two-gate recovery controller.

This gives the cloud controller new options without allowing an arbitrary web
result to silently enter the Apple TV playlist.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import hashlib
import html
import ipaddress
import json
import os
import re
import signal
import subprocess
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from coverage_status import build_status, print_status, write_status

try:
    from discovery_memory import (
        candidate_is_due,
        finish_run,
        load_history,
        plan_searches,
        record_task,
        save_history,
    )
except ModuleNotFoundError:  # Imported as scripts.discover_channel_sources in tests.
    from scripts.discovery_memory import (
        candidate_is_due,
        finish_run,
        load_history,
        plan_searches,
        record_task,
        save_history,
    )


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "scripts" / "source_discovery.json"
CATALOG_PATH = ROOT / "scripts" / "self_healing_catalog.json"
TEST = ROOT / "scripts" / "test_stream.sh"
REPORT_DEFAULT = ROOT / "source-discovery-report.json"
HISTORY_DEFAULT = ROOT / "source-discovery-history.json"
REGISTRIES = {
    "france": ROOT / "scripts" / "french_top20_target.json",
    "algeria": ROOT / "scripts" / "algerian_top20_target.json",
}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_4) "
    "AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15"
)
HTTP_TIMEOUT = 20
PLAYBACK_TIMEOUT = 105
URL_RE = re.compile(
    r"https?:(?:\\/\\/|//)[^\"'<>\\s]+?\.m3u8(?:\?[^\"'<>\\s]+)?",
    re.IGNORECASE,
)
SCRIPT_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
ATTR_RE = re.compile(r"([\w-]+)=\"([^\"]*)\"")
NOISE_RE = re.compile(
    r"\b(?:hd|sd|uhd|fhd|4k|1080p?|720p?|576p?|480p?|360p?|240p?|"
    r"live|direct|channel|chaine|chaîne|official|officiel)\b",
    re.IGNORECASE,
)
EXPIRY_KEYS = {"expire", "expires", "expiry", "exp", "e"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def normalize(value: str) -> str:
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(character)
    ).lower()
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"^\s*\d+\s*[.)-]\s*", "", value)
    value = re.sub(r"[^\w\s+]", " ", value)
    value = NOISE_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_text(url: str, token: str = "", timeout: int = HTTP_TIMEOUT) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json,application/vnd.apple.mpegurl,*/*",
    }
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(2_500_000)
    return payload.decode("utf-8", errors="ignore")


def decode_embedded_url(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\\u0026", "&").replace("\\/", "/")
    return value.rstrip("\\,;)")


def safe_stream_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "malformed URL"
    if parsed.scheme != "https":
        return False, "HTTPS is required for Apple clients"
    if parsed.username or parsed.password:
        return False, "embedded credentials"
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "localhost.localdomain"}:
        return False, "missing or local host"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        return False, "raw IP restream"
    if any(part in url.lower() for part in ("acestream://", "magnet:", ".mpd")):
        return False, "not directly playable HLS"
    if "googlevideo.com" in host:
        return False, "short-lived YouTube media URL needs a resolver"
    if ".m3u8" not in parsed.path.lower() and not parsed.path.lower().endswith("/live"):
        return False, "not an HLS manifest URL"
    return True, "safe URL shape"


def stable_stream_url(url: str, minimum_lifetime: int = 86_400) -> tuple[bool, str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    now = int(time.time())
    for key, values in query.items():
        if key.lower() not in EXPIRY_KEYS:
            continue
        for value in values:
            try:
                expiry = int(value)
            except ValueError:
                continue
            if expiry < 10_000_000_000 and expiry < now + minimum_lifetime:
                return False, "direct URL expires within 24 hours"
    match = re.search(r"/expire/(\d+)/", url)
    if match and int(match.group(1)) < now + minimum_lifetime:
        return False, "direct URL expires within 24 hours"
    # Several broadcaster CDNs put a JWT in the path rather than the query.
    # Decode only the unsigned payload metadata; this is not authentication.
    for part in parsed.path.split("/"):
        pieces = part.split(".")
        if len(pieces) != 3:
            continue
        try:
            padding = "=" * (-len(pieces[1]) % 4)
            payload = json.loads(
                base64.urlsafe_b64decode(pieces[1] + padding).decode("utf-8")
            )
        except Exception:
            continue
        if payload.get("cip"):
            return False, "direct CDN token is bound to the resolver IP"
        try:
            expiry = int(payload.get("exp", 0))
        except (TypeError, ValueError):
            expiry = 0
        if expiry and expiry < now + minimum_lifetime:
            return False, "direct CDN token expires within 24 hours"
    return True, "stable URL"


@dataclass(frozen=True)
class Candidate:
    country: str
    target: str
    target_tvg_id: str
    candidate_name: str
    candidate_tvg_id: str
    url: str
    source: str
    trusted: bool
    match_basis: str


def parse_m3u(text: str, country: str, source: str, trusted: bool) -> list[Candidate]:
    # Target assignment happens later; this parser stores the catalog identity
    # temporarily in the target fields to keep Candidate serialization simple.
    entries: list[Candidate] = []
    current_name = ""
    current_tvg_id = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            attributes = dict(ATTR_RE.findall(line))
            current_tvg_id = attributes.get("tvg-id", "").strip()
            current_name = line.rsplit(",", 1)[-1].strip()
            continue
        if line.startswith(("http://", "https://")) and current_name:
            entries.append(
                Candidate(
                    country=country,
                    target="",
                    target_tvg_id="",
                    candidate_name=current_name,
                    candidate_tvg_id=current_tvg_id,
                    url=decode_embedded_url(line),
                    source=source,
                    trusted=trusted,
                    match_basis="",
                )
            )
            current_name = ""
            current_tvg_id = ""
    return entries


def target_aliases(target: dict[str, Any]) -> set[str]:
    aliases = {normalize(str(target["name"]))}
    if target.get("playlist_name"):
        aliases.add(normalize(str(target["playlist_name"])))
    for alias in target.get("aliases", []) or []:
        aliases.add(normalize(str(alias)))
    return {alias for alias in aliases if alias}


def match_candidate(
    country: str,
    target: dict[str, Any],
    item: Candidate,
) -> Candidate | None:
    target_tvg_id = str(target.get("tvg_id", ""))
    if target_tvg_id and item.candidate_tvg_id == target_tvg_id:
        basis = "exact_tvg_id"
    elif normalize(item.candidate_name) in target_aliases(target):
        basis = "exact_name"
    else:
        return None
    return Candidate(
        country=country,
        target=str(target["name"]),
        target_tvg_id=target_tvg_id,
        candidate_name=item.candidate_name,
        candidate_tvg_id=item.candidate_tvg_id,
        url=item.url,
        source=item.source,
        trusted=item.trusted,
        match_basis=basis,
    )


def official_page_candidates(
    country: str,
    target: dict[str, Any],
    asset_limit: int,
    mode: str = "all",
) -> list[Candidate]:
    page_url = str(target.get("official_url", ""))
    if not page_url.startswith("https://"):
        return []
    try:
        page = fetch_text(page_url)
    except Exception as error:
        print(f"DISCOVERY\t{country}\t{target['name']}\tofficial page unavailable: {error}")
        return []

    documents = [(page_url, page)] if mode in {"all", "page"} else []
    assets: list[str] = []
    if mode in {"all", "assets", "deep_assets"}:
        for source in SCRIPT_RE.findall(page):
            asset = urljoin(page_url, html.unescape(source))
            if asset.startswith("https://") and asset not in assets:
                assets.append(asset)
            if len(assets) >= asset_limit:
                break
        for asset in assets:
            try:
                documents.append((asset, fetch_text(asset, timeout=15)))
            except Exception:
                continue

    found: list[Candidate] = []
    seen: set[str] = set()
    for document_url, body in documents:
        for raw_url in URL_RE.findall(body):
            url = decode_embedded_url(raw_url)
            if url in seen:
                continue
            seen.add(url)
            found.append(
                Candidate(
                    country=country,
                    target=str(target["name"]),
                    target_tvg_id=str(target.get("tvg_id", "")),
                    candidate_name=str(target["name"]),
                    candidate_tvg_id=str(target.get("tvg_id", "")),
                    url=url,
                    source=f"official-page:{urlparse(document_url).hostname}",
                    trusted=True,
                    match_basis="official_page",
                )
            )
    return found


def github_candidates(
    country: str,
    target: dict[str, Any],
    token: str,
    trusted_repositories: set[str],
    result_limit: int,
    query_mode: str = "tvg_id",
    repository: str = "",
) -> list[Candidate]:
    tvg_id = str(target.get("tvg_id", ""))
    if not token or not tvg_id:
        return []
    target_name = str(target.get("name", ""))
    official_host = urlparse(str(target.get("official_url", ""))).hostname or ""
    aliases = [
        str(alias)
        for alias in target.get("aliases", []) or []
        if str(alias).strip()
    ]
    if query_mode == "tvg_id":
        query_text = f'"{tvg_id}"'
    elif query_mode == "tvg_id_hls":
        query_text = f'"{tvg_id}" m3u8'
    elif query_mode == "exact_name_hls":
        query_text = f'"{target_name}" m3u8'
    elif query_mode == "exact_name_live":
        query_text = f'"{target_name}" live'
    elif query_mode == "country_name_hls":
        country_name = "France" if country == "france" else "Algeria"
        query_text = f'"{target_name}" "{country_name}" m3u8'
    elif query_mode == "official_host" and official_host:
        query_text = f'"{tvg_id}" "{official_host}"'
    elif query_mode == "alias_hls" and aliases:
        query_text = f'"{aliases[0]}" m3u8'
    elif query_mode == "playlist_name_hls" and target.get("playlist_name"):
        query_text = f'"{target["playlist_name"]}" m3u8'
    else:
        return []
    if repository:
        query_text += f" repo:{repository}"
    query = quote_plus(query_text)
    search_url = f"https://api.github.com/search/code?q={query}&per_page={result_limit}"
    payload: dict[str, Any] | None = None
    for attempt in range(1, 5):
        try:
            payload = json.loads(fetch_text(search_url, token=token))
            break
        except HTTPError as error:
            if error.code not in (403, 429) or attempt == 4:
                print(
                    f"DISCOVERY\t{country}\t{target['name']}\t"
                    f"GitHub search unavailable after {attempt} attempt(s): {error}"
                )
                return []
            retry_after = int(error.headers.get("Retry-After", "0") or 0)
            reset_at = int(error.headers.get("X-RateLimit-Reset", "0") or 0)
            reset_wait = max(0, reset_at - int(time.time()) + 2)
            delay = max(10 * attempt, retry_after, reset_wait)
            delay = min(delay, 90)
            print(
                f"RETRY\t{country}\t{target['name']}\t"
                f"GitHub search rate-limited; waiting {delay}s"
            )
            time.sleep(delay)
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == 4:
                print(
                    f"DISCOVERY\t{country}\t{target['name']}\t"
                    f"GitHub search unavailable after {attempt} attempt(s): {error}"
                )
                return []
            time.sleep(5 * attempt)

    if payload is None:
        return []

    found: list[Candidate] = []
    for item in payload.get("items", [])[:result_limit]:
        repository = str(item.get("repository", {}).get("full_name", ""))
        api_url = str(item.get("url", ""))
        if not api_url:
            continue
        try:
            content_payload = json.loads(fetch_text(api_url, token=token))
            download_url = str(content_payload.get("download_url", ""))
            if not download_url:
                continue
            body = fetch_text(download_url)
        except Exception:
            continue
        parsed = parse_m3u(
            body,
            country,
            f"github:{repository}",
            repository in trusted_repositories,
        )
        for candidate in parsed:
            matched = match_candidate(country, target, candidate)
            if matched:
                found.append(matched)
    return found


def live_manifest(url: str) -> tuple[bool, str]:
    try:
        body = fetch_text(url, timeout=15)
    except Exception as error:
        return False, f"manifest fetch failed: {error}"
    if not body.lstrip().startswith("#EXTM3U"):
        return False, "not an HLS manifest"
    if "#EXT-X-ENDLIST" in body:
        return False, "VOD/event playlist has ended"
    if "#EXT-X-STREAM-INF" in body:
        lines = [line.strip() for line in body.splitlines()]
        variants = [
            urljoin(url, lines[index + 1])
            for index, line in enumerate(lines[:-1])
            if line.startswith("#EXT-X-STREAM-INF") and lines[index + 1]
        ]
        if variants:
            try:
                media = fetch_text(variants[-1], timeout=15)
            except Exception as error:
                return False, f"variant fetch failed: {error}"
            if "#EXT-X-ENDLIST" in media:
                return False, "VOD/event variant has ended"
            if "#EXT-X-MEDIA-SEQUENCE" not in media:
                return False, "variant is not identifiable as a live window"
    elif "#EXT-X-MEDIA-SEQUENCE" not in body:
        return False, "manifest is not identifiable as a live window"
    return True, "live HLS window"


def playback_gate(url: str, min_height: int, attempts: int) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    successes = 0
    for attempt in range(1, attempts + 1):
        completed: subprocess.CompletedProcess[str]
        process = subprocess.Popen(
            [str(TEST), url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=PLAYBACK_TIMEOUT)
            completed = subprocess.CompletedProcess(
                process.args,
                process.returncode,
                stdout,
                stderr,
            )
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            evidence.append(f"{attempt}:timeout")
            return False, evidence
        output = (completed.stdout or completed.stderr).strip()
        fields = output.split("|")
        if completed.returncode != 0 or not fields or fields[0] != "PASS":
            evidence.append(f"{attempt}:{fields[2] if len(fields) > 2 else output}")
            return False, evidence
        try:
            height = int(fields[4].split("x", 1)[1])
        except (IndexError, ValueError):
            evidence.append(f"{attempt}:unreadable resolution")
            return False, evidence
        if height < min_height:
            evidence.append(f"{attempt}:{height}p below {min_height}p")
            return False, evidence
        successes += 1
        evidence.append(f"{attempt}:{fields[3]} {fields[4]}, moving")
        if attempt < attempts:
            time.sleep(attempt)
    return successes == attempts, evidence


def candidate_priority(candidate: Candidate) -> tuple[int, int, str]:
    return (
        0 if candidate.trusted else 1,
        0 if candidate.match_basis in {"exact_tvg_id", "official_page"} else 1,
        candidate.source,
    )


def exact_channel_identity(candidate: Candidate) -> tuple[bool, str]:
    if candidate.match_basis == "official_page":
        url_compact = re.sub(r"[^a-z0-9]", "", unquote(candidate.url).lower())
        name_compact = re.sub(r"[^a-z0-9]", "", normalize(candidate.target))
        tvg_compact = re.sub(
            r"[^a-z0-9]",
            "",
            candidate.target_tvg_id.split(".", 1)[0].lower(),
        )
        slugs = {slug for slug in (name_compact, tvg_compact) if len(slug) >= 3}
        if slugs and any(slug in url_compact for slug in slugs):
            return True, "target-specific official page and channel slug"
        return False, "official page URL lacks a target-specific channel slug"
    if normalize(candidate.candidate_name) != normalize(candidate.target):
        return False, "candidate name is a variant or substitute"
    target_id = candidate.target_tvg_id.casefold()
    candidate_id = candidate.candidate_tvg_id.split("@", 1)[0].casefold()
    if not target_id or candidate_id != target_id:
        return False, "candidate tvg-id is not the exact target"
    return True, "exact name and tvg-id"


def deduplicate(candidates: Iterable[Candidate]) -> list[Candidate]:
    best: dict[str, Candidate] = {}
    for candidate in candidates:
        current = best.get(candidate.url)
        if current is None or candidate_priority(candidate) < candidate_priority(current):
            best[candidate.url] = candidate
    return sorted(best.values(), key=candidate_priority)


def apply_candidate(
    target: dict[str, Any],
    candidate: Candidate,
    evidence: list[str],
) -> None:
    old_status = target.get("status")
    old_reason = target.get("reason")
    healing = dict(target.get("auto_healing") or {})
    healing.update(
        {
            "enabled": True,
            "recovery_allowed": True,
            "failure_streak": 0,
            # The discovery gate is the first complete successful gate. The
            # normal controller must independently pass it once more.
            "success_streak": 1,
            "prior_status": healing.get("prior_status", old_status),
            "prior_reason": healing.get("prior_reason", old_reason),
            "candidate_discovered_at": utc_now(),
            "candidate_source": candidate.source,
            "candidate_evidence": "; ".join(evidence),
        }
    )
    target["stream_url"] = candidate.url
    target["auto_healing"] = healing
    target["status"] = "candidate_cloud_verification"
    target["reason"] = (
        f"Automatically discovered from {candidate.source}; exact identity and "
        "three moving-media gates passed. Awaiting the independent recovery gate."
    )


def should_search(target: dict[str, Any]) -> bool:
    if target.get("publish") is not True:
        return True
    healing = target.get("auto_healing") or {}
    return int(healing.get("failure_streak", 0)) > 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", choices=("all", "france", "algeria"), default="all")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--no-official-pages", action="store_true")
    parser.add_argument("--no-github-search", action="store_true")
    parser.add_argument(
        "--official-only",
        action="store_true",
        help="Use only broadcaster-owned web surfaces; skip catalogs and GitHub.",
    )
    parser.add_argument("--skip-playback", action="store_true")
    parser.add_argument("--attempts", type=int)
    parser.add_argument("--history", type=Path, default=HISTORY_DEFAULT)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--wide",
        action="store_true",
        help="Manually sweep multiple source families per target without research cooldowns.",
    )
    args = parser.parse_args()

    policy = json.loads(POLICY_PATH.read_text())
    attempts = args.attempts or int(policy["minimum_successful_playback_attempts"])
    wide_settings = policy.get("wide_sweep", {})
    candidate_limit = int(
        wide_settings.get("maximum_candidates_per_target", 10)
        if args.wide
        else policy["maximum_candidates_per_target"]
    )
    asset_limit = int(policy["official_page_asset_limit"])
    github_limit = int(
        wide_settings.get("github_search_result_limit", 10)
        if args.wide
        else policy["github_search_result_limit"]
    )
    trusted_repositories = set(policy["trusted_github_repositories"])
    token = os.environ.get("GITHUB_TOKEN", "")
    selected = list(REGISTRIES) if args.country == "all" else [args.country]

    registries = {
        country: json.loads(REGISTRIES[country].read_text()) for country in selected
    }
    targets = {
        country: [
            target
            for target in registry["channels"]
            if (
                registry.get("target_count") is None
                or int(target.get("rank", 10_000))
                <= int(registry["target_count"])
            )
            and should_search(target)
        ]
        for country, registry in registries.items()
    }

    run_at = utc_now()
    history = load_history(args.history, policy, registries, run_at)
    planned_tasks, deferred_targets = plan_searches(
        history, policy, targets, run_at, wide=args.wide
    )
    if args.no_official_pages:
        planned_tasks = [
            task for task in planned_tasks if task["family"]["kind"] != "official"
        ]
    if args.no_github_search or args.official_only:
        planned_tasks = [
            task for task in planned_tasks if task["family"]["kind"] != "github"
        ]
    if args.official_only:
        # A manually requested official audit deliberately covers every
        # unresolved in-scope target. It does not inherit the incremental
        # scheduler's eight-task budget or third-party research rotation.
        planned_tasks = [
            {
                "country": country,
                "target": str(target["name"]),
                "target_data": target,
                "family": {
                    "key": "official:deep_assets",
                    "kind": "official",
                    "mode": "deep_assets",
                },
                "last_task_at": None,
            }
            for country, country_targets in targets.items()
            for target in country_targets
            if str(target.get("official_url", "")).startswith("https://")
        ]

    if args.plan_only:
        plan_report = {
            "version": 2,
            "generated_at": run_at,
            "plan_only": True,
            "tasks": [
                {
                    "country": task["country"],
                    "target": task["target"],
                    "family": task["family"]["key"],
                }
                for task in planned_tasks
            ],
            "deferred": deferred_targets,
        }
        args.report.write_text(
            json.dumps(plan_report, ensure_ascii=False, indent=2) + "\n"
        )
        if planned_tasks:
            print(
                f"SEARCH_DUE\ttasks={len(planned_tasks)}; "
                f"families={','.join(sorted({task['family']['key'] for task in planned_tasks}))}"
            )
        else:
            eligible = [
                item["next_eligible_at"]
                for item in deferred_targets
                if item.get("next_eligible_at")
            ]
            print(
                "SEARCH_DEFERRED\tno research path is due; "
                f"next={min(eligible) if eligible else 'unavailable'}"
            )
        return 0

    catalog_items: dict[str, list[Candidate]] = {country: [] for country in selected}
    source_results: list[dict[str, Any]] = []
    selected_catalogs = {
        task["family"]["key"]
        for task in planned_tasks
        if task["family"]["kind"] == "catalog"
    }
    for spec in policy["catalogs"]:
        if f"catalog:{spec['name']}" not in selected_catalogs:
            continue
        countries = selected if spec["country"] == "all" else [spec["country"]]
        countries = [country for country in countries if country in selected]
        if not countries:
            continue
        try:
            body = fetch_text(str(spec["url"]))
            count = 0
            for country in countries:
                parsed = parse_m3u(
                    body,
                    country,
                    str(spec["name"]),
                    bool(spec.get("auto_recover")),
                )
                catalog_items[country].extend(parsed)
                count += len(parsed)
            source_results.append({"source": spec["name"], "status": "ok", "entries": count})
        except Exception as error:
            source_results.append({"source": spec["name"], "status": "error", "error": str(error)})

    official_items: dict[tuple[str, str, str], list[Candidate]] = {}
    if not args.no_official_pages:
        official_jobs = [
            task
            for task in planned_tasks
            if task["family"]["kind"] == "official"
        ]
        with futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {
                executor.submit(
                    official_page_candidates,
                    str(task["country"]),
                    task["target_data"],
                    (
                        int(policy.get("official_page_deep_asset_limit", 12))
                        if task["family"]["mode"] == "deep_assets"
                        else asset_limit
                    ),
                    str(task["family"]["mode"]),
                ): (
                    str(task["country"]),
                    str(task["target"]),
                    str(task["family"]["key"]),
                )
                for task in official_jobs
            }
            for future in futures.as_completed(future_map):
                key = future_map[future]
                try:
                    official_items[key] = future.result()
                except Exception as error:
                    print(f"DISCOVERY\t{key[0]}\t{key[1]}\tofficial crawl failed: {error}")
                    official_items[key] = []

    candidate_sets: dict[tuple[str, str, str], list[Candidate]] = {}
    for task in planned_tasks:
        country = str(task["country"])
        target = task["target_data"]
        family = task["family"]
        found: list[Candidate] = []
        if family["kind"] == "catalog":
            source_name = str(family["mode"])
            catalog_candidates = [
                item for item in catalog_items[country] if item.source == source_name
            ]
        else:
            catalog_candidates = []
        for item in catalog_candidates:
            matched = match_candidate(country, target, item)
            if matched:
                found.append(matched)
        found.extend(
            official_items.get(
                (country, str(target["name"]), str(family["key"])), []
            )
        )
        if family["kind"] == "github" and not args.no_github_search:
            found.extend(
                github_candidates(
                    country,
                    target,
                    token,
                    trusted_repositories,
                    github_limit,
                    str(family["mode"]),
                    str(family.get("repository", "")),
                )
            )
            # Keep well below GitHub's authenticated code-search burst limit.
            if token:
                time.sleep(6.5)
        candidate_sets[
            (country, str(target["name"]), str(family["key"]))
        ] = deduplicate(found)

    def evaluate_target(
        task: dict[str, Any],
    ) -> tuple[list[Candidate], list[dict[str, Any]], Candidate | None, list[str]]:
        country = str(task["country"])
        target = task["target_data"]
        candidates = candidate_sets[
            (country, str(target["name"]), str(task["family"]["key"]))
        ]
        evaluated: list[dict[str, Any]] = []
        selected_candidate: Candidate | None = None
        selected_evidence: list[str] = []
        current_url = str(target.get("stream_url", ""))
        for candidate in candidates[:candidate_limit]:
            record = asdict(candidate)
            safe, safe_reason = safe_stream_url(candidate.url)
            stable, stable_reason = stable_stream_url(candidate.url)
            exact, exact_reason = exact_channel_identity(candidate)
            eligible = candidate.trusted and exact and safe and stable
            record.update(
                {
                    "safe": safe,
                    "safe_reason": safe_reason,
                    "stable": stable,
                    "stable_reason": stable_reason,
                    "exact_identity": exact,
                    "exact_identity_reason": exact_reason,
                    "eligible_for_recovery": eligible,
                }
            )
            if not eligible:
                record["outcome"] = "rejected_policy"
                evaluated.append(record)
                continue
            if candidate.url == current_url:
                record["outcome"] = "current_stream"
                evaluated.append(record)
                continue
            if args.wide:
                candidate_due, due_reason = True, "manual wide sweep"
            else:
                candidate_due, due_reason = candidate_is_due(
                    history,
                    country,
                    str(target["name"]),
                    candidate.url,
                    run_at,
                )
            if not candidate_due:
                record["outcome"] = "candidate_cooldown"
                record["candidate_cooldown_reason"] = due_reason
                evaluated.append(record)
                continue
            if args.skip_playback:
                record["playback_skipped"] = True
                record["outcome"] = "playback_skipped"
                evaluated.append(record)
                continue
            live, live_reason = live_manifest(candidate.url)
            record["live_manifest"] = live
            record["live_reason"] = live_reason
            if not live:
                record["outcome"] = "not_live"
                evaluated.append(record)
                continue
            passed, evidence = playback_gate(
                candidate.url,
                int(target.get("min_height", 540)),
                attempts,
            )
            record["playback_passed"] = passed
            record["playback_evidence"] = evidence
            record["outcome"] = "qualified" if passed else "playback_failed"
            evaluated.append(record)
            if passed:
                selected_candidate = candidate
                selected_evidence = evidence
                break
        return candidates, evaluated, selected_candidate, selected_evidence

    jobs = planned_tasks
    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        evaluation_results = list(executor.map(evaluate_target, jobs))

    report_targets: list[dict[str, Any]] = []
    changed_countries: set[str] = set()
    qualified_count = 0
    task_summaries: list[dict[str, Any]] = []
    for task, result in zip(jobs, evaluation_results):
        country = str(task["country"])
        target = task["target_data"]
        candidates, evaluated, selected_candidate, selected_evidence = result
        if selected_candidate and args.apply:
            apply_candidate(target, selected_candidate, selected_evidence)
            changed_countries.add(country)
            qualified_count += 1
            print(
                f"QUALIFIED\t{country}\t{target['name']}\t"
                f"{selected_candidate.source}\t{selected_candidate.url}"
            )
        else:
            print(
                f"DISCOVERY\t{country}\t{target['name']}\t"
                f"family={task['family']['key']}; "
                f"{len(candidates)} candidate(s), no applied replacement"
            )
        outcomes = {
            str(record["url"]): str(record.get("outcome", "discovered"))
            for record in evaluated
        }
        history_candidates = []
        for candidate in candidates:
            item = asdict(candidate)
            item["outcome"] = outcomes.get(candidate.url, "not_evaluated_limit")
            history_candidates.append(item)
        task_summaries.append(
            record_task(
                history,
                policy,
                task,
                candidates=history_candidates,
                qualified=selected_candidate is not None,
                now=run_at,
            )
        )
        report_targets.append(
            {
                "country": country,
                "target": target["name"],
                "family": task["family"]["key"],
                "published": target.get("publish") is True,
                "candidates_found": len(candidates),
                "evaluated": evaluated,
                "qualified": asdict(selected_candidate) if selected_candidate else None,
            }
        )

    finish_run(history, policy, run_at, task_summaries, deferred_targets)
    save_history(args.history, history)

    if args.apply:
        for country in changed_countries:
            REGISTRIES[country].write_text(
                json.dumps(registries[country], ensure_ascii=False, indent=2) + "\n"
            )
        coverage = write_status()
    else:
        coverage = build_status()

    report = {
        "version": 2,
        "generated_at": run_at,
        "policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        "countries": selected,
        "targets_searched": len(report_targets),
        "research_memory": {
            "path": str(args.history),
            "run_count": history["run_count"],
            "tasks": task_summaries,
            "deferred_targets": deferred_targets,
        },
        "changed_countries": sorted(changed_countries),
        "qualified_count": qualified_count,
        "sources": source_results,
        "targets": report_targets,
        "coverage": coverage,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"OPERATIONAL\tdiscovery controller\ttargets={len(report_targets)}; "
        f"qualified={qualified_count} channel(s)"
    )
    print_status(coverage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
