# IPTVX release contract

`iptvx.m3u` and the legacy `chaines-tv.m3u` are client-facing releases.
They are never changed by discovery, source renewal, or routine health audits.

`chaines-tv-candidate.m3u` is the only automatically rebuilt combined
manifest. It may change as channels are recovered or quarantined.

Promote a candidate only after both country playback audits have completed
successfully on the exact candidate revision. The promotion workflow snapshots
the candidate in `releases/` and atomically updates both client aliases. If
post-promotion playback fails, restore the prior release commit; client URLs do
not change.

Only authorized sources may be promoted. A P2P source is eligible only when
its authorization and exact channel identity are verified; it may not bypass a
paid service, DRM, geo restriction, or broadcaster access controls.
