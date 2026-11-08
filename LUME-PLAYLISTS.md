# Lume playlists (France / Algérie / USA)

Three ready-to-import playlists for **Lume** (App Store `6779551584`), one per
country. They live at the repo root and are served by GitHub Pages:

| Playlist  | URL                                                                   | Channels |
|-----------|-----------------------------------------------------------------------|----------|
| France    | `https://adamshl-oss.github.io/iptv-curated/lume-france.m3u`         | 23       |
| Algérie   | `https://adamshl-oss.github.io/iptv-curated/lume-algeria.m3u`        | 16       |
| USA       | `https://adamshl-oss.github.io/iptv-curated/lume-usa.m3u`            | 30       |
| **Chaines TV** (all three combined) | `https://adamshl-oss.github.io/iptv-curated/lume-chaines-tv.m3u` | 69 |
| EPG       | `https://adamshl-oss.github.io/iptv-curated/lume-epg.xml.gz`          | 69 ch.   |

Total: **69 channels**, every one verified by real playback.

## Import into Lume

Lume's add-playlist form takes the playlist URL and the guide URL separately:

* Playlist URL → `lume-france.m3u` / `lume-algeria.m3u` / `lume-usa.m3u`, or
  `lume-chaines-tv.m3u` for all three at once
* EPG URL → `lume-epg.xml.gz`

Each playlist carries `url-tvg="…/lume-epg.xml.gz"` on the `#EXTM3U` line as well,
so players that read it from the manifest alone still resolve the guide.

> Lume's free tier is limited to one playlist. Three playlists needs **Lume Pro**
> ($9.99, one-time — not a subscription).

### "Chaines TV" — the combined playlist

`lume-chaines-tv.m3u` is the same **69 channels** as the three country playlists,
concatenated into one file, so the free tier covers everything:

* built from the three published files by `scripts/build_lume_chaines_tv.py`
* `tvg-chno` renumbered `1..69` so ordering is unambiguous across countries;
  `tvg-id` is untouched, so the one shared EPG still matches every channel
* `group-title` is untouched — the categories stay country-prefixed
  (`France — Général`, `Algérie — Public`, `USA — Info`, …)
* verified at build time: 69 channels, 69 unique `tvg-id`s, 69 unique stream
  URLs, and every `tvg-id` resolves in `lume-epg.xml.gz`
* **no channel was added, dropped or substituted** — it is a union, not a new mix

Use it if you would rather not buy Lume Pro; buy Pro only if you want the three
country playlists side by side in the app.

## Content policy — no Spanish-language channels in the USA playlist

The USA playlist contains **no Spanish-language channels**: no Telemundo,
Univision, UniMás, Canal Uno, América Te Ve, NuvoTV, LATV, Entravision,
Bandorama, Pdia, TUDN, ESPN Deportes, Fox Deportes or V-me. This is a standing
requirement, not a sourcing accident.

It is enforced at build time: the playlist generator aborts before writing any
file when a USA channel matches an excluded id or a Spanish-language marker
token, so a candidate can never slip in through a later import. The result is
reported in `lume-manifest.json` under `policy_checks.usa_no_spanish_channels`,
and the excluded list is published under `excluded_by_policy.USA`.

The rule also applies to the *feeds*, not just the channel names. A full
frame-by-frame audit of every USA entry showed that several feeds carried the
**Latin-American** edition of a US brand — Discovery Channel, Investigation
Discovery, National Geographic and History were all serving the Spanish (or
Portuguese) version with burned-in subtitles. Those feeds were removed and the
channels are listed under `unsourced_targets` with the reason. Discovery
Channel, Investigation Discovery and History have no free English linear feed at
all (TV-provider gated); National Geographic was replaced with the English feed.

## What the playlists look like

* `group-title` → Lume renders it as a category rail, so one playlist shows
  `France — Général`, `France — Info`, `France — Régions`, `Algérie — Public`,
  `Algérie — Religieux`, `USA — Info`, `USA — Généraliste`, `USA — Sport`,
  `USA — Cinéma & séries`, `USA — Documentaire`, … as separate sections.
* `tvg-id` → matches the channel ids in `lume-epg.xml.gz`.
* `tvg-logo` → channel logo from the iptv-org logo registry, Wikimedia
  Commons, or the broadcaster's own site.
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
when it carries real sound and not a silent track. Segments are downloaded
whole and decrypted where the CDN uses AES-128, so a silent or encrypted track
cannot pass as "audible".

**H.264 only.** All published renditions are H.264 (`avc1`). Some feeds are
served as **HEVC-only** variants; AVFoundation can silently fall back to an
*audio-only* rendition on HEVC, which looks like a working channel to a
transport check but shows no picture. Those are never published.

The codec check is also how **Euronews** was moved: the feed it used first was a
legacy SD **MPEG-2** rendition, so it was replaced with Euronews's own Akamai
feed (`cdn-euronews.akamaized.net`), which serves H.264/AAC up to 720p. All 69
published channels are H.264 video.

**Identity from the picture, not from the label.** Every published channel's
on-screen logo was read from a decoded frame, and the channel name in the
playlist is the name that frame actually shows. Several corrections came out of
that check and are recorded in `lume-manifest.json` → `identity_notes`.

**A full identity audit was run over every channel in all three playlists** —
frames were decoded from the published URLs and read. It found, and fixed:

