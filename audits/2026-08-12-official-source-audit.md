# Official-source audit — 2026-08-12

## Scope

Read-only audit of every unresolved or degraded in-scope target in
`CHANNEL_TARGETS.md`. It searched broadcaster-owned web pages and their
referenced public assets only. No third-party catalog, peer-to-peer source,
proxy, geo-bypass, account session, or playlist was used or changed.

## Observed result

14 targets were checked; no portable HLS candidate passed qualification.

| Country | Targets checked | Qualified sources |
| --- | ---: | ---: |
| France | 9 | 0 |
| Algeria | 5 | 0 |

France: France 2, France 3, M6, France 5, W9, 6ter, Canal+, CStar, Gulli.

Algeria: Samira TV, Echorouk TV, El Heddaf TV, Ennahar TV, Echorouk News.

The Ennahar check was a degradation investigation of the existing published
route, not a missing-target search.

## Interpretation

This is evidence about the public broadcaster surfaces observed on the audit
date. It is not proof that a channel has no licensed delivery method. In
particular, official services may be app-only, account-bound, DRM-protected,
geo-limited, or dynamically generated after browser authentication.

No stable IPTVX release was changed by this audit.
