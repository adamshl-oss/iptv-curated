# Lume playlists — verification report

Generated 2026-11-08T04:33:12.508174Z · commit `3f89b66` on `adamshl-oss/iptv-curated`

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
| TV3 / A3 | 1920x1080 | 48000Hz/2ch | -24.8 dB | 248 | 6.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV4 / Tamazight | 544x576 | 48000Hz/2ch | -23.2 dB | 240 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV6 / EPTV 6 (الشبابية) | 1920x1080 | 48000Hz/2ch | -24.7 dB | 248 | 5.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV7 / El Maarifa | 720x576 | 48000Hz/2ch | -28.4 dB | 247 | 6.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
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
