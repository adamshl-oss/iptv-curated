#!/usr/bin/env python3
"""Refresh YouTube Live HLS URLs every 90 minutes.

For each channel in scripts/yt_channels.json:
  1. yt-dlp --get-url <handle> to resolve current HLS manifest
  2. 5-gate verify it
  3. Regenerate the YT-LIVE block in each claudette-*.m3u

YT-LIVE block is delimited by these markers so the 6h refresh leaves it alone:
  #---YT-LIVE-BEGIN---
  ... youtube entries ...
  #---YT-LIVE-END---
"""
import json, subprocess, re, sys, os
import concurrent.futures as cf
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = str(ROOT / "scripts" / "test_stream.sh")
CONFIG = ROOT / "scripts" / "yt_channels.json"
PARALLEL = 6
TIMEOUT = 45

BEGIN = "#---YT-LIVE-BEGIN---"
END   = "#---YT-LIVE-END---"

def resolve_youtube(handle):
    """yt-dlp --get-url → returns HLS URL or None.
    Tries multiple extractor clients since YouTube blocks some datacenter IPs
    when using the default 'web' client."""
    for client in ("default", "web_safari", "android_vr"):
        try:
            command = [
                "yt-dlp", "--no-warnings", "--no-playlist", "--skip-download",
                "--js-runtimes", "node",
                "--remote-components", "ejs:github",
            ]
            if server_home := os.environ.get("BGUTIL_SERVER_HOME"):
                command.extend(
                    [
                        "--extractor-args",
                        f"youtubepot-bgutilscript:server_home={server_home}",
                    ]
                )
            command.extend(
                [
                    "--extractor-args", f"youtube:player_client={client}",
                    "-f", "best[protocol=m3u8_native]/best",
                    "--get-url", handle,
                ]
            )
            p = subprocess.run(
                command,
                capture_output=True, text=True, timeout=TIMEOUT
            )
            if p.returncode == 0:
                url = (p.stdout or "").strip().splitlines()[-1] if p.stdout else ""
                if url.startswith("http"):
                    return url
        except Exception:
            pass
    return None

def verify_stream(url):
    try:
        p = subprocess.run([TEST, url], capture_output=True, text=True, timeout=TIMEOUT)
        line = (p.stdout or p.stderr).strip().splitlines()[-1]
        return line.startswith("PASS")
    except Exception:
        return False

def process_channel(ch):
    """Returns (ch, url_or_None)."""
    url = resolve_youtube(ch["handle"])
    if not url:
        return (ch, None, "resolve_failed")
    ok = verify_stream(url)
    return (ch, url if ok else None, "ok" if ok else "verify_failed")

def render_block(entries):
    """Render a YT-LIVE block for one playlist."""
    lines = [BEGIN]
    for ch, url, _status in entries:
        if not url: continue
        chno = ch.get("chno", 0)
        attrs = []
        if chno: attrs.append(f'tvg-chno="{chno}"')
        attrs.append(f'group-title="{ch["group"]}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{ch["name"]}')
        lines.append(url)
    lines.append(END)
    return "\n".join(lines) + "\n"

def splice_m3u(path, block):
    """Replace existing YT-LIVE block in M3U, or append at end."""
    if not path.exists():
        return
    text = path.read_text()
    pattern = re.compile(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(block, text)
    else:
        # Append at end
        if not text.endswith("\n"): text += "\n"
        text += block
    path.write_text(text)

def main():
    with CONFIG.open() as f:
        channels = json.load(f)

    print(f"Resolving {len(channels)} YouTube live handles...", flush=True)
    by_playlist = {"usa": [], "france": [], "algeria": [], "us-news": []}

    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        results = list(ex.map(process_channel, channels))

    for ch, url, status in results:
        print(f"  [{status:15s}] {ch['name']:<30s} {ch['playlist']:<8s}  {'' if not url else url[:60]}", flush=True)
        by_playlist[ch["playlist"]].append((ch, url, status))

    # For each playlist, regenerate the YT-LIVE block
    for pl, entries in by_playlist.items():
        path = ROOT / f"claudette-{pl}.m3u"
        block = render_block(entries)
        splice_m3u(path, block)
        working = sum(1 for _, u, _ in entries if u)
        print(f"\n{path.name}: wrote {working}/{len(entries)} YT entries", flush=True)

if __name__ == "__main__":
    main()
