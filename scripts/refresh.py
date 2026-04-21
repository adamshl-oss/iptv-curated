#!/usr/bin/env python3
"""Self-healing playlist refresher. Runs every 6 hours in GitHub Actions.

On each channel in the current M3U:
  1. Test the current URL. If it passes, keep.
  2. If it fails, look up the candidate pool for the same channel name.
  3. Test pool entries (until one passes). Swap that in as the new URL.
  4. Only DROP a channel if neither the current URL nor any pool entry plays.

This prevents the playlist from monotonically draining to zero.
The weekly rebuild workflow handles DISCOVERY of new streams.
"""
import os, re, sys, json, subprocess, unicodedata
import concurrent.futures as cf
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = str(ROOT / "scripts" / "test_stream.sh")
POOL = ROOT / "candidates_pool.jsonl"
PLAYLISTS = ["claudette-usa.m3u", "claudette-france.m3u", "claudette-algeria.m3u"]
PARALLEL = 3      # low to avoid tvpass.org rate limits
TIMEOUT = 22

# -------------------- name normalization --------------------

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

NOISE = re.compile(
    r'\b(hd|sd|uhd|fhd|4k|1080p?|720p?|576p?|480p?|360p?|240p?|live|tv|channel|chaine|chaîne|'
    r'geo|blocked|eastern|east|west|feed|usa|not 24 7)\b', re.IGNORECASE)

def norm(s):
    if not s: return ""
    s = strip_accents(s).lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\[[^\]]*\]', ' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = NOISE.sub(' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# -------------------- helpers --------------------

def rewrite_tokenized(url):
    """thetvapp.to tokenized → tvpass.org permalink (issues fresh tokens per request)."""
    m = re.match(r'^https?://[^/]*thetvapp\.to/hls/([^/]+)/', url)
    if m:
        return f'https://tvpass.org/live/{m.group(1)}/hd'
    return url

def parse_m3u(path):
    header = "#EXTM3U"
    entries = []
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
                entries.append((extinf, lines[j].strip()))
                i = j + 1
                continue
        elif ln.startswith("#EXTM3U"):
            header = ln
        i += 1
    return header, entries

def extinf_name(ext):
    m = re.search(r',(.*)$', ext)
    return m.group(1).strip() if m else ""

def test_url(url):
    try:
        p = subprocess.run([TEST, url], capture_output=True, text=True, timeout=TIMEOUT)
        out = (p.stdout or p.stderr).strip().split("|")
        return out[0] if out else "ERR"
    except Exception:
        return "EXC"

def write_m3u(path, header, entries):
    with path.open("w") as f:
        f.write(header + "\n")
        for ext, url in entries:
            f.write(ext + "\n")
            f.write(url + "\n")

# -------------------- pool loading --------------------

def load_pool():
    """Return {norm_name: [pool_entry, ...]} so we can do a backup lookup per channel."""
    index = {}
    if not POOL.exists():
        print(f"WARN: no candidates pool at {POOL}", file=sys.stderr)
        return index
    with POOL.open() as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                o = json.loads(line)
                n = norm(o.get("channel",""))
                if n and o.get("url"):
                    index.setdefault(n, []).append(o)
            except Exception: pass
    # Sort each bucket by resolution desc
    def res_score(o):
        r = o.get("resolution","")
        if "x" not in r: return 0
        try:
            w,h = r.split("x"); return int(w)*int(h)
        except: return 0
    for k in index: index[k].sort(key=lambda o: -res_score(o))
    return index

def find_backups(channel_name, pool):
    """Find pool entries matching the channel name."""
    key = norm(channel_name)
    return pool.get(key, [])[:6]   # at most 6 backup candidates per slot

# -------------------- main process --------------------

def process(path, pool):
    print(f"\n=== {path.name} ===", flush=True)
    header, entries = parse_m3u(path)
    # Rewrite any leftover tokenized URLs to permalinks
    entries = [(e, rewrite_tokenized(u)) for e, u in entries]

    # Phase 1: test current URLs
    urls = [u for _, u in entries]
    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        statuses = list(ex.map(test_url, urls))

    survived = []        # (ext, url) — passed primary test
    candidates_swap = [] # (idx, ext, name) — need to try pool backups
    for i, (ext, url) in enumerate(entries):
        if statuses[i] == "PASS":
            survived.append((ext, url))
        else:
            candidates_swap.append((i, ext, extinf_name(ext), url))

    print(f"Primary test: {len(survived)}/{len(entries)} passed "
          f"({len(candidates_swap)} need backup)", flush=True)

    # Phase 2: for each failing entry, try pool backups (serial per channel, but parallel across channels)
    def try_backups(job):
        idx, ext, name, orig_url = job
        backups = find_backups(name, pool)
        for b in backups:
            if b["url"] == orig_url:      # same URL — skip
                continue
            s = test_url(b["url"])
            if s == "PASS":
                return (idx, ext, b["url"], "swap", orig_url, name, b.get("source",""))
        return (idx, ext, None, "drop", orig_url, name, "")

    swaps = []
    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        for r in ex.map(try_backups, candidates_swap):
            swaps.append(r)

    kept = survived[:]  # start with originals that passed
    swapped = 0
    dropped = 0
    for idx, ext, new_url, action, orig, name, src in swaps:
        if action == "swap":
            kept.append((ext, new_url))
            swapped += 1
            print(f"  SWAP  {name}  (source: {src})  old={orig[:60]}", flush=True)
        else:
            dropped += 1
            print(f"  DROP  {name}  no working backup  old={orig[:60]}", flush=True)

    # Preserve original M3U order by re-sorting against the ref channel ordering in the file
    # (we lost ordering when partitioning — re-establish by original index)
    order = {}
    for i, (ext, url) in enumerate(entries):
        order[ext] = i
    kept.sort(key=lambda x: order.get(x[0], 9_999_999))

    write_m3u(path, header, kept)
    print(f"Result: {len(kept)} kept ({len(survived)} unchanged + {swapped} swapped), {dropped} dropped",
          flush=True)
    return len(kept), len(entries), swapped, dropped

def main():
    pool = load_pool()
    print(f"Loaded candidate pool: {sum(len(v) for v in pool.values())} URLs across "
          f"{len(pool)} channels", flush=True)

    total_kept = total_all = total_swaps = total_drops = 0
    for pl in PLAYLISTS:
        path = ROOT / pl
        if not path.exists(): continue
        k,a,s,d = process(path, pool)
        total_kept += k; total_all += a; total_swaps += s; total_drops += d
    print(f"\n=== TOTAL: {total_kept}/{total_all} channels  "
          f"(+{total_swaps} swapped, -{total_drops} dropped) ===")

if __name__ == "__main__":
    main()
