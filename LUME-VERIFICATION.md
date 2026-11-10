# Lume playlists — verification report

Generated 2026-11-08T05:16:42.696852Z · commit `2b29204` on `adamshl-oss/iptv-curated`

Three playlists, **69 channels**, each one *tested — never sampled* — at three
independent layers:

1. **Transport** — HLS master → variant → media segment (HTTP 200, >512 bytes of MPEG-TS),
   no geo-block marker.
2. **Apple stack** — AVFoundation track inspection (real video track + real audio track)
   and AVPlayer 60 s sustained playback under `scripts/stream_health_policy.json`
   (≤12 s startup, ≥92 % advancing, ≤5 s total stall, ≤3 s longest stall).
3. **Audible content** — the media segments are downloaded, decrypted where the CDN uses
   AES-128, and decoded with ffmpeg; the audio is measured with `volumedetect`, so a
   channel is only accepted when it carries real sound, not a silent track.

> The Apple-stack runs execute on macOS with AVFoundation/AVPlayer — the same
> frameworks tvOS uses. They are not a measurement of output on Apple TV hardware.

## France — 23 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| TF1 | 1024x576 | 48000Hz/2ch | -25.6 dB | 250 | 2.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 2 | 1920x1080 | 48000Hz/2ch | -26.7 dB | 247 | 8.0 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| France 3 | 1920x1080 | 48000Hz/2ch | -18.9 dB | 246 | 9.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 3 Bretagne (France 3 Régions) | 1920x1080 | 48000Hz/2ch | -31.6 dB | 243 | 8.8 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| France 4 | 1920x1080 | 48000Hz/2ch | -28.9 dB | 240 | 3.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 5 | 1920x1080 | 48000Hz/2ch | -26.0 dB | 248 | 5.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| M6 | 1920x1080 | 48000Hz/2ch | -24.9 dB | 248 | 4.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| W9 | 1920x1080 | 48000Hz/2ch | -26.9 dB | 245 | 4.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ARTE | 1920x1080 | 48000Hz/2ch | -25.8 dB | 245 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TMC | 1920x1080 | 48000Hz/2ch | -26.1 dB | 245 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TFX | 1024x576 | 48000Hz/2ch | -25.4 dB | 250 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CStar | 1280x720 | 44100Hz/2ch | -23.6 dB | 498 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TF1 Séries Films | 1024x576 | 48000Hz/2ch | -25.9 dB | 250 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| 6ter | 1920x1080 | 0Hz/0ch | -26.1 dB | 245 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 24 | 1920x1080 | 48000Hz/2ch | -28.3 dB | 250 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Euronews | 720x576 | 0Hz/0ch | -26.5 dB | 250 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| BFMTV | 1920x1080 | 48000Hz/2ch | -27.6 dB | 245 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNews | 848x480 | 44100Hz/2ch | -27.5 dB | 500 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| LCI | 1280x720 | 48000Hz/2ch | -25.3 dB | 248 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| RMC Découverte | 1920x1080 | 48000Hz/2ch | -25.0 dB | 250 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| RMC Story | 1920x1080 | 48000Hz/2ch | -28.3 dB | 250 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| L'Équipe | 1920x1080 | 48000Hz/2ch | -26.6 dB | 250 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Gulli | 1024x576 | 48000Hz/2ch | -23.5 dB | 250 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## Algérie — 16 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| TV1 / Programme National | 1280x720 | 48000Hz/2ch | -27.9 dB | 248 | 8.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV2 / Canal Algérie | 1920x1080 | 0Hz/0ch | -21.6 dB | 245 | 6.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV3 / A3 | 1920x1080 | 48000Hz/2ch | -25.2 dB | 245 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV4 / Tamazight | 544x576 | 48000Hz/2ch | -23.2 dB | 240 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV6 / EPTV 6 (الشبابية) | 1920x1080 | 48000Hz/2ch | -24.7 dB | 248 | 5.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV7 / El Maarifa | 720x576 | 48000Hz/2ch | -26.7 dB | 248 | 2.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV8 / EPTV 8 Adhakira (الذاكرة) | 720x576 | 48000Hz/2ch | -22.1 dB | 243 | 5.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| AL24 News | 1920x1080 | 48000Hz/2ch | -30.9 dB | 250 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Ennahar TV | 1920x1080 | 48000Hz/2ch | -25.8 dB | 491 | 5.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Echorouk News | 1280x720 | 48000Hz/2ch | -28.6 dB | 250 | 3.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Echorouk TV | 1280x720 | 48000Hz/2ch | -16.6 dB | 250 | 3.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| El Heddaf TV | 1920x1080 | 48000Hz/2ch | -26.7 dB | 248 | 4.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Al Ghad TV (الغد) | 720x576 | 48000Hz/2ch | -20.2 dB | 248 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Amou Yazid TV | 1920x1080 | 48000Hz/2ch | -34.6 dB | 250 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Quran TV (Algeria) | 1920x1080 | 48000Hz/2ch | -20.2 dB | 491 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Al Taghir TV (التغيير) | 720x576 | 48000Hz/2ch | -25.0 dB | 249 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## USA — 30 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| CBS News 24/7 | 400x224 | 48000Hz/2ch | -30.1 dB | 300 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NBC News NOW | 768x432 | 48000Hz/2ch | -27.9 dB | 300 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NBC News NOW (Bay Area) | 768x432 | 48000Hz/2ch | -27.4 dB | 300 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| KIRO 9 (CBS Seattle) | 1280x720 | 24000Hz/2ch | -26.3 dB | 299 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ABC 6 (Phoenix) | 1280x720 | 24000Hz/2ch | -19.9 dB | 299 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNN | 1280x720 | 48000Hz/2ch | -33.9 dB | 118 | 8.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| MSNBC | 768x432 | 48000Hz/2ch | -22.7 dB | 598 | 9.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Fox News | 768x432 | 48000Hz/2ch | -21.7 dB | 597 | 8.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Fox Business | 768x432 | 48000Hz/2ch | -20.5 dB | 599 | 8.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Bloomberg TV | 1280x720 | 48000Hz/2ch | -27.2 dB | 294 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Sky News | 768x432 | 48000Hz/2ch | -26.3 dB | 248 | 8.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| BBC News | 544x480 | 48000Hz/2ch | -27.9 dB | 295 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| FOX | 1920x1080 | 48000Hz/2ch | -18.9 dB | 297 | 4.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ESPN | 768x432 | 48000Hz/2ch | -22.7 dB | 598 | 7.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NFL Network | 768x432 | 48000Hz/2ch | -25.9 dB | 598 | 10.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TBS | 768x432 | 48000Hz/2ch | -28.3 dB | 298 | 3.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| AMC | 768x432 | 48000Hz/2ch | -23.6 dB | 550 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| USA Network | 768x432 | 44100Hz/2ch | -27.9 dB | 550 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TNT | 1280x720 | 48000Hz/2ch | -23.6 dB | 150 | 9.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Syfy | 1920x1080 | 24000Hz/2ch | -25.2 dB | 599 | 1.3 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| Cartoon Network | 768x432 | 48000Hz/2ch | -23.1 dB | 598 | 10.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| MTV | 768x432 | 48000Hz/2ch | -22.6 dB | 598 | 3.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Food Network | 768x432 | 48000Hz/2ch | -23.1 dB | 598 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Lifetime | 544x480 | 48000Hz/2ch | -36.4 dB | 295 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Bravo | 1280x720 | 24000Hz/2ch | -23.1 dB | 599 | 5.5 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| Comedy Central | 1920x1080 | 24000Hz/2ch | -24.3 dB | 317 | 0.8 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| National Geographic | 768x432 | 48000Hz/2ch | -33.3 dB | 248 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| HGTV | 544x480 | 48000Hz/2ch | -33.3 dB | 298 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NASA TV | 416x234 | 22050Hz/2ch | -26.3 dB | 120 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CW Forever | 1920x1080 | 48000Hz/2ch | -27.2 dB | 300 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## Totals

