# French TV — audience top 20

The target is the exact 2025 Médiamétrie audience top 20, not a collection of
loosely French-language channels. Each channel is investigated separately in
`scripts/french_top20_target.json`.

Publication requires all of the following:

1. It is the actual linear channel.
2. It decodes as live audio and video.
3. It is not a loop, FAST substitute, or unrelated regional channel.
4. It can play from the cloud-hosted playlist on Apple TV without this Mac.
5. Its source is broadcaster-operated or a public licensed distribution feed.

The public playlist intentionally contains only the audited target channels
that meet every rule. DRM, paid, geo-restricted, viewer-IP-bound, dead, and
unauthorized candidates remain documented but are never inserted as filler.

As of the 2026-07-25 audit, eight exact top-20 channels pass every gate:

- #6 CNEWS — 1080p
- #9 BFMTV — 540p
- #11 LCI — 720p through an always-on token-refresh relay
- #14 RMC Découverte — 1080p
- #15 RMC Story — 1080p
- #17 L'Équipe — 1080p through Samsung TV Plus
- #19 CStar — 480p from its official Dailymotion live
- #20 RMC Life — 1080p through Samsung TV Plus

Canonical playlist:

`https://adamshl-oss.github.io/iptv-curated/french-tv-top20-july-2026.m3u`

The GitHub Actions refresh resolves expiring official live URLs and refuses to
publish any update unless every included channel passes a real decode test.
The LCI relay obtains a fresh official TF1 token per media request, so neither
the playlist nor Apple TV depends on this Mac remaining online.
