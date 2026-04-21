#!/usr/bin/env python3
"""Refresh Claude playlists: re-verify every stream URL, drop dead ones, rewrite M3Us.

Ephemeral token protection:
- tvpass.org permalinks (https://tvpass.org/live/<NAME>/hd) are stable — they 302 to fresh
  tokenized streams on every fetch, so they never expire.
- If a URL on thetvapp.to direct token is found (leftover), rewrite it to the permalink form.

Runs on GitHub Actions every 6h. Concurrency=3 to avoid tvpass.org rate limit.
"""
import os, re, sys, subprocess, concurrent.futures as cf
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = str(ROOT / "scripts" / "test_stream.sh")
PLAYLISTS = ["claude-usa.m3u", "claude-france.m3u", "claude-algeria.m3u"]
PARALLEL = 3  # Keep low — tvpass.org rate-limits aggressive parallelism
TIMEOUT = 22

def rewrite_tokenized(url: str) -> str:
    """Tokenized thetvapp.to URLs → tvpass.org permalinks."""
    m = re.match(r'^https?://[^/]*thetvapp\.to/hls/([^/]+)/', url)
    if m:
        return f'https://tvpass.org/live/{m.group(1)}/hd'
    return url

def parse_m3u(path: Path):
    entries = []  # list of (extinf_line, url)
    header = "#EXTM3U"
    with path.open() as f:
        lines = [l.rstrip("\n") for l in f]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#EXTINF"):
            extinf = ln
            j = i + 1
            while j < len(lines) and (not lines[j] or lines[j].startswith("#")):
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                entries.append((extinf, url))
                i = j + 1
                continue
        elif ln.startswith("#EXTM3U"):
            header = ln
        i += 1
    return header, entries

def test_url(url: str):
    try:
        p = subprocess.run([TEST, url], capture_output=True, text=True, timeout=TIMEOUT)
        out = (p.stdout or p.stderr).strip().split("|")
        return out[0] if out else "ERR", url
    except Exception:
        return "EXC", url

def write_m3u(path: Path, header: str, entries: list):
    with path.open("w") as f:
        f.write(header + "\n")
        for ext, url in entries:
            f.write(ext + "\n")
            f.write(url + "\n")

def process(playlist_path: Path):
    print(f"\n=== {playlist_path.name} ===", flush=True)
    header, entries = parse_m3u(playlist_path)
    # Rewrite tokenized URLs to permalinks before testing
    entries = [(e, rewrite_tokenized(u)) for e, u in entries]

    # Test each URL
    urls = [u for _, u in entries]
    print(f"Testing {len(urls)} URLs (parallel={PARALLEL})...", flush=True)
    status_by_url = {}
    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        for status, url in ex.map(test_url, urls):
            status_by_url[url] = status

    kept = [(e, u) for e, u in entries if status_by_url.get(u) == "PASS"]
    dropped = [(e, u, status_by_url.get(u)) for e, u in entries if status_by_url.get(u) != "PASS"]

    print(f"Kept: {len(kept)}/{len(entries)}  Dropped: {len(dropped)}", flush=True)
    for e, u, s in dropped:
        name = re.search(r',(.*)$', e)
        nm = name.group(1) if name else u
        print(f"  DROP [{s}] {nm}  {u[:70]}", flush=True)

    write_m3u(playlist_path, header, kept)
    return len(kept), len(entries)

def main():
    total_kept = total_all = 0
    for pl in PLAYLISTS:
        path = ROOT / pl
        if not path.exists():
            print(f"skip missing {pl}", file=sys.stderr)
            continue
        k, a = process(path)
        total_kept += k; total_all += a
    print(f"\n=== TOTAL: {total_kept}/{total_all} channels playing ===")

if __name__ == "__main__":
    main()