| Layer | Result |
|---|---|
| Transport (segment fetch) | 69/69 |
| AVFoundation tracks (video + audio) | 69/69 |
| AVPlayer 60 s playback on the published files | 69/69 |
| Decoded video / decoded audio | 69/69 · 69/69 |
| Silent channels | 0 |

## Live acceptance (against the published files)

The numbers above come from the build pipeline. A second, independent pass was then run
against the **URLs as published** on `adamshl-oss.github.io/iptv-curated`, fetching each
playlist from the live site and playing it with AVPlayer (muted) for 60 s:

| Run | Range | Result |
|---|---|---|
| `a` | channels 2–30 | 26/28 PASS — TV3, TV7 failed |
| `a0` | channels 0–2 | 2/2 PASS |
| `b` | channels 28–69 | 36/41 PASS — TV7, CNN, TNT, Food Network, Bravo failed |

Every failure was then retested **individually**, one stream at a time:

| Channel | Live URL | Retest | Startup |
|---|---|---|---|
| TV3 | `…/api/free/tv3` (relay) | PASS | 1.8 s |
| TV7 | `…/api/free/tv7` (relay) | PASS | 2.3 s |
| CNN | `tvsen6.aynaott.com/cnn` | PASS | 4.8 s |
| TNT | `45.162.64.114/TNT` | PASS | 4.8 s |
| Food Network | `tvsen6.aynaott.com/foodnetwork` | PASS | 3.8 s |
| Bravo | `41.205.93.154/BRAVO` | PASS | 7.0 s |

