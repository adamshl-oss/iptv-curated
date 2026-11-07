# Lume playlists — verification report

Generated 2026-11-07T23:03:50.092158Z · commit `2194da8` on `adamshl-oss/iptv-curated`

Three playlists, **60 channels**, each one *tested — never sampled* — at three
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

## France — 20 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| TF1 | 1024x576 | 48000Hz/2ch | -27.4 dB | 250 | 2.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 2 | 1920x1080 | 48000Hz/2ch | -26.0 dB | 243 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 3 | 1920x1080 | 48000Hz/2ch | -26.3 dB | 242 | 1.3 s | 60.0 s (1.0) | 0 / 0.0 s | PASS |
| France 4 | 1920x1080 | 48000Hz/2ch | -26.3 dB | 247 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| France 5 | 1920x1080 | 48000Hz/2ch | -25.1 dB | 249 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| M6 | 1920x1080 | 48000Hz/2ch | -29.5 dB | 245 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| W9 | 1920x1080 | 48000Hz/2ch | -29.2 dB | 245 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ARTE | 1920x1080 | 48000Hz/2ch | -26.6 dB | 245 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TMC | 1920x1080 | 48000Hz/2ch | -26.4 dB | 245 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TFX | 1024x576 | 48000Hz/2ch | -26.4 dB | 250 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CStar | 1280x720 | 44100Hz/2ch | -25.9 dB | 498 | 2.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TF1 Séries Films | 1024x576 | 48000Hz/2ch | -26.2 dB | 250 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| D17 | 1920x1080 | 48000Hz/2ch | -27.1 dB | 201 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| BFMTV | 1920x1080 | 48000Hz/2ch | -26.5 dB | 245 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNews | 848x480 | 44100Hz/2ch | -26.5 dB | 500 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| LCI | 1280x720 | 48000Hz/2ch | -25.4 dB | 248 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| RMC Découverte | 1920x1080 | 48000Hz/2ch | -26.8 dB | 250 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| RMC Story | 1920x1080 | 48000Hz/2ch | -24.0 dB | 250 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| L'Équipe | 1920x1080 | 48000Hz/2ch | -26.9 dB | 250 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Gulli | 1024x576 | 48000Hz/2ch | -25.8 dB | 250 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## Algérie — 14 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| TV1 / Programme National | 1920x1080 | 44100Hz/2ch | -17.2 dB | 245 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV2 / Canal Algérie | 1920x1080 | 0Hz/0ch | -22.2 dB | 245 | 2.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV3 / A3 | 1920x1080 | 48000Hz/2ch | -24.3 dB | 248 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV4 / Tamazight | 544x576 | 48000Hz/2ch | -21.2 dB | 245 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TV7 / El Maarifa | 720x576 | 48000Hz/2ch | -21.7 dB | 247 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| AL24 News | 1920x1080 | 48000Hz/2ch | -29.8 dB | 250 | 0.8 s | 60.0 s (1.0) | 0 / 0.0 s | PASS |
| Ennahar TV | 1920x1080 | 48000Hz/2ch | -27.0 dB | 495 | 1.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Echorouk News | 1280x720 | 48000Hz/2ch | -14.7 dB | 250 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Echorouk TV | 1280x720 | 48000Hz/2ch | -21.5 dB | 249 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| El Bilad TV | 720x576 | 48000Hz/2ch | -17.8 dB | 248 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Amou Yazid TV | 1920x1080 | 48000Hz/2ch | -32.6 dB | 250 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Assalat TV (الساعة) | 1280x720 | 48000Hz/2ch | -22.8 dB | 241 | 4.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Al Taghir TV (التغيير) | 720x576 | 48000Hz/2ch | -23.3 dB | 250 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Ikhtyar TV (إختيار) | 720x576 | 48000Hz/2ch | -24.6 dB | 248 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## USA — 26 channels

| Channel | Video | Audio | Mean level | Decoded frames | Startup | Advancing | Stalls | AVPlayer |
|---|---|---|---|---|---|---|---|---|
| CBS | 1280x720 | 24000Hz/2ch | -20.2 dB | 299 | 1.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NBC | 768x432 | 48000Hz/2ch | -28.3 dB | 300 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ABC | 426x240 | 48000Hz/2ch | -19.9 dB | 299 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| FOX | 1280x720 | 24000Hz/2ch | -20.2 dB | 299 | 1.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ABC News | 1280x720 | 48000Hz/2ch | -25.7 dB | 300 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NBC News NOW | 768x432 | 48000Hz/2ch | -26.5 dB | 300 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNN | 1280x720 | 48000Hz/2ch | -27.9 dB | 171 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNN International | 544x480 | 48000Hz/2ch | -33.7 dB | 265 | 5.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| CNBC | 768x432 | 48000Hz/2ch | -27.4 dB | 298 | 3.3 s | 60.0 s (1.0) | 0 / 0.0 s | PASS |
| MSNBC | 768x432 | 48000Hz/6ch | -22.4 dB | 599 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Fox News | 768x432 | 48000Hz/2ch | -23.1 dB | 599 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Fox Business | 768x432 | 48000Hz/2ch | -19.5 dB | 298 | 8.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Bloomberg TV | 1280x720 | 48000Hz/2ch | -25.6 dB | 295 | 1.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Sky News | 768x432 | 48000Hz/2ch | -26.6 dB | 248 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| ESPN | 768x432 | 48000Hz/2ch | -27.3 dB | 598 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| NFL Network | 768x432 | 48000Hz/2ch | -23.3 dB | 598 | 11.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| TBS | 768x432 | 48000Hz/2ch | -24.5 dB | 599 | 11.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| AMC | 768x432 | 48000Hz/2ch | -21.3 dB | 599 | 8.3 s | 60.0 s (1.0) | 0 / 0.0 s | PASS |
| Syfy | 1920x1080 | 24000Hz/2ch | -23.6 dB | 598 | 0.8 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| Discovery Channel | 1280x720 | 48000Hz/2ch | -26.5 dB | 299 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| National Geographic | 1920x1080 | 0Hz/0ch | -19.8 dB | 299 | 0.8 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| History | 1920x1080 | 24000Hz/2ch | -23.3 dB | 600 | 0.8 s | 60.1 s (1.0) | 0 / 0.0 s | PASS |
| Investigation Discovery | 1280x720 | 24000Hz/2ch | -29.5 dB | 299 | 2.0 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Cartoon Network | 768x432 | 48000Hz/2ch | -23.7 dB | 550 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| MTV | 768x432 | 48000Hz/2ch | -24.5 dB | 599 | 3.3 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |
| Food Network | 768x432 | 48000Hz/2ch | -22.7 dB | 598 | 3.5 s | 60.2 s (1.0) | 0 / 0.0 s | PASS |

## Totals

| Layer | Result |
|---|---|
| Transport (segment fetch) | 60/60 |
| AVFoundation tracks (video + audio) | 60/60 |
| AVPlayer 60 s playback on the published files | 60/60 |
| Decoded video / decoded audio | 60/60 · 60/60 |
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