| Published as | What the picture actually showed | Action |
|--------------|----------------------------------|--------|
| History (USA) | Comedy Central programming + the Comedy Central ident | republished as **Comedy Central** |
| CNBC (USA) | CNBC **Asia** (Asia index ticker) / unbranded footage | removed — listed under `unsourced_targets` |
| CNN International (USA) | Comedy Central content | removed |
| ABC News (USA) | unidentified lifestyle footage (Tubi) / a documentary film with no ABC branding (Disney CDN) | removed |
| Discovery Channel (USA) | Discovery Channel **Latin America** — Spanish subtitles | removed (policy) |
| Investigation Discovery (USA) | ID **Latin America** — Portuguese | removed (policy) |
| National Geographic (USA) | Nat Geo **Latin America** — Spanish | replaced with the English feed |
| El Bilad TV (Algérie) | Al Ghad TV | renamed to **Al Ghad TV** |
| France 3 (France) | France 3 **Bretagne** | split into France 3 + France 3 Bretagne |
| D17 (France) | CStar content on both farm paths | removed |
| Ikhtyar TV (Algérie) | stream 404 | removed |

Where a brand has several regional editions, the playlist now names the feed
that is actually on air — e.g. **KIRO 9 (CBS Seattle)**, **ABC 6 (Phoenix)** and
**NBC News NOW (Bay Area)** are local affiliates taken from the station's own
publisher stream, and the national feeds are published separately.

The captured build evidence (segment URL, byte counts, and a decoded frame per
channel) is in `lume-manifest.json` under `channels[]`.

> The Apple-stack checks run on this Mac, not on Apple TV hardware. They prove
> the streams decode with real picture and sound through AVFoundation/AVPlayer
> and play smoothly for 60 s; they are not a substitute for confirming output
> on the television itself.

Source tiers used for ranking:

| Tier | Meaning |
|------|---------|
| 1 | first-party broadcaster CDN (`ar.ycncdn.online`, `fl-dvr.iptvcdn.tv`, `live.france24.com`, `cdn.live.easybroadcast.io`, `akamaized.net`, `cloudfront.net`, `nextradiotv.com`, `6cloud.fr`, `uplynk.com`, `bloomberg.com`, `mediatailor…amazonaws.com`, `amagi.tv`, `streaming.onnethn.com`, `airspace-cdn.cbsivideo.com`) |
| 2 | the project's own relay (`algerian-tv-relay-2026.espiiem.chatgpt.site`) |
| 3 | public repository / CDN mirror (ParaTV, raw.githubusercontent) |
| 4 | third-party stream farm |

Nothing in these playlists depends on a machine in the house — every URL is
served from the public internet, so the Mac can stay off.

## Targets that could not be sourced

These are **not** substituted with something else. They stay listed, so the gap
is visible instead of silent (see `lume-manifest.json` → `unsourced_targets`).

* **Algérie** — Samira TV (rank 1), TV5/Coran, TV9 El Barlamaniya,
  El Hayat TV, Beur TV, Bahia TV, El Fadjer TV, El Watania TV, Zahra TV,
  Al Anis TV, Al Magharibia, Ennahar Laki, Echorouk Benna, El Bilad TV,
  Ikhtyar TV.
  * The official broadcaster CDN `cdn.hta.dz` — which carries Samira TV, TV5,
    TV6, TV8, TV9, El Heddaf, El Hayat, Beur, Bahia, El Bilad, Echorouk,
    Ennahar — has **dead nameservers** and does not resolve globally. The
    channel paths (`/abr_htatv/<NAME>/playlist.m3u8`) are still published by
    the broadcaster, so those channels come back as soon as the DNS zone is
    restored.
  * `live.elheddaftv.com` answers 404 on the stale path; the correct path
    (`/elheddaftvlive/playlist.m3u8`) works and **El Heddaf TV is published**.
  * The relay's El Heddaf upstream answers 503 "all sources unavailable".
  * The Algerian relay/CDN tenant exposes codes for TV1, TV2, TV3, TV4, TV6,
    TV7, TV8, Canal Algérie, Echorouk News, Ennahar and Al Ghad, all of which
    are published here. The tenant has **no code for TV5 or TV9**, and the
    remaining live codes carry international channels, so they are not
    published under guessed names.
* **USA** — The CW (national) and C-SPAN: both networks keep their 24/7 feeds
  behind TV-provider authentication. The free CW-branded FAST channel
  (**CW Forever**) and **NASA TV** are published instead. The CW national feed
  runs on Brightcove with a freewheel ad layer, and C-SPAN's networks are
  "reserved for cable and satellite TV customers"; their public live-event
  HLS manifests rotate per event and are not stable channel URLs.

  Also unsourced, after the identity audit:

  * **Discovery Channel**, **Investigation Discovery**, **History** — the only
    reachable feeds are the Latin-American (Spanish/Portuguese) editions, which
    the no-Spanish rule excludes; the US linear feeds are TV-provider gated.
  * **CNBC** — the reachable feeds carry CNBC Asia or unbranded footage; the US
    feed is subscription-gated.
  * **CNN International** — the reachable feed carries Comedy Central content.
  * **ABC News** — the Tubi feed carries unidentified lifestyle content, and
    Disney's own `ABCNewsLive` Akamai manifest runs documentary programming with
    no ABC branding on screen, so neither can be published as "ABC News".

  Replacements that were found and published instead: **CBS News 24/7** (CBS's
  own `airspace-cdn` newsroom CDN), **BBC News**, **HGTV**, **FOX** (the
  broadcast network, not Fox News) and **National Geographic** (English).
* **France** — Canal+ (pay/DRM, out of scope by policy); D17 (every farm path
  serves CStar content instead of D17). **France 3 national**, **France 3
  Bretagne** (a France 3 Régions feed), **France 24** and **Euronews** are all
  published.

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
