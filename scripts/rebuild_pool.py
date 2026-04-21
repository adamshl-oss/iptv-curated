#!/usr/bin/env python3
"""Weekly: re-scrape aggregators, refresh candidates_pool.jsonl.

This doesn't modify the M3Us — the 6h refresh does that. This job KEEPS THE POOL
FRESH so backups stay plentiful: new streams get added, permanently-dead ones get
pruned.

Sources:
  - iptv-org (main index + country playlists + categories)
  - Paradise-91 ParaTV (French)
  - schumijo/iptv (French)
  - Pluto TV (US + FR via codyisland fork)
  - Free-TV aggregator
"""
import json, os, re, sys, subprocess, unicodedata
import concurrent.futures as cf
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent.parent
TEST = str(ROOT / "scripts" / "test_stream.sh")
POOL = ROOT / "candidates_pool.jsonl"
REF_DIR = ROOT / "reference"
PARALLEL = 20
TIMEOUT = 20

SOURCES = {
    "iptv-org-us":      "https://iptv-org.github.io/iptv/countries/us.m3u",
    "iptv-org-fr":      "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "iptv-org-dz":      "https://iptv-org.github.io/iptv/countries/dz.m3u",
    "iptv-org-fra":     "https://iptv-org.github.io/iptv/languages/fra.m3u",
    "iptv-org-ara":     "https://iptv-org.github.io/iptv/languages/ara.m3u",
    "iptv-org-news":    "https://iptv-org.github.io/iptv/categories/news.m3u",
    "iptv-org-sports":  "https://iptv-org.github.io/iptv/categories/sports.m3u",
    "free-tv":          "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "schumijo-fr":      "https://raw.githubusercontent.com/schumijo/iptv/main/fr.m3u8",
    "pluto-us":         "https://raw.githubusercontent.com/codyisland/Pluto-TV-Playlists-2026/main/output/plutotv_us.m3u8",
    "pluto-fr":         "https://raw.githubusercontent.com/codyisland/Pluto-TV-Playlists-2026/main/output/plutotv_fr.m3u8",
}

# -------------------- name normalization (same as refresh.py) --------------------

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

def tokens(s):
    return set(t for t in norm(s).split() if len(t) >= 3)

# -------------------- fetch + parse M3Us --------------------

def http_get(url, timeout=30):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (auto-refresh-bot)"})
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (URLError, TimeoutError, Exception) as e:
        print(f"  WARN fetch {url} failed: {e}", file=sys.stderr)
        return ""

def parse_m3u_text(text, source_label):
    entries = []
    if "#EXTM3U" not in text: return entries
    cur_name = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            m = re.search(r',(.*)$', line)
            cur_name = m.group(1).strip() if m else None
        elif line and not line.startswith("#"):
            if cur_name:
                entries.append({"channel": cur_name, "url": line, "source": source_label})
            cur_name = None
    return entries

# -------------------- reference channels --------------------

def load_references():
    """Collect all reference channel names + aliases."""
    names = set()
    for f in REF_DIR.glob("*.json"):
        data = json.load(open(f))
        for r in data:
            n = r.get("name") or r.get("branding") or ""
            if n: names.add(norm(n))
            b = r.get("branding","")
            if b: names.add(norm(b))
            for a in r.get("aliases", []) or []:
                if a: names.add(norm(a))
    return {n for n in names if n}

def channel_is_interesting(name, ref_names):
    """Cheap filter: is this candidate plausibly one of the ref channels?"""
    n = norm(name)
    if not n: return False
    toks = tokens(name)
    if not toks: return False
    # Whole-phrase or token-subset match
    for rn in ref_names:
        if rn == n: return True
        if re.search(r'(?:^|\s)' + re.escape(rn) + r'(?:\s|$)', n): return True
        rn_toks = set(t for t in rn.split() if len(t) >= 3)
        if rn_toks and rn_toks <= toks: return True
    return False

# -------------------- verify --------------------

def test_url(url):
    try:
        p = subprocess.run([TEST, url], capture_output=True, text=True, timeout=TIMEOUT)
        out = (p.stdout or p.stderr).strip().split("|")
        return (out[0] if out else "ERR"), out
    except Exception:
        return "EXC", []

# -------------------- main --------------------

def main():
    print("Loading references...", flush=True)
    ref_names = load_references()
    print(f"  {len(ref_names)} normalized reference names", flush=True)

    # Fetch all sources
    print("\nFetching aggregators...", flush=True)
    all_candidates = []
    for label, url in SOURCES.items():
        text = http_get(url)
        items = parse_m3u_text(text, label)
        relevant = [e for e in items if channel_is_interesting(e["channel"], ref_names)]
        all_candidates.extend(relevant)
        print(f"  {label}: {len(items)} total, {len(relevant)} relevant", flush=True)

    # Dedup by URL
    seen_urls = set()
    candidates = []
    for c in all_candidates:
        if c["url"] in seen_urls: continue
        seen_urls.add(c["url"])
        candidates.append(c)

    # Fold in existing pool (may have entries outside aggregators)
    existing = []
    if POOL.exists():
        with POOL.open() as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    o = json.loads(line)
                    if o.get("url") and o["url"] not in seen_urls:
                        seen_urls.add(o["url"])
                        candidates.append(o)
                except Exception: pass

    print(f"\nTotal unique URLs to verify: {len(candidates)}", flush=True)

    # Verify all (parallel)
    done = 0; passes = 0
    results = []
    def run(c):
        status, out = test_url(c["url"])
        if status == "PASS":
            c["resolution"] = out[4] if len(out) > 4 else ""
            c["codec"] = out[3] if len(out) > 3 else ""
            return c
        return None

    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        futs = {ex.submit(run, c): c for c in candidates}
        for f in cf.as_completed(futs):
            r = f.result()
            done += 1
            if r:
                results.append(r); passes += 1
            if done % 50 == 0 or done == len(candidates):
                print(f"  verified {done}/{len(candidates)}, passes={passes}", flush=True)

    # Filter: skip ephemeral YouTube URLs
    results = [r for r in results if "googlevideo.com" not in r["url"]]

    # Write pool
    with POOL.open("w") as f:
        for r in results:
            # Strip test artifacts, keep core
            out = {"channel": r.get("channel",""), "url": r.get("url",""),
                   "source": r.get("source","unknown"),
                   "codec": r.get("codec",""), "resolution": r.get("resolution","")}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(results)} passing entries to {POOL.name}")

if __name__ == "__main__":
    main()