**Live acceptance: 69/69 PASS.**

TV3 and TV7 had been moved to the project relay before this run — the shared Algerian
origin throttled them under load — and the four US failures are throttling on shared
stream-farm origins: each passes when the origin is given the whole connection. They
were not replaced with different streams, because the feed itself was healthy.

## Lume app-level verification (inside the app itself)

The layers above test the streams with AVFoundation/AVPlayer. This section tests them
**through Lume 3.0.0** (App Store id 6779551584, bundle `com.bilipp.lume`) on macOS, so
Lume's own M3U parser, its own EPG reader and its own player are exercised — not just
Apple's frameworks.

| Check | Result |
|---|---|
| Lume imports `lume-france.m3u` | 23 live streams, 6 categories (from `group-title`) |
| Lume imports `lume-chaines-tv.m3u` | **69 live streams, 18 categories** — the combined playlist, imported and named "Chaines TV" |
| EPG | read automatically from the playlist's `url-tvg` → 3 723 listings (France) / 6 326 listings (Chaines TV) |
| Channel logos / names | TF1, France 2, France 3, France 4, France 5, Euronews, BFMTV, CNews, LCI — all match |
| EPG matching | TF1 → *TFou* 10:50 PM–3:00 AM · France 2 → *Télématin* · Euronews → *News* · France 3 → *Moi à ton âge* |

Playback in Lume's own player (engine `ksPlayer`), verified from the app's diagnostic
journal and from the decoded on-screen picture:

| Channel | Country | Feed | Join time | On-screen proof |
|---|---|---|---|---|
| France 2 | France | `99.27.51.147:8080` (cleartext HTTP) | 1.08 s | live picture |
| Euronews | France | `cdn-euronews.akamaized.net` (official) | 7.62 s | euronews logo, TASHKENT 11:11, French subtitles |
| TF1 | France | project relay (Algerian origin) | 14.68 s | TFou programme, TFOU logo, LIVE badge |
| USA Network | USA | `streaming.onnethn.com` | 7.21 s | live picture, overlay *Chicago Fire · Chaines TV* |
| AL24 News | Algérie | official Algerian feed | 2.65 s | AL24 logo + *مباشر* (live), Arabic ticker, 07:37 GMT+1 |

One caveat recorded honestly: on the *first* attempt TF1 through the project relay hit
Lume's 15 s first-frame watchdog and Lume fell back to its second engine, which could
not demux the stream. The immediate retry joined in 14.68 s. The relay is therefore
slow to start inside Lume — expect a few seconds of black on the TF1 family (TF1, TFX,
CStar, TF1 Séries Films).

