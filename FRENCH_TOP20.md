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

Canonical playlist:

`https://adamshl-oss.github.io/iptv-curated/french-tv-top20-july-2026.m3u`

The GitHub Actions refresh resolves expiring official live URLs and refuses to
publish any update unless every included channel passes a real decode test.
