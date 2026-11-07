# Lume playlists (France / Algérie / USA)

Three ready-to-import playlists for **Lume** (App Store `6779551584`), one per
country. They live at the repo root and are served by GitHub Pages:

| Playlist  | URL                                                                   | Channels |
|-----------|-----------------------------------------------------------------------|----------|
| France    | `https://adamshl-oss.github.io/iptv-curated/lume-france.m3u`         | 21       |
| Algérie   | `https://adamshl-oss.github.io/iptv-curated/lume-algeria.m3u`        | 14       |
| USA       | `https://adamshl-oss.github.io/iptv-curated/lume-usa.m3u`            | 26       |
| EPG       | `https://adamshl-oss.github.io/iptv-curated/lume-epg.xml.gz`          | 61 ch.   |

Total: **61 channels**, every one verified by real playback.

## Import into Lume

Lume's add-playlist form takes the playlist URL and the guide URL separately:

* Playlist URL → `lume-france.m3u` / `lume-algeria.m3u` / `lume-usa.m3u`
* EPG URL → `lume-epg.xml.gz`

Each playlist carries `url-tvg="…/lume-epg.xml.gz"` on the `#EXTM3U` line as well,
so players that read it from the manifest alone still resolve the guide.

> Lume's free tier is limited to one playlist. Three playlists needs **Lume Pro**
> ($9.99, one-time — not a subscription).

## What the playlists look like

* `group-title` → Lume renders it as a category rail, so one playlist shows
  `France — Général`, `France — Info`, `France — Kids`, `Algérie — Public`,
  `USA — Broadcast`, `USA — Sport`, … as separate sections.
* `tvg-id` → matches the channel ids in `lume-epg.xml.gz`.
* `tvg-logo` → channel logo from the iptv-org logo registry.
* No `catchup` attributes are published: none of the selected sources expose a
  usable catch-up/archive window, so advertising one would be a lie.

## Verification standard

Every channel in these files was **tested, never sampled**, and tested at three
independent layers.

**1. Transport.** The HLS master is resolved to a variant playlist, an actual
media segment is fetched, and it must answer HTTP 200 with more than 512 bytes
of MPEG-TS. A URL that answers 200 with a playlist instead of media, or that
carries a geo-block marker, is rejected.

**2. Apple stack.** Every published URL is loaded with **AVFoundation** — the
same framework tvOS uses — and its real media tracks are inspected: video
resolution / fps / bitrate, and audio sample rate / channel count. A separate
**AVPlayer** run then plays the stream for 60 seconds under the strict policy in
`scripts/stream_health_policy.json` (≤12 s startup, ≥92 % advancing time,
≤5 s total stall, ≤3 s longest stall, ≤3 stall events). This is the test that
answers "will it actually watch without lagging".

**3. Audible content.** Every URL is decoded for 10 seconds with ffmpeg and the
decoded audio is measured with `volumedetect`, so a channel is only accepted
when it carries real sound and not a silent track.

**H.264 only.** All published renditions are H.264 (`avc1`). Three feeds
(ABC News, Discovery Channel, National Geographic) were originally served as
**HEVC-only** variants; AVFoundation can silently fall back to an *audio-only*
rendition on HEVC, which looks like a working channel to a transport check but
shows no picture. Those three now point at H.264 renditions that AVFoundation
confirms carry both a video track and an audio track.

The captured build evidence (segment URL, byte counts, and a decoded frame per
channel) is in `lume-manifest.json` under `channels[]`.

> The Apple-stack checks run on this Mac, not on Apple TV hardware. They prove
> the streams decode with real picture and sound through AVFoundation/AVPlayer
> and play smoothly for 60 s; they are not a substitute for confirming output
> on the television itself.

Source tiers used for ranking:

| Tier | Meaning |
|------|---------|
| 1 | first-party broadcaster CDN (`ar.ycncdn.online`, `fl-dvr.iptvcdn.tv`, `cdn.live.easybroadcast.io`, `akamaized.net`, `cloudfront.net`, `nextradiotv.com`, `6cloud.fr`, `uplynk.com`, `bloomberg.com`) |
| 2 | the project's own relay (`algerian-tv-relay-2026.espiiem.chatgpt.site`) |
| 3 | public repository / CDN mirror (ParaTV, raw.githubusercontent) |
| 4 | third-party stream farm |

Nothing in these playlists depends on a machine in the house — every URL is
served from the public internet, so the Mac can stay off.

## Targets that could not be sourced

These are **not** substituted with something else. They stay listed, so the gap
is visible instead of silent (see `lume-manifest.json` → `unsourced_targets`).

* **Algérie** — Samira TV (rank 1), El Heddaf TV, TV5/Coran, TV6, TV8, TV9,
  El Hayat TV, Beur TV, Bahia TV, El Fadjer TV, El Watania TV, Zahra TV,
  Al Anis TV, Al Magharibia, Ennahar Laki, Echorouk Benna.
  * The official broadcaster CDN `cdn02.hta.dz` (which carries Samira TV, TV6,
    TV8, TV9, El Heddaf, El Hayat, Beur, Bahia, …) is **NXDOMAIN globally** —
    it resolves neither from the local network nor via DNS-over-HTTPS.
  * `live.elheddaftv.com` answers 404; the relay's El Heddaf upstream answers
    503 with "all sources unavailable".
  * The Algerian relay/CDN tenant exposes codes for TV1, TV3, TV4, TV5, TV7,
    El Bilad, Echorouk News and Ennahar, all of which are published here. The
    remaining live tenant codes carry the EPTV national simulcast and cannot
    be attributed to TV6/TV8/TV9 by content, so they are not published under
    guessed names.
* **USA** — The CW, C-SPAN, NASA TV (no usable iptv-org stream); USA Network,
  Lifetime, Bravo and TNT (every candidate either stalled or failed under
  AVPlayer); Telemundo and Univision (candidate streams failed playback).
* **France** — Canal+ (pay/DRM, out of scope by policy); France 3 Régions (the
  only source that carries it stalls under AVPlayer).

## Guide coverage

* France → epgshare FR1
* USA → epgshare US2
* Algérie → **no public XMLTV guide for Algeria exists** at the time of writing.
  The Algerian channels are emitted in the guide with their id, display name and
  logo, but without programme data. They still play; they just have no EPG.

## Relationship to the IPTVX releases

`iptvx.m3u` and `chaines-tv.m3u` remain the client-facing IPTVX releases and
are untouched by this work. These `lume-*.m3u` files are a separate,
three-playlist build for Lume, so they are not affected by the IPTVX promotion
workflow, and `lume-epg.xml.gz` is published separately from `epg.xml.gz` so the
nightly `refresh-epg.yml` job cannot overwrite it.
