#!/usr/bin/env bash
# 6-gate stream tester. Prints single-line result: PASS|FAIL|<url>|<reason>|<codec>|<res>|<bitrate>
# Usage: test_stream.sh <hls_url> [user_agent]
# Exit 0 = PASS, non-zero = FAIL.

set -u
URL="${1:-}"
UA="${2:-Mozilla/5.0 (Macintosh; Intel Mac OS X 15_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15}"
TIMEOUT=10
TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
HLS_ARGS=(-allowed_extensions ALL)
if ffprobe -hide_banner -h demuxer=hls 2>&1 | grep -q "extension_picky"; then
  HLS_ARGS+=(-extension_picky 0)
fi

fail() {
  echo "FAIL|${URL}|$1|||"
  exit 1
}

pass() {
  echo "PASS|${URL}|ok|$1|$2|$3"
  exit 0
}

# Gate 1: Fetch content with GET. Many valid HLS origins reject HEAD requests.
curl -sL --max-time "$TIMEOUT" -A "$UA" \
  -o "$TMPD/body" -w '%{http_code}\n%{url_effective}\n' \
  "$URL" >"$TMPD/fetch" 2>/dev/null
CODE=$(sed -n '1p' "$TMPD/fetch")
EFFECTIVE_URL=$(sed -n '2p' "$TMPD/fetch")
[ -z "$CODE" ] || [ "$CODE" = "000" ] && fail "no_response"
[ "$CODE" -lt 200 ] || [ "$CODE" -ge 400 ] && fail "http_$CODE"

# Gate 2: Verify HLS or stream content.
BODY=$(head -c 65536 "$TMPD/body")
[ -z "$BODY" ] && fail "empty_body"

IS_HLS=0
echo "$BODY" | head -1 | grep -q "#EXTM3U" && IS_HLS=1
HAS_SEPARATE_AUDIO=0
echo "$BODY" | grep -q '#EXT-X-MEDIA:TYPE=AUDIO' && HAS_SEPARATE_AUDIO=1

# If the master has muxed audio, resolve its best variant. Keep masters with a
# separate audio rendition intact so ffprobe/ffmpeg can validate both tracks.
PLAY_URL="${EFFECTIVE_URL:-$URL}"
if [ "$IS_HLS" -eq 1 ] && [ "$HAS_SEPARATE_AUDIO" -eq 0 ] && echo "$BODY" | grep -q "#EXT-X-STREAM-INF"; then
  # Pick highest bandwidth variant
  VARIANT=$(echo "$BODY" | awk '
    /#EXT-X-STREAM-INF/ {
      match($0, /BANDWIDTH=[0-9]+/);
      bw = substr($0, RSTART+10, RLENGTH-10)+0;
      getline line;
      if (bw > maxbw) { maxbw = bw; best = line }
    }
    END { print best }
  ')
  if [ -n "$VARIANT" ]; then
    # Resolve every relative form correctly, including ../../ paths used by
    # MediaTailor/CloudFront manifests.
    PLAY_URL=$(python3 -c \
      'from urllib.parse import urljoin; import sys; print(urljoin(sys.argv[1], sys.argv[2]))' \
      "$PLAY_URL" "$VARIANT")
    MEDIA=$(curl -sL --max-time "$TIMEOUT" -A "$UA" "$PLAY_URL" 2>/dev/null | head -c 65536)
    [ -z "$MEDIA" ] && fail "variant_empty"
    BODY="$MEDIA"
  fi
fi

# Gate 3: ffprobe — verify it's a real video stream with codec info
PROBE=$(ffprobe -v quiet -print_format json -show_streams -show_format \
  -user_agent "$UA" "${HLS_ARGS[@]}" \
  -timeout 10000000 "$PLAY_URL" 2>/dev/null)
[ -z "$PROBE" ] && fail "ffprobe_empty"

