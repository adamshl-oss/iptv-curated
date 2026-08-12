# Live route verification — 2026-08-12

This is fresh observed behavior, not a restatement of historical registry
claims. No playlist was changed during the audit.

## Results

- All 17 currently published canonical routes passed the repository's full
  six-gate test: HTTP HLS fetch, stream probe, audio/video decode, second
  probe, and changing-frame verification.
- All 17 also passed 60 seconds in macOS AVFoundation with a 100% advancing
  ratio and zero stalls.
- CStar, which is recorded but unpublished, passed both gates at 848x480 and
  displayed an explicit CStar watermark.
- El Heddaf displayed the correct channel and passed the short six-gate test,
  but failed sustained Apple playback on both its relay and direct upstream.
  The relay advanced for 34.5/60.1 seconds; the direct source advanced for
  50.8/60.1 seconds. It remains correctly quarantined.
- The dormant Echorouk News relay endpoint still returns a live HLS window,
  but current segments cannot establish valid video dimensions and repeatedly
  fail H.264 SPS/PPS decoding. It is not publishable.

## Passing canonical routes

France (11/20): TF1, CNEWS, ARTE, TMC, BFMTV, LCI, TFX, RMC Découverte,
RMC Story, TF1 Séries Films, and L'Équipe.

Algeria (6/10): Ennahar TV, Programme National/TV1, Canal Algérie/TV2,
TV3/A3, El Bilad TV, and AL24 News.

Current sampled frames visibly confirmed the intended channel for every route
except TF1 (advertising was sampled) and TFX (TFOU branding was sampled).
Those two identities are supported by their channel-specific resolver paths
and historical evidence, but not by a visible channel watermark in this run.

## Recovered runtime source map

The relay implementation itself is not stored in this repository. Its current
HLS responses nevertheless expose these runtime upstreams:

- TF1, TMC, TFX, TF1 Séries Films and ARTE: channel-specific `diff.tf1.fr`
  CDN delivery.
- CNEWS: Dailymotion live identity `x3b68jn` through the Apple-facing relay.
- BFMTV: `live-cdn-stream-euw1.bfmtv.bct.nextradiotv.com`.
- RMC Découverte and RMC Story: their recorded CloudFront distributions.
- L'Équipe: Samsung TV Plus CloudFront distribution.
- AL24: `cdn.live.easybroadcast.io`.
- TV1, TV3, Ennahar, El Bilad and dormant Echorouk News: channel-specific
  paths on `ar.ycncdn.online`, with media shortened through the relay.
- TV2: `fl-dvr.iptvcdn.tv/chid_347`.
- El Heddaf: `live.elheddaftv.com:8081/elheddaftv/index.m3u8`.

## Missing-channel observations

- France 2, France 3 and France 5: current wrapper and SSAI masters respond,
  but their live media segments return HTTP 403 and do not decode.
- M6, W9 and 6ter: recorded clear/provider alternatives did not decode; W9's
  former 6cloud paths return HTTP 403.
- Canal+: the stored public resolver is only the inexact en-clair service, not
  the full canonical linear channel.
- Gulli: the recorded candidate returns HTTP 404.
- Samira TV: no stored portable endpoint was recovered.
- Echorouk TV: no active relay route was recovered; its former signed source
  is no longer usable.

## Repository defects exposed

- The French registry records are not physically rank-sorted. The playback
  checker incorrectly required file order rather than sorting by canonical
  rank; this audit fixes the checker.
- The Algerian checker still assumed all 20 legacy records were in scope. It
  now honors the canonical `target_count` of 10.
- TF1 and TF1 Séries Films have stale reason text saying they are quarantined,
  despite current `publish: true` state and fresh successful playback.
- The frozen IPTVX release still contains obsolete RMC Life rather than the
  canonical Gulli target. This is release drift, not a live source result.
