#!/usr/bin/env python3
"""Build the combined Lume playlist "Chaines TV" from the three published
country playlists (France + Algérie + USA).

Reads the three published .m3u files and emits one .m3u containing every
channel, with:
  - a single #EXTM3U header pointing at the shared EPG,
  - tvg-chno renumbered 1..N so channel ordering is unambiguous across
    countries (the EPG matches on tvg-id, which is left untouched),
  - group-titles untouched (they are already country-prefixed).

Every step is verified: channel count, unique tvg-ids, EPG coverage of every
tvg-id, and no duplicate stream URLs.
"""
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET

EPG_URL = "https://adamshl-oss.github.io/iptv-curated/lume-epg.xml.gz"
SOURCES = [
    ("lume-france.m3u", "France"),
    ("lume-algeria.m3u", "Algérie"),
    ("lume-usa.m3u", "USA"),
]
OUT_NAME = "lume-chaines-tv.m3u"

EXTINF = re.compile(r"^#EXTINF:(-?\d+)\s+(.*)$")
TVGID = re.compile(r'tvg-id="([^"]*)"')
CHNO = re.compile(r'tvg-chno="([^"]*)"')


def read_playlist(path):
    """Yield (extinf_attrs, display_name, url) per channel."""
    lines = open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            attrs = line[len("#EXTINF:"):]
            url = ""
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt and not nxt.startswith("#"):
                    url = nxt
                    break
                j += 1
            # display name is after the last comma of the EXTINF line
            display = attrs.rsplit(",", 1)[-1].strip()
            yield attrs, display, url
            i = j + 1
            continue
        i += 1


def build(base_dir, epg_path):
    out = ['#EXTM3U url-tvg="%s"' % EPG_URL]
    seen_ids = {}
    seen_urls = {}
    chno = 0
    total = 0
    for fname, _country in SOURCES:
        path = os.path.join(base_dir, fname)
        for attrs, display, url in read_playlist(path):
            if not url:
                raise SystemExit("channel without URL in %s: %s" % (fname, display))
            m = TVGID.search(attrs)
            if not m or not m.group(1):
                raise SystemExit("channel without tvg-id in %s: %s" % (fname, display))
            tvg_id = m.group(1)
            if tvg_id in seen_ids:
                raise SystemExit("duplicate tvg-id %s (%s and %s)"
                                 % (tvg_id, seen_ids[tvg_id], fname))
            if url in seen_urls:
                raise SystemExit("duplicate URL %s (%s and %s)"
                                 % (url, seen_urls[url], display))
            seen_ids[tvg_id] = fname
            seen_urls[url] = display
            chno += 1
            total += 1
            attrs = CHNO.sub('tvg-chno="%d"' % chno, attrs)
            out.append("#EXTINF:" + attrs)
            out.append(url)
    return out, seen_ids, total


def check_epg(epg_path, tvg_ids):
    with gzip.open(epg_path, "rb") as fh:
        root = ET.parse(fh).getroot()
    epg_ids = set()
    for ch in root.iter("channel"):
        cid = ch.get("id")
        if cid:
            epg_ids.add(cid)
    missing = sorted(t for t in tvg_ids if t not in epg_ids)
    return missing, len(epg_ids)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "/Users/adam/.iptv-playlists/lume-2026-11"
    out_path = os.path.join(base, OUT_NAME)
    epg_path = os.path.join(base, "lume-epg.xml.gz")
    lines, ids, total = build(base, epg_path)
    missing, epg_total = check_epg(epg_path, ids)
    if missing:
        raise SystemExit("tvg-ids absent from EPG: %s" % ", ".join(missing))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote %s" % out_path)
    print("channels: %d   unique tvg-ids: %d   unique URLs: %d" % (total, len(ids), total))
    print("EPG: %d channels, every tvg-id resolved" % epg_total)


if __name__ == "__main__":
    main()
