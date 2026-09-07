#!/usr/bin/env python3
"""Build a compact, identity-aligned XMLTV guide for the French lineup."""

from __future__ import annotations

import argparse
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz"
OUTPUT = ROOT / "epg.xml.gz"
SOURCE_TO_TARGET = {
    "TF1.fr": "TF1.fr",
    "CNews.fr": "CNews.fr",
    "Arte.fr": "ARTE.fr",
    "TMC.fr": "TMC.fr",
    "BFM.TV.fr": "BFMTV.fr",
    "LCI.fr": "LCI.fr",
    "TFX.fr": "TFX.fr",
    "RMC.Découverte.fr": "RMCDecouverte.fr",
    "RMC.Story.fr": "RMCStory.fr",
    "TF1.Séries.Films.fr": "TF1SeriesFilms.fr",
    "L'Equipe.fr": "LEquipe.fr",
    "CStar.fr": "CStar.fr",
}


def input_stream(source: str):
    if source.startswith("https://"):
        response = urlopen(Request(source, headers={"User-Agent": "iptvx-epg/1.0"}), timeout=60)
        return gzip.GzipFile(fileobj=response)
    path = Path(source)
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def build(source: str, output: Path) -> tuple[int, int]:
    root = ET.Element("tv", {
        "generator-info-name": "IPTVX curated EPG",
        "source-info-url": SOURCE,
    })
    seen_channels: set[str] = set()
    programmes = 0
    with input_stream(source) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == "channel":
                target = SOURCE_TO_TARGET.get(element.get("id", ""))
                if target and target not in seen_channels:
                    element.set("id", target)
                    root.append(element)
                    seen_channels.add(target)
                else:
                    element.clear()
            elif element.tag == "programme":
                target = SOURCE_TO_TARGET.get(element.get("channel", ""))
                if target:
                    element.set("channel", target)
                    root.append(element)
                    programmes += 1
                else:
                    element.clear()
    if len(seen_channels) < 8 or programmes < 40:
        raise RuntimeError(
            f"EPG source incomplete: {len(seen_channels)} channels, {programmes} programmes"
        )
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output.write_bytes(gzip.compress(xml, compresslevel=9, mtime=0))
    return len(seen_channels), programmes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    channels, programmes = build(args.source, args.output)
    print(
        f"EPG_READY\tchannels={channels}; programmes={programmes}; "
        f"generated={datetime.now(timezone.utc).isoformat()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
