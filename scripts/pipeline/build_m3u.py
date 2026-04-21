#!/usr/bin/env python3
"""Read a tested_*.json (with winner per ref channel) and emit a final M3U.
Also accepts optional *_hunted.jsonl overlay: hunted URLs override winner if they pass."""
import json, sys, os, re, subprocess

TEST = "/Users/adam/iptv-rebuild/test_stream.sh"

def test_url(url, timeout=25):
    try:
        p = subprocess.run([TEST, url], capture_output=True, text=True, timeout=timeout)
        line = (p.stdout or p.stderr).strip()
        parts = line.split("|")
        return parts[0] == "PASS", parts
    except Exception:
        return False, None

def load_hunted(path):
    """Load a hunted.jsonl and re-verify each entry. Return dict {channel_lower: [entry,...]}"""
    out = {}
    if not os.path.exists(path): return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not e.get("url"): continue
            # Re-verify (hunted files may be old)
            ok, parts = test_url(e["url"])
            if not ok:
                continue
            key = e["channel"].strip().lower()
            out.setdefault(key, []).append({
                "name": e.get("channel"),
                "url": e["url"],
                "source": e.get("source", "hunted"),
                "status": "PASS",
                "codec": (parts[3] if parts and len(parts) > 3 else ""),
                "resolution": (parts[4] if parts and len(parts) > 4 else ""),
                "logo": e.get("logo", ""),
            })
    return out

def pick_winner(entry, hunted_map):
    """Prefer hunted > current winner if both PASS."""
    ref = entry["ref"]
    ref_name = (ref.get("name") or ref.get("branding") or "").strip()
    ref_aliases = ref.get("aliases", [])
    names_to_try = [ref_name] + list(ref_aliases or [])
    if ref.get("branding") and ref.get("branding") != ref_name:
        names_to_try.append(ref["branding"])
    for n in names_to_try:
        if not n: continue
        key = n.strip().lower()
        if key in hunted_map and hunted_map[key]:
            return hunted_map[key][0]
    return entry.get("winner")

def build_m3u(tested_path, hunted_path, playlist_name, order_key):
    with open(tested_path) as f:
        tested = json.load(f)
    hunted = load_hunted(hunted_path) if hunted_path else {}
    lines = ["#EXTM3U"]
    winners = []
    # Sort by ref number (for Freebox numeric order) ascending
    tested_sorted = sorted(tested, key=lambda e: (e["ref"].get("number", 9999), e["ref"].get("name", "")))
    for entry in tested_sorted:
        ref = entry["ref"]
        # Skip Freebox "Mosaïque" placeholder channels
        if ref.get("name", "").lower().startswith("mosa") or "mosa\u00efque" in ref.get("name", "").lower():
            continue
        w = pick_winner(entry, hunted)
        if not w: continue
        name = ref.get("branding") or ref.get("name")
        num = ref.get("number") or ref.get(order_key) or 0
        category = ref.get("category", "Live")
        logo = w.get("logo") or ref.get("logo", "")
        tvg_id = w.get("tvg_id", "")
        extinf_attrs = []
        if tvg_id: extinf_attrs.append(f'tvg-id="{tvg_id}"')
        if num: extinf_attrs.append(f'tvg-chno="{num}"')
        if logo: extinf_attrs.append(f'tvg-logo="{logo}"')
        if category: extinf_attrs.append(f'group-title="{category}"')
        attrs_str = " ".join(extinf_attrs)
        lines.append(f'#EXTINF:-1 {attrs_str},{name}')
        lines.append(w["url"])
        winners.append({"number": num, "name": name, "category": category,
                        "resolution": w.get("resolution", ""),
                        "codec": w.get("codec", ""), "url": w["url"][:80]})
    return "\n".join(lines) + "\n", winners

def main():
    tested_path = sys.argv[1]
    hunted_path = sys.argv[2] if len(sys.argv) > 2 else None
    out_path = sys.argv[3]
    playlist_name = sys.argv[4] if len(sys.argv) > 4 else "playlist"
    order_key = sys.argv[5] if len(sys.argv) > 5 else "number"
    content, winners = build_m3u(tested_path, hunted_path, playlist_name, order_key)
    with open(out_path, "w") as f:
        f.write(content)
    print(f"Wrote {len(winners)} channels to {out_path}", file=sys.stderr)
    # Log
    log_path = out_path + ".log"
    with open(log_path, "w") as f:
        for w in winners:
            f.write(f"{w['number']:>4}  {w['category'][:20]:<20}  {w['name']:<40}  {w['resolution']:<10}  {w['codec']}\n")
    print(f"Log: {log_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
