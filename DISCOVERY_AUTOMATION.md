# Channel discovery memory

The cloud discovery controller is stateful. Frequent scheduler wakes do not
repeat the same full search.

## Sequence

1. Restore `source-discovery-history.json` from the dedicated
   `discovery-state` branch.
2. Build a per-channel frontier of distinct source families: official page,
   official app assets, deeper app assets, multiple GitHub query forms, and
   each maintained catalog.
3. Choose up to four never-tried, oldest-channel-first tasks per wake. This
   keeps the research moving broadly without burning the entire frontier at
   once. If every path is cooling down, report the next eligible time and skip
   FFmpeg installation.
4. Record candidates, rejection/playback outcome, source, redacted URL,
   attempt count, and next eligible time.
5. Treat every discovered URL as a lead, including official player assets,
   catalogs, GitHub, and P2P indexes. It cannot be published until an
   endpoint-level admission records rights-holder or distributor evidence that
   explicitly permits third-party IPTVX delivery (and proxying/P2P where
   applicable).
6. Do not decode an unchanged failed candidate again for seven days. Catalogs
   may be revisited after 24 hours, official surfaces after 72 hours, and deep
   or GitHub research after seven days.
7. Persist the updated frontier back to `discovery-state` and attach the full
   plan, report, and memory ledger to the workflow run.

The state branch is separate from `main`, so research bookkeeping does not
rebuild GitHub Pages or change either public playlist. Playback evidence is
never distribution-rights evidence. Automatic replacement is disabled; a
source must first be added to `scripts/source_admissions.json` with exact
channel, endpoint, territory, and authorization evidence before a separately
reviewed promotion.