VCODEC=$(echo "$PROBE" | jq -r '[.streams[]|select(.codec_type=="video")] | max_by(.height // 0) | .codec_name // empty' 2>/dev/null)
ACODEC=$(echo "$PROBE" | jq -r '[.streams[]|select(.codec_type=="audio")][0].codec_name // empty' 2>/dev/null)
WIDTH=$(echo "$PROBE" | jq -r '[.streams[]|select(.codec_type=="video")] | max_by(.height // 0) | .width // empty' 2>/dev/null)
HEIGHT=$(echo "$PROBE" | jq -r '[.streams[]|select(.codec_type=="video")] | max_by(.height // 0) | .height // empty' 2>/dev/null)
BITRATE=$(echo "$PROBE" | jq -r '.format.bit_rate // empty' 2>/dev/null)

[ -z "$VCODEC" ] && fail "no_video_codec"
[ -z "$ACODEC" ] && fail "no_audio_codec"
[ -z "$WIDTH" ] || [ -z "$HEIGHT" ] && fail "no_video_dimensions"
[ "$WIDTH" -le 0 ] || [ "$HEIGHT" -le 0 ] && fail "invalid_video_dimensions_${WIDTH}x${HEIGHT}"

# Gate 4: Download actual playable data (≥3s equiv). Use ffmpeg to read 3s real playback.
ffmpeg -hide_banner -loglevel error -user_agent "$UA" \
  "${HLS_ARGS[@]}" -rw_timeout 8000000 \
  -t 3 -i "$PLAY_URL" -f null - >"$TMPD/ff.err" 2>&1
FFRC=$?
if [ "$FFRC" -ne 0 ]; then
  REASON=$(head -1 "$TMPD/ff.err" | tr -d '\n' | tr '|' ':' | cut -c1-80)
  fail "ffmpeg_rc${FFRC}:${REASON}"
fi

# Gate 5: Re-probe (second look to catch intermittent/redirect-only streams)
PROBE2=$(ffprobe -v quiet -print_format json -show_streams \
  -user_agent "$UA" "${HLS_ARGS[@]}" \
  -timeout 8000000 "$PLAY_URL" 2>/dev/null)
V2=$(echo "$PROBE2" | jq -r '[.streams[]|select(.codec_type=="video")] | max_by(.height // 0) | .codec_name // empty' 2>/dev/null)
[ -z "$V2" ] && fail "reprobe_failed"

# Gate 6: Sample separated frames. A manifest, audio bed, or one frozen frame
# must not qualify as a healthy linear channel.
ffmpeg -hide_banner -loglevel error -user_agent "$UA" \
  "${HLS_ARGS[@]}" -rw_timeout 8000000 \
  -t 8 -i "$PLAY_URL" -an -vf "fps=1,scale=160:-2" \
  -f framemd5 "$TMPD/motion.md5" >"$TMPD/motion.err" 2>&1
MOTION_RC=$?
if [ "$MOTION_RC" -ne 0 ]; then
  REASON=$(head -1 "$TMPD/motion.err" | tr -d '\n' | tr '|' ':' | cut -c1-80)
  fail "motion_rc${MOTION_RC}:${REASON}"
fi
FRAMES=$(awk -F, '!/^#/ { count += 1 } END { print count + 0 }' "$TMPD/motion.md5")
UNIQUE_FRAMES=$(
  awk -F, '!/^#/ { gsub(/[[:space:]]/, "", $6); if ($6 != "") print $6 }' \
    "$TMPD/motion.md5" |
    sort -u |
    wc -l |
    tr -d ' '
)
[ "$FRAMES" -lt 3 ] && fail "insufficient_frames_${FRAMES}"
[ "$UNIQUE_FRAMES" -lt 2 ] && fail "frozen_video_${UNIQUE_FRAMES}_unique"

RES="${WIDTH}x${HEIGHT}"
[ -z "$BITRATE" ] && BITRATE="?"
pass "${VCODEC}/${ACODEC}" "$RES" "$BITRATE"
