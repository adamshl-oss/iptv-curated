#!/usr/bin/env python3
"""Keep the stable French IPTVX playlist healthy without a local Mac.

Every run playback-tests the current source for every channel. A source is
only changed after it fails twice and an alternate passes a complete
ffprobe/ffmpeg playback test. Channels are never silently removed: if no
alternate works, the entry remains present and the playback-checking workflow
records a failure for follow-up.
"""

from __future__ import annotations

import concurrent.futures as futures
import json
import re
import subprocess
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "french-tv-july-2026-v2.m3u"
SOURCES = ROOT / "scripts" / "french_sources.json"
POOL = ROOT / "candidates_pool.jsonl"
TEST = ROOT / "scripts" / "test_stream.sh"
EXPECTED_CHANNELS = 32
PARALLEL_TESTS = 6
TEST_TIMEOUT_SECONDS = 60

POOL_ALIASES = {
    "Ciné Nanar+": ["Zylo Ciné Nanar"],
    "France 24 Français (1080p)": ["France 24 French"],
    "Sophia TV": ["Sophia TV Français"],
}

NOISE = re.compile(
    r"\b(hd|sd|uhd|fhd|4k|1080p?|720p?|576p?|480p?|360p?|240p?|"
    r"live|tv|channel|chaine|chaîne|geo|blocked|feed)\b",
    re.IGNORECASE,
)


def normalize(name: str) -> str:
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(character)
    ).lower()
    value = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)
    value = re.sub(r"[^\w\s]", " ", value)
    value = NOISE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_playlist(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines()
    header = next(
        (line for line in lines if line.startswith("#EXTM3U")),
        "#EXTM3U",
    )
    entries: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        cursor = index + 1
        while cursor < len(lines) and (
            not lines[cursor] or lines[cursor].startswith("#")
        ):
            cursor += 1
        if cursor < len(lines) and lines[cursor].startswith(("http://", "https://")):
            entries.append((line, lines[cursor].strip()))
    return header, entries


def channel_name(extinf: str) -> str:
    return extinf.rsplit(",", 1)[-1].strip()


def test_url(url: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(TEST), url],
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "test_timeout"
    output = (completed.stdout or completed.stderr).strip()
    fields = output.split("|")
    if completed.returncode == 0 and fields and fields[0] == "PASS":
        codec = fields[3] if len(fields) > 3 else "unknown codec"
        resolution = fields[4] if len(fields) > 4 else "unknown resolution"
        return True, f"{codec} {resolution}"
    reason = fields[2] if len(fields) > 2 else output or "unknown failure"
    return False, reason


def load_known_sources() -> dict[str, list[str]]:
    payload = json.loads(SOURCES.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError("French source registry must be a JSON object")
    return {
        str(name): [str(url) for url in urls if str(url).startswith(("http://", "https://"))]
        for name, urls in payload.items()
        if isinstance(urls, list)
    }


def load_pool() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    if not POOL.exists():
        return index
    for line in POOL.read_text().splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = normalize(str(record.get("channel", "")))
        url = str(record.get("url", ""))
        if name and url.startswith(("http://", "https://")):
            index.setdefault(name, []).append(url)
    return index


def alternates_for(
    name: str,
    current_url: str,
    known_sources: dict[str, list[str]],
    pool: dict[str, list[str]],
) -> list[str]:
    candidates = list(known_sources.get(name, []))
    pool_names = [name, *POOL_ALIASES.get(name, [])]
    for pool_name in pool_names:
        candidates.extend(pool.get(normalize(pool_name), []))

    unique: list[str] = []
    seen = {current_url}
    for candidate in candidates:
        if candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def render(header: str, entries: list[tuple[str, str]]) -> str:
    lines = [header]
    for extinf, url in entries:
        lines.extend([extinf, url])
    lines.extend(["#---YT-LIVE-BEGIN---", "#---YT-LIVE-END---"])
    return "\n".join(lines) + "\n"


def main() -> None:
    header, entries = parse_playlist(PLAYLIST.read_text())
    if len(entries) != EXPECTED_CHANNELS:
        raise RuntimeError(
            f"French playlist has {len(entries)} entries; "
            f"expected {EXPECTED_CHANNELS}"
        )

    known_sources = load_known_sources()
    pool = load_pool()

    with futures.ThreadPoolExecutor(max_workers=PARALLEL_TESTS) as executor:
        primary_results = list(executor.map(lambda entry: test_url(entry[1]), entries))

    def repair(
        item: tuple[tuple[str, str], tuple[bool, str]],
    ) -> tuple[str, str, str]:
        (extinf, current_url), (passed, detail) = item
        name = channel_name(extinf)
        if passed:
            return current_url, "KEEP", detail

        # Retry before replacing a source so one transient CDN miss never causes churn.
        retry_passed, retry_detail = test_url(current_url)
        if retry_passed:
            return current_url, "KEEP_AFTER_RETRY", retry_detail

        failure = f"{detail}; retry: {retry_detail}"
        for alternate in alternates_for(name, current_url, known_sources, pool):
            alternate_passed, alternate_detail = test_url(alternate)
            if alternate_passed:
                return alternate, "SWAP", alternate_detail
        return current_url, "UNRESOLVED", failure

    with futures.ThreadPoolExecutor(max_workers=PARALLEL_TESTS) as executor:
        repairs = list(executor.map(repair, zip(entries, primary_results)))

    updated_entries: list[tuple[str, str]] = []
    unresolved = 0
    swapped = 0
    for (extinf, old_url), (new_url, action, detail) in zip(entries, repairs):
        name = channel_name(extinf)
        updated_entries.append((extinf, new_url))
        if action == "SWAP":
            swapped += 1
            print(f"SWAP\t{name}\t{detail}\t{new_url}")
        elif action == "UNRESOLVED":
            unresolved += 1
            print(f"::warning::{name} has no working alternate ({detail})")
        else:
            print(f"PASS\t{name}\t{detail}")

    updated = render(header, updated_entries)
    if updated != PLAYLIST.read_text():
        PLAYLIST.write_text(updated)
        print(f"Updated French playlist with {swapped} verified failover(s)")
    else:
        print("French playlist sources are unchanged")
    print(
        f"French refresh complete: {EXPECTED_CHANNELS - unresolved}/"
        f"{EXPECTED_CHANNELS} currently healthy, {unresolved} unresolved"
    )


if __name__ == "__main__":
    main()