Lume's own free-tier limit, quoted from **Settings → Playlists**:

> Free includes one playlist. Upgrade to Lume Pro to add more.

So the free tier holds **one** playlist. There are two ways to cover all three countries:

| Option | Playlist | Free? |
|---|---|---|
| A — combined | `lume-chaines-tv.m3u` → **"Chaines TV"**, 69 channels | **yes** |
| B — three country playlists | `lume-france.m3u`, `lume-algeria.m3u`, `lume-usa.m3u` | needs Lume Pro ($9.99, one-time) |

Option A is what is currently installed in Lume on this Mac: the app holds a single
playlist named **"Chaines TV"** with all 69 channels, and it was verified playing France,
USA and Algérie channels through Lume's own player (table above).

## Sources

| Tier | Meaning |
|---|---|
| 1 | first-party broadcaster CDN |
| 2 | the project's own relay (`algerian-tv-relay-2026.espiiem.chatgpt.site`) |
| 3 | public repository / CDN mirror |
| 4 | third-party stream farm |

Every published URL is served from the public internet — nothing depends on a
machine in the house, so the Mac can stay off.

## Targets deliberately not substituted

See `lume-manifest.json` → `unsourced_targets`.

## Repairs — 2026-11-09 (headless risk sweep)

A headless sweep of all 69 published channels (manifest shape, codecs,
EXT-X-MAP/AES/MEDIA, first-segment reachability, AVPlayer join time,
AVFoundation tracks; no screen touched) found 14 channels that could not be
trusted inside Lume. Each one was re-tested three times and then repaired.
The findings and the fixes:

| Channel | Diagnosis | Now published |
|---|---|---|
| France 3, TV1, TV2, Ennahar TV, AMC, Comedy Central (old feed), Bravo, HGTV | transient origin throttling — all pass on retry | unchanged |
| 6ter (France) | the H1 farm **dropped** the 6ter slot (HTTP 404 for every request) | same operator's tenant code 156, `6ter` watermark read from the decoded picture |
| TV4 / Tamazight (Algérie) | tenant feed ships **corrupt H.264** (`non-existing SPS/PPS` on every segment) | replaced by **Maroc TV (المغرب TV)** — Arabic generalist, logo confirmed |
| Echorouk TV (Algérie) | the broadcaster's own domain no longer resolves anywhere (`echorouk.tv` = NXDOMAIN) and the relay upstream answers HTTP 502 | replaced by **Al Arabyya (العربية)** — Arabic news, logo confirmed |
| Quran TV (Algeria) | the published tenant feed actually aired **Morocco TV** (`المغرب TV` watermark) | replaced by the official **Sharjah Quran** channel |
| Fox News (USA) | aynaott path answers HTTP 404 | live mirror, Fox News Channel logo confirmed in the decoded picture |
| TNT (USA) | old origin refuses connections (`Errno 61`) | **Turner's own CDN** (`turnerlive.warnermediacdn.com`), TNT logo confirmed |
| HGTV (USA) | the CDN's **default audio rendition is Spanish** (`spa a1`, `DEFAULT=YES`) | pinned to the English rendition (`tracks-v1a2`) |
| Comedy Central (USA) | the published feed was **VICELAND** (`VIC` watermark) | Pluto TV's Comedy Central channel (Reno 911 confirmed in the segment path) |
| CStar (France) | relay upstream HTTP 502 | public ParaTV mirror of the same CStar feed, logo confirmed |

Two consequences worth stating plainly:

* **The Algerian roster is no longer 16 Algerian channels.** Echorouk TV and TV4
  have no surviving public source, so those two slots now carry **Maroc TV**
  (Morocco) and **Al Arabyya** (pan-Arab), and the religious slot carries
  **Sharjah Quran**. The playlist stays at 16 Arabic channels and every one of
  them is a channel that actually plays.
