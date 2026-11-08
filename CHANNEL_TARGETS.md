# Canonical channel targets

This registry defines the channels the service is trying to deliver. It is
independent from stream availability: an unavailable channel remains a target
and is never silently replaced by a different channel.

## France

Ranked by 2025 national audience share (Médiamétrie/Médiamat), with services
that are no longer operating excluded. Ties retain their source order.

| Rank | Channel |
| ---: | --- |
| 1 | TF1 |
| 2 | France 2 |
| 3 | France 3 |
| 4 | M6 |
| 5 | France 5 |
| 6 | CNews |
| 7 | Arte |
| 8 | TMC |
| 9 | BFMTV |
| 10 | W9 |
| 11 | LCI |
| 12 | RMC Découverte |
| 13 | TFX |
| 14 | RMC Story |
| 15 | TF1 Séries Films |
| 16 | L'Équipe |
| 17 | Canal+ |
| 18 | CStar |
| 19 | Gulli |
| 20 | 6ter |

## Algeria

This is a list of Algerian-origin services, not a list of every foreign
channel watched in Algeria. Kantar's 2025 Africascope top ten confirms the
relative audience position of the first five domestic services below. Public
reporting does not provide a credible domestic-only order for the remaining
five, so they are a deliberate national-coverage selection rather than
invented ranks.

| Rank | Channel | Evidence status |
| ---: | --- | --- |
| 1 | Samira TV | Kantar domestic leader |
| 2 | Echorouk TV | Kantar domestic ranking |
| 3 | El Heddaf TV | Kantar domestic ranking |
| 4 | Ennahar TV | Kantar domestic ranking |
| 5 | ENTV – Programme National | Kantar domestic ranking |
| 6 | Canal Algérie | national public-service selection |
| 7 | TV3 / A3 | national public-service selection |
| 8 | Echorouk News | national news selection |
| 9 | El Bilad TV | national news/generalist selection |
| 10 | AL24 News | national news selection |

## Evidence

- Kantar, *Africascope Maghreb 2025*: fieldwork November–December 2025,
  4,109 respondents aged 15+ across the main Maghreb cities.
- Médiamétrie, *Médiamat Annuel 2025*: audience-share source for France.
- Arcom's current national-service list is used to exclude discontinued
  services and confirm current French channel identities.

## Operating rule

Every source candidate must match this exact channel identity and be recorded
as one of: official, licensed provider, or verified authorized distribution.
Peer-to-peer transport is allowed only when the underlying distribution is
authorized; it cannot be used to bypass paid access, DRM, geographic controls,
or broadcaster terms.

## USA — content policy

The USA playlist carries **no Spanish-language channels**. This is a standing
requirement from the service owner, not a sourcing constraint: Spanish-language
networks (Telemundo, Univision, UniMás, Canal Uno, América Te Ve, NuvoTV, LATV,
Entravision, Bandorama, Pdia, TUDN, ESPN Deportes, Fox Deportes, V-me and
similar) are **excluded by policy** and must never appear in the USA playlist.

They are not "unsourced" either — they are out of scope, and are reported
separately from the sourcing gaps:

* `lume-manifest.json` → `excluded_by_policy.USA`
* `lume-manifest.json` → `policy_checks.usa_no_spanish_channels`

The rule is enforced at build time: the playlist generator aborts before
writing any file if a USA channel matches an excluded id or a Spanish-language
marker token, so a candidate can never slip in through a later import.

### The rule covers the feed, not only the channel name

A brand can have a US channel and a separate Latin-American channel under the
same name. A frame-by-frame audit of every published USA feed found that the
reachable streams for **Discovery Channel**, **Investigation Discovery**,
**National Geographic** and **History** were the **Spanish (or Portuguese)
Latin-American editions**, with the language baked into the picture. Publishing
them would have broken this policy while the playlist said nothing wrong.

Those feeds are therefore not published. The channels are listed in
`lume-manifest.json` → `unsourced_targets` with the reason, and the US linear
feeds are TV-provider gated. Where an English equivalent exists it is published
instead — National Geographic (English), BBC News, HGTV, FOX (the broadcast
network), CBS News 24/7 and Comedy Central are in the playlist as a result.

The same audit is why three entries were renamed to their factual identity
(`KIRO 9 (CBS Seattle)`, `ABC 6 (Phoenix)`, `NBC News NOW (Bay Area)`) and why
`Comedy Central` is published under its own name rather than as "History".

