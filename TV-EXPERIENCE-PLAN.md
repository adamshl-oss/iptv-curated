# Adam's TV experience: acceptance criteria and repair plan

## Honest assessment — September 6, 2026

Not best in class. CHAINES TV was frozen at its August 14 release while country
controllers changed a different candidate. Equal channel counts concealed a
different lineup. CNEWS is available at 288p, not good television quality.
Echorouk's last successful renewal depended on a Mac and expired. A green job
was repeatedly confused with complete coverage and a good viewing experience.

## What the current repair changes

- Test the actual candidate AND previous client URLs, not just registry flags.
- Three audio/video/moving-frame startup tests, a sustained transport test and
  a real 60-second AVPlayer test. Report resolution separately from playback.
- Hourly cloud release checks, with evidence bound to exact stream URLs,
  playlist hashes, policy and time. Healthy additions/replacements can ship
  despite unrelated failures. Never silently remove an omitted healthy item.
- Persist failures across audits. Only remove an omitted existing item after
  durable repeated failure plus a fresh 0/3 gate; retain its recovery target.
- Verify both public client aliases after publishing. Save evidence and release
  snapshots; do not claim Apple TV hardware was tested by a cloud Mac runner.

## Remaining work, in order

| Priority | Deliverable | Acceptance test |
|---|---|---|
| 1 | Eliminate remaining Mac-only renewal paths, starting with Echorouk; renew expiring sources before expiry | Shut the home Mac down for 72 hours; exercise at least two expiry/renewal cycles remotely; no channel depends on a local sidecar |
| 2 | Public-client playback and freshness watchdog independent of GitHub's scheduler | Disable the GitHub scheduler in an isolated test; watchdog detects missed audits and restores scheduling; a missed job cannot stay silently green |
| 3 | Channel-specific failover between independently verified sources | Break primary in a staging route; alternate starts without editing IPTVX; verify failback, exhausted alternatives and current channel identity; mirrors of one source do not count as redundancy |
| 4 | Better pictures and coverage: CNEWS HD, Echorouk recovery, France Télévisions and M6 group | Publish each exact channel only after current branding, moving video, audio, repeated decodes and Apple playback; normally native 720p+; no upscaled SD passed off as HD |
| 5 | A simple living-room interface: one CHAINES TV source, consistent names/logos, guide data and favourites | Reopen IPTVX after a cold start; all expected identities appear in one accessible list; current/next programme agrees with broadcaster schedules |
| 6 | A quiet but honest service dashboard | Show playable/target counts separately, resolution, last actual test, failures and recovery progress; email notifications off; alert only on meaningful outages through an agreed non-email route |

## Definition of delivered

- Every published channel tested, never sampled. Visible moving pictures and
  startup/stall measurements on the actual Apple TV network are a separate
  acceptance step from cloud AVPlayer tests.
- Target startup under 5 seconds and no repeated stalls; measure 7 days first,
  then a 30-day rolling record. Target 99.5% availability for each supported
  channel, not merely for the scheduler. These are goals, not present guarantees.
- Run 10-minute viewing checks for new/repaired channels and a 24-hour soak
  before claiming a recovery is durable. Report quality compromises explicitly.
- Show coverage honestly: France's 20 exact targets remain a stretch goal, and
  Algeria's major channels remain durable recovery/discovery targets. Successful
  automation does not mean those targets have been achieved.
- Use source-discovery memory with backoff and new source families; count only
  channels actually restored/added as coverage progress. If no suitable feed
  exists, keep the gap visible rather than substitute an unrelated channel.

No unattended system can guarantee that an external broadcaster never changes
or stops its feed. Best in class here means rapid measured recovery, independent
failure detection, honest gaps and no need for Adam to discover every outage.