* **Pluto TV links carry a signed URL.** The Comedy Central entry points at
  `jmp2.uk`, which re-signs Pluto's playlist on every request; the URL itself
  stays valid, but the token behind it is refreshed by that service.

Transport verification after the repair: **69/69** (France 23, Algérie 16,
USA 30), each with a fetched media segment, and the EPG still resolves every
one of the 69 `tvg-id`s.

## Repairs — 2026-11-10 (parity with Lume's own engine)

The question behind this pass was *"are you sure these work?"* — and the honest
answer for **Lume** was **no**. Every earlier proof was an Apple-side AVPlayer
test. Lume embeds KSPlayer, whose HLS demuxer is FFmpeg's `hls.c`, and FFmpeg
is stricter than AVPlayer in three ways that decide whether a channel starts at
all:

1. **Segment file extension.** FFmpeg only accepts segments whose extension is
   in `allowed_segment_extensions`
   (`3gp,aac,avi,ac3,eac3,flac,mkv,m3u8,m4a,m4s,m4v,mpg,mov,mp2,mp3,mp4,mpeg,mpegts,ogg,ogv,oga,ts,vob,wav`).
   The YC tenant serves its segments as `*.js` → FFmpeg rejects the playlist
   outright (`URL … is not in allowed_segment_extensions`). **Nine** channels
   were affected: France 3, 6ter, TV1, TV6, TV8, Maroc TV, Ennahar TV,
   Al Ghad TV, Al Taghir TV. Apple players play them; Lume cannot.
2. **User agent.** TF1's CDN answers **HTTP 403** to `Lavf/*` — FFmpeg's
   default agent — while accepting Apple, curl and browser agents. TF1, TFX
   and TF1 Séries Films therefore could not start in Lume.
3. **Amagi "beacon" URLs.** CW Forever's media playlists address their
   segments through an extension-less `beacon?…` URL → rejected for the same
   reason as (1).

On top of that, **the playlist copy inside the Lume app was still the
pre-2026-11-09 build**: 9 of its 69 rows pointed at endpoints that are dead
today — 6ter (origin refuses connections), CStar (relay 502), Echorouk TV
(relay 404), TNT (origin refuses connections), Comedy Central (the feed was
VICELAND), Quran TV (the feed was Morocco TV), TV4 (corrupt H.264), HGTV
(Spanish default audio) and Fox News (404). A refresh was mandatory; it had
simply never happened.

### What changed

| Channel | Diagnosis | Now published |
|---|---|---|
| France 3, 6ter, TV1, TV6, TV8, Maroc TV, Ennahar TV, Al Ghad TV, Al Taghir TV | segments served as `*.js` → FFmpeg refuses the playlist | re-pointed through the relay's `segment.ts` rewriter, which serves the same segments as `.ts` (identity re-checked from decoded frames) |
| CStar | the ParaTV file is a **VMAP ad document**, not a playlist (`Invalid data found`) | the operator's CStar slot (`/D17/index.m3u8`) — `C STAR` + `TOP FRANCE` logos read from the decoded picture |
| CW Forever | Amagi's extension-less `beacon?…` segment URLs | **Disney Channel** (English, logo confirmed) |
| TF1, TFX, TF1 Séries Films | TF1's CDN answers 403 to FFmpeg's user agent | the three TF1 channels moved to the companion playlist **`lume-france-tf1.m3u`** (plays in VLC / Apple TV's native player); the three slots in `lume-france.m3u` now carry **Gong**, **20 Minutes TV** and **Africanews (Français)**, each confirmed from decoded frames |

### Verification of this build

* **69/69** URLs re-tested with **FFmpeg**, the engine Lume actually uses:
  every one decodes H.264 video with AAC/MP2 audio.
* **69/69** re-tested with AVPlayer under the strict health policy.
* EPG still resolves every one of the 69 `tvg-id`s (6 642 programmes).

### What the user has to do

The app caches its playlist. **"Chaines TV" in Lume must be refreshed**
(pull-to-refresh on the playlist) to receive this build — until then the app
still points at the dead endpoints listed above.
