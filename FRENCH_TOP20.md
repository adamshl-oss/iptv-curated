# French TV — audience top 20

The target is the exact 2025 Médiamétrie audience top 20, not a collection of
loosely French-language channels. Each channel is investigated separately in
`scripts/french_top20_target.json`.

Publication requires all of the following:

1. It is the actual linear channel.
2. It decodes as live audio and video.
3. It is not a loop, FAST substitute, or unrelated regional channel.
4. It can play from the cloud-hosted playlist on Apple TV without this Mac.
5. Its source is broadcaster-operated, a public licensed distribution feed,
   or a maintained resolver that exposes an unmodified official non-DRM feed.

The public playlist intentionally contains only the audited target channels
that meet every rule. DRM, paid, geo-restricted, viewer-IP-bound, dead, and
unauthorized candidates remain documented but are never inserted as filler.

As of the latest 2026-07-25 audit, twelve exact top-20 channels pass every gate:

- #1 TF1 — 720p through an always-on current-master resolver
- #6 CNEWS — 1080p
- #7 ARTE — 1080p through an always-on current-master resolver
- #8 TMC — 720p through an always-on current-master resolver
- #9 BFMTV — 540p
- #11 LCI — 720p through an always-on token-refresh relay
- #12 TFX — 720p through an always-on current-master resolver
- #14 RMC Découverte — 1080p
- #15 RMC Story — 1080p
- #16 TF1 Séries Films — 720p through an always-on current-master resolver
- #17 L'Équipe — 1080p through Samsung TV Plus
- #20 RMC Life — 1080p through Samsung TV Plus

CStar previously passed at 480p, but its official Dailymotion live is now
geo-restricted from the United States and its last signed rendition expired.
It was removed immediately instead of leaving a dead item in IPTVX.

Canonical playlist:

`https://adamshl-oss.github.io/iptv-curated/french-tv-top20-july-2026.m3u`

The GitHub Actions refresh resolves expiring official live URLs and refuses to
publish any update unless every included channel passes a real decode test.
The LCI relay obtains fresh official TF1 tokens, while the TF1-family resolver
selects the newest signed official master on every channel start. Neither the
playlist nor Apple TV depends on this Mac remaining online.
