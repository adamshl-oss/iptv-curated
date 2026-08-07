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


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "scripts" / "source_discovery.json"
CATALOG_PATH = ROOT / "scripts" / "self_healing_catalog.json"
TEST = ROOT / "scripts" / "test_stream.sh"
REPORT_DEFAULT = ROOT / "source-discovery-report.json"
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
) -> list[Candidate]:
    page_url = str(target.get("official_url", ""))
    if not page_url.startswith("https://"):
        return []
    try:
        page = fetch_text(page_url)
    except Exception as error:
        print(f"DISCOVERY\t{country}\t{target['name']}\tofficial page unavailable: {error}")
        return []

    documents = [(page_url, page)]
    assets: list[str] = []
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
) -> list[Candidate]:
    tvg_id = str(target.get("tvg_id", ""))
    if not token or not tvg_id:
        return []
    query = quote_plus(f'"{tvg_id}"')
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
    parser.add_argument("--skip-playback", action="store_true")
    parser.add_argument("--attempts", type=int)
    args = parser.parse_args()

    policy = json.loads(POLICY_PATH.read_text())
    attempts = args.attempts or int(policy["minimum_successful_playback_attempts"])
    candidate_limit = int(policy["maximum_candidates_per_target"])
    asset_limit = int(policy["official_page_asset_limit"])
    github_limit = int(policy["github_search_result_limit"])
    trusted_repositories = set(policy["trusted_github_repositories"])
    token = os.environ.get("GITHUB_TOKEN", "")
    selected = list(REGISTRIES) if args.country == "all" else [args.country]

    registries = {
        country: json.loads(REGISTRIES[country].read_text()) for country in selected
    }
    targets = {
        country: [target for target in registry["channels"] if should_search(target)]
        for country, registry in registries.items()
    }

    catalog_items: dict[str, list[Candidate]] = {country: [] for country in selected}
    source_results: list[dict[str, Any]] = []
    for spec in policy["catalogs"]:
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

    official_items: dict[tuple[str, str], list[Candidate]] = {}
    if not args.no_official_pages:
        official_jobs = [
            (country, target)
            for country in selected
            for target in targets[country]
            if str(target.get("official_url", "")).startswith("https://")
        ]
        with futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {
                executor.submit(
                    official_page_candidates,
                    country,
                    target,
                    asset_limit,
                ): (country, str(target["name"]))
                for country, target in official_jobs
            }
            for future in futures.as_completed(future_map):
                key = future_map[future]
                try:
                    official_items[key] = future.result()
                except Exception as error:
                    print(f"DISCOVERY\t{key[0]}\t{key[1]}\tofficial crawl failed: {error}")
                    official_items[key] = []

    candidate_sets: dict[tuple[str, str], list[Candidate]] = {}
    for country in selected:
        for target in targets[country]:
            found: list[Candidate] = []
            for item in catalog_items[country]:
                matched = match_candidate(country, target, item)
                if matched:
                    found.append(matched)
            found.extend(official_items.get((country, str(target["name"])), []))
            if not args.no_github_search:
                found.extend(
                    github_candidates(
                        country,
                        target,
                        token,
                        trusted_repositories,
                        github_limit,
                    )
                )
                # Keep well below GitHub's authenticated code-search burst limit.
                if token:
                    time.sleep(6.5)
            candidate_sets[(country, str(target["name"]))] = deduplicate(found)

    def evaluate_target(
        country: str,
        target: dict[str, Any],
    ) -> tuple[list[Candidate], list[dict[str, Any]], Candidate | None, list[str]]:
        candidates = candidate_sets[(country, str(target["name"]))]
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
            if not eligible or candidate.url == current_url:
                evaluated.append(record)
                continue
            if args.skip_playback:
                record["playback_skipped"] = True
                evaluated.append(record)
                continue
            live, live_reason = live_manifest(candidate.url)
            record["live_manifest"] = live
            record["live_reason"] = live_reason
            if not live:
                evaluated.append(record)
                continue
            passed, evidence = playback_gate(
                candidate.url,
                int(target.get("min_height", 540)),
                attempts,
            )
            record["playback_passed"] = passed
            record["playback_evidence"] = evidence
            evaluated.append(record)
            if passed:
                selected_candidate = candidate
                selected_evidence = evidence
                break
        return candidates, evaluated, selected_candidate, selected_evidence

    jobs = [
        (country, target)
        for country in selected
        for target in targets[country]
    ]
    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        evaluation_results = list(
            executor.map(lambda job: evaluate_target(*job), jobs)
        )

    report_targets: list[dict[str, Any]] = []
    changed_countries: set[str] = set()
    qualified_count = 0
    for (country, target), result in zip(jobs, evaluation_results):
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
                f"{len(candidates)} candidate(s), no applied replacement"
            )
        report_targets.append(
            {
                "country": country,
                "target": target["name"],
                "published": target.get("publish") is True,
                "candidates_found": len(candidates),
                "evaluated": evaluated,
                "qualified": asdict(selected_candidate) if selected_candidate else None,
            }
        )

    if args.apply:
        for country in changed_countries:
            REGISTRIES[country].write_text(
                json.dumps(registries[country], ensure_ascii=False, indent=2) + "\n"
            )
        coverage = write_status()
    else:
        coverage = build_status()

    report = {
        "version": 1,
        "generated_at": utc_now(),
        "policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        "countries": selected,
        "targets_searched": len(report_targets),
        "changed_countries": sorted(changed_countries),
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
