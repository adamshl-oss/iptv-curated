#!/usr/bin/env python3
"""Build the Lume programme guide (lume-epg.xml.gz) from public XMLTV feeds.

The Lume app resolves its guide by ``tvg-id``.  This script emits one
``<channel>`` element per channel of the published Lume playlist and fills in
programme data for every channel that has a public XMLTV source:

* France   -> epgshare FR1
* USA      -> epgshare US2
* Algerie / Monde arabe / Maroc -> no public XMLTV guide, emitted without
  programme data (the channel still plays, it simply has no guide rows).

Unlike the IPTVX guide (``epg.xml.gz``) this file is published separately so
the nightly IPTVX refresh job can never overwrite it.
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
PLAYLIST = ROOT / "lume-chaines-tv.m3u"
OUTPUT = ROOT / "lume-epg.xml.gz"

FR_SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
US_SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

# source id (epgshare) -> Lume tvg-id
FR_MAP = {
    "France.2.fr": "France2.fr",
    "France.3.fr": "France3.fr",
    "France.3.-.Bretagne.fr": "France3Bretagne.fr",
    "France.4.fr": "France4.fr",
    "France.5.fr": "France5.fr",
    "M6.fr": "M6.fr",
    "W9.fr": "W9.fr",
    "Arte.fr": "ARTE.fr",
    "TMC.fr": "TMC.fr",
    "6ter.fr": "6ter.fr",
    "CSTAR.fr": "CStar.fr",
    "BFM.TV.fr": "BFMTV.fr",
    "LCI.fr": "LCI.fr",
    "CNews.fr": "CNews.fr",
    "Euronews.fr": "Euronews.fr",
    "France.24.fr": "France24.fr",
    "RMC.Story.fr": "RMCStory.fr",
    "RMC.Découverte.fr": "RMCDecouverte.fr",
    "Gulli.fr": "Gulli.fr",
    "L'Equipe.fr": "LEquipe.fr",
    "20.Minutes.TV.fr": "20MinutesTV.fr",
    "TF1.fr": "TF1.fr",
    "TF1.Séries-Films.fr": "TF1SeriesFilms.fr",
    "TFX.fr": "TFX.fr",
    "AL.ARABIYA.fr": "Alarabiya.ae",
    "Gong.Max.fr": "Gong.fr",
    "Télé.Maroc.fr": "MarocTV.ma",
}

US_MAP = {
    "CNN.HD.us2": "CNN.us",
    "MSNBC.HD.us2": "MSNBC.us",
    "NASA.Plus.us2": "NASATV.us",
    "ESPN.HD.us2": "ESPN.us",
    "NFL.Network.HD.us2": "NFLNetwork.us",
    "Food.Network.HD.us2": "FoodNetwork.us",
    "Bravo.HD.us2": "Bravo.us",
    "USA.Network.HD.us2": "USANetwork.us",
    "Syfy.HD.us2": "Syfy.us",
    "TNT.HD.us2": "TNT.us",
    "TBS.HD.us2": "TBS.us",
    "Comedy.Central.HD.us2": "ComedyCentral.us",
    "AMC+.us2": "AMC.us",
    "National.Geographic.HD.us2": "NationalGeographic.us",
    "Cartoon.Network.HD.us2": "CartoonNetwork.us",
    "MTV.-.Music.Television.HD.us2": "MTV.us",
    "BBC.News.(North.America).HD.us2": "BBCNews.us",
    "Bloomberg.HD.us2": "BloombergTV.us",
    "Fox.Business.HD.us2": "FoxBusinessNetwork.us",
    "Fox.News.Channel.HD.us2": "FoxNews.us",
    "CBS.News.National.Stream.us2": "CBSNews24-7.us",
    "FS1.HD.us2": "FoxSports.us",
    "Lifetime.HD.us2": "LifetimeMovies.us",
    "Disney.Channel.HD.us2": "DisneyChannel.us",
    "ABC.National.Feed.us2": "ABC6Phoenix.us",
    "NBC.East.Stream.us2": "NBCNewsNOW.us",
    "NBC.West.Stream.us2": "NBCNewsNowBayArea.us",
}

ATTR_RE = re.compile(r'([a-zA-Z0-9-]+)="([^"]*)"')


def parse_playlist(path: Path) -> list[dict]:
    """Return the channel list of the published Lume playlist."""
    channels: list[dict] = []
    current: dict | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            attrs = dict(ATTR_RE.findall(line))
            current = {
                "id": attrs.get("tvg-id", ""),
                "name": attrs.get("tvg-name") or line.rsplit(",", 1)[-1].strip(),
                "logo": attrs.get("tvg-logo", ""),
            }
        elif line and not line.startswith("#") and current is not None:
            current["url"] = line
            channels.append(current)
            current = None
    return channels


def fetch(source: str) -> bytes:
    request = Request(source, headers={"User-Agent": "iptvx-lume-epg/1.0"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def programme_channel_counts(xml_bytes: bytes) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, element in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if element.tag == "programme":
            cid = element.get("channel", "")
            counts[cid] = counts.get(cid, 0) + 1
            element.clear()
    return counts


def build(source_url: str, mapping: dict[str, str], wanted: set[str]) -> tuple[list[ET.Element], dict[str, int]]:
    """Return the programme elements whose source channel maps to a Lume id."""
    payload = fetch(source_url)
    elements: list[ET.Element] = []
    counts: dict[str, int] = {}
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag != "programme":
                continue
            target = mapping.get(element.get("channel", ""))
            if not target or target not in wanted:
                element.clear()
                continue
            element.set("channel", target)
            elements.append(element)
            counts[target] = counts.get(target, 0) + 1
    return elements, counts


def build_guide(playlist: Path, output: Path, keep_icons: bool = True) -> tuple[int, int, int]:
    channels = parse_playlist(playlist)
    if not channels:
        raise RuntimeError("playlist has no channels")
    wanted = {c["id"] for c in channels if c["id"]}

    root = ET.Element("tv", {"generator-info-name": "iptv-curated lume build"})
    for channel in channels:
        node = ET.SubElement(root, "channel", {"id": channel["id"]})
        ET.SubElement(node, "display-name", {"lang": "en"}).text = channel["name"]
        if channel["logo"]:
            ET.SubElement(node, "icon", {"src": channel["logo"]})

    programmes = 0
    for source_url, mapping in ((FR_SOURCE, FR_MAP), (US_SOURCE, US_MAP)):
        elements, counts = build(source_url, mapping, wanted)
        for element in elements:
            if not keep_icons:
                for icon in element.findall("icon"):
                    element.remove(icon)
            root.append(element)
            programmes += 1
        print(f"  {os.path.basename(source_url)}: {sum(counts.values())} programmes, {len(counts)} channels")

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output.write_bytes(gzip.compress(xml, compresslevel=9, mtime=0))
    return len(channels), programmes, len(wanted)


def validate(output: Path, playlist: Path) -> None:
    ids = {c["id"] for c in parse_playlist(playlist)}
    with gzip.open(output, "rb") as handle:
        text = handle.read().decode("utf-8", "replace")
    present = set(re.findall(r'<channel id="([^"]+)"', text))
    missing = sorted(ids - present)
    if missing:
        raise RuntimeError(f"guide is missing channels: {missing}")
    programmes = len(re.findall(r"<programme ", text))
    if programmes < 500:
        raise RuntimeError(f"guide looks truncated: {programmes} programmes")
    stamps = re.findall(r'start="(\d{8})', text)
    if stamps:
        latest = max(stamps)
        age = (datetime.now(timezone.utc) - datetime.strptime(latest, "%Y%m%d").replace(tzinfo=timezone.utc)).days
        if age > 2:
            raise RuntimeError(f"guide window ends {latest}, {age} day(s) behind today")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", type=Path, default=PLAYLIST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--no-icons", action="store_true")
    args = parser.parse_args()

    channels, programmes, _ = build_guide(args.playlist, args.output, keep_icons=not args.no_icons)
    validate(args.output, args.playlist)
    print(
        f"EPG_READY\tchannels={channels}; programmes={programmes}; "
        f"generated={datetime.now(timezone.utc).isoformat()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
