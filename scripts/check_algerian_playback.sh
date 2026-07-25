#!/usr/bin/env bash
# Verify that every published Algerian entry yields decodable video and audio.

set -uo pipefail

PLAYLIST_URL="${1:-https://adamshl-oss.github.io/iptv-curated/algerian-tv-july-2026-v2.m3u}"
FAILED=0
COUNT=0

while IFS=$'\t' read -r name url; do
  [ -n "$name" ] && [ -n "$url" ] || continue
  COUNT=$((COUNT + 1))
  result="$(scripts/test_stream.sh "$url" 2>/dev/null || true)"
  outcome="${result%%|*}"
  reason="$(printf '%s' "$result" | cut -d'|' -f3)"
  if [ "$outcome" = "PASS" ]; then
    printf 'PASS\t%s\n' "$name"
  else
    printf 'FAIL\t%s\t%s\n' "$name" "${reason:-unknown failure}"
    FAILED=1
  fi
done < <(
  curl -fsSL "${PLAYLIST_URL}?health=$(date -u +%s)" |
    awk '
      /^#EXTINF:/ {
        name=$0
        sub(/^.*,/, "", name)
        getline url
        if (url ~ /^https?:/) print name "\t" url
      }
    '
)

if [ "$COUNT" -ne 13 ]; then
  printf 'FAIL\tplaylist count\tfound %s entries, expected 13\n' "$COUNT"
  FAILED=1
fi

exit "$FAILED"
