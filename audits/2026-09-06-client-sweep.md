# CHAINES TV sweep — September 6, 2026 (Chicago)

## Release defect

Public `chaines-tv.m3u` and `iptvx.m3u` were identical August 14 releases:
18 entries, SHA256 `e0a5a8fcd1083a95da9755bc6de314cae02f8e42e4b158b787fe3efd51c36dd4`.
The candidate also had 18 entries, but replaced Echorouk with recovered El Heddaf.
This was missed by count-only checks. Country aliases matched their canonical
copies at 11 French and 7 Algerian entries.

## Observed Echorouk failure, not a policy-only exclusion

The public URL actually tested was
`https://raw.githubusercontent.com/adamshl-oss/iptv-curated/main/streams/echorouk.m3u8`.
Three fresh complete startup gates, each with three independent media attempts:

| Completed UTC, September 7 | Result |
|---|---|
| 01:31:35.959576 | 0/3, `variant_empty` on all three |
| 01:32:09.672425 | 0/3, `variant_empty` on all three |
| 01:32:43.399859 | 0/3, `variant_empty` on all three |

No sustained or Apple test could run after those startup failures. These real
observations seed the new client health history at failure streak 3. The full
client audit independently also got 0/3. The fresh official resolver timed out
at the broadcaster rendezvous; the existing request-time cloud relay returned
HTTP 502 with upstream 522. No replacement was accepted. The channel remains
in its durable Algerian recovery registry even if quarantined from the client.

## Local full regression and limitations

All 18 old client entries were tested. All except Echorouk produced moving
decoded media; CNEWS was only 512x288. The initial strict 540p test rejected
CNEWS on quality and therefore skipped its Apple test. The improved cloud
audit measures quality and playback separately.

Eight entries passed the original local Apple+startup aggregate. Multiple later
local Apple startups timed out; TV1 took 14.1 seconds, and TV3 also had sustained
transport network errors. These are not dismissed as success. The Mac was
locked when native UI access was attempted, so IPTVX screen and Apple TV
hardware playback were not tested. Separate outside-cloud evidence is required;
any disagreement remains visible rather than attributed to locking without proof.

Current frames captured and inspected for Ennahar, El Heddaf and CNEWS showed
correct branding and broadcaster clocks matching the test time. Ennahar and
El Heddaf decoded at 1920x1080; CNEWS at 512x288. Short observation cannot prove
that a stream will never repeat or fail later.

## Independent verification

An adversarial subagent identified the frozen-release/count-masking problems,
then rejected initial all-or-nothing promotion and insufficient evidence checks.
Those findings were addressed before publication. It independently passed all
35 related regression tests, including contradictory gate fields, stale hashes,
wrong URLs, omitted healthy channels, transient failures and per-source history.

Cloud release audit: GitHub Actions run `34073170780` tests every unique candidate
and prior-client URL with three audio/video/motion attempts, sustained transport,
and real AVPlayer. Terminal result and final public counts must be checked before
claiming delivery. This document is not a claim that every channel is healthy.
