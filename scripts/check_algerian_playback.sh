#!/usr/bin/env bash
# Backward-compatible entry point for the comprehensive Algerian checker.

set -euo pipefail
exec python3 scripts/check_algerian_playback.py "$@"
