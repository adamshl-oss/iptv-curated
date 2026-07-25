# French TV — France Top 30

The production target is defined in
`scripts/french_top30_target.json`. It is based on the 2025 annual
Médiamétrie audience ranking, the current Arcom national-channel lineup, and
five explicitly identified French additions. It is not a list of any streams
that happen to be in French.

`scripts/validate_french_top30.py` enforces exact membership, uniqueness, and
order. A refresh must never replace an unavailable target with an unrelated
channel.

The target and playback gates are intentionally separate:

1. The target validator proves that the playlist contains the requested
   channels.
2. The playback validator proves that every published stream currently
   decodes.

The production playlist must pass both. Channels whose official delivery
requires an account, regional entitlement, paid subscription, custom headers,
or DRM cannot be represented by an unauthenticated public M3U URL. They must
remain unavailable until an authorized delivery method exists; they must not
be replaced with foreign or niche channels.
