#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$REPO_DIR/.venv-home-renewal"
APPLE_BIN="$REPO_DIR/.apple-avplayer-check-home"
LOCK_DIR="$REPO_DIR/.home-renewal.lock"
SERVER_PID=""

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  OLD_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    exit 0
  fi
  rm -f "$LOCK_DIR/pid"
  rmdir "$LOCK_DIR" 2>/dev/null || exit 0
  mkdir "$LOCK_DIR"
fi
echo "$$" >"$LOCK_DIR/pid"
cleanup() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$LOCK_DIR/pid"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

cd "$REPO_DIR"
[ "$(git branch --show-current)" = "main" ] || exit 1
git restore --staged --worktree --source=HEAD -- \
  streams/echorouk.m3u8 streams/echorouk-health.json
git pull --rebase origin main

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c \
  'import importlib.metadata; assert importlib.metadata.version("curl_cffi") == "0.14.0"' \
  2>/dev/null; then
  "$VENV/bin/pip" install -q 'curl_cffi==0.14.0'
fi
if [ ! -x "$APPLE_BIN" ] || [ scripts/apple_avplayer_check.swift -nt "$APPLE_BIN" ]; then
  xcrun swiftc -O scripts/apple_avplayer_check.swift -o "$APPLE_BIN"
fi

"$VENV/bin/python" - <<'PY'
from scripts.refresh_algerian_cloud import resolve_echorouk, write_echorouk_wrapper

write_echorouk_wrapper(resolve_echorouk())
PY

python3 -m http.server 18765 --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER_PID="$!"
sleep 1
kill -0 "$SERVER_PID"
APPLE_OUTPUT="$($APPLE_BIN \
  http://127.0.0.1:18765/streams/echorouk.m3u8 \
  scripts/stream_health_policy.json)"
kill "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""
case "$APPLE_OUTPUT" in
  PASS*) ;;
  *) echo "$APPLE_OUTPUT" >&2; exit 1 ;;
esac

git add streams/echorouk.m3u8
if ! git diff --cached --quiet; then
  git commit -m "Renew Echorouk home Apple session"
  for attempt in 1 2 3; do
    git pull --rebase origin main
    git push origin HEAD:main && break
    [ "$attempt" -eq 3 ] && exit 1
    sleep 5
  done
fi

EXPECTED_SHA="$(shasum -a 256 streams/echorouk.m3u8 | cut -d' ' -f1)"
PUBLIC_URL="https://raw.githubusercontent.com/adamshl-oss/iptv-curated/main/streams/echorouk.m3u8"
for attempt in $(seq 1 30); do
  REMOTE_SHA="$(curl -fsSL "$PUBLIC_URL?sync=$(date -u +%s%N)" | shasum -a 256 | cut -d' ' -f1)"
  [ "$REMOTE_SHA" = "$EXPECTED_SHA" ] && break
  [ "$attempt" -eq 30 ] && exit 1
  sleep 10
done
PUBLIC_OUTPUT="$($APPLE_BIN \
  "$PUBLIC_URL?health=$(date -u +%s%N)" \
  scripts/stream_health_policy.json)"
case "$PUBLIC_OUTPUT" in
  PASS*) ;;
  *) echo "$PUBLIC_OUTPUT" >&2; exit 1 ;;
esac

PUBLIC_EVIDENCE="${PUBLIC_OUTPUT#*|apple_ok; }"
"$VENV/bin/python" scripts/mark_home_authority_pass.py \
  --channel "Echorouk TV" --evidence "apple_ok; $PUBLIC_EVIDENCE"
git add streams/echorouk-health.json
if ! git diff --cached --quiet; then
  git commit -m "Record Echorouk home Apple health"
  for attempt in 1 2 3; do
    git pull --rebase origin main
    git push origin HEAD:main && break
    [ "$attempt" -eq 3 ] && exit 1
    sleep 5
  done
fi
