#!/usr/bin/env bash
# Wave A — core pipeline API smoke (leads, workboard, follow-ups, gate assistant, meta).
# Run from repo root: bash scripts/verify_wave_a.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pytest \
  tests/test_api_v1_leads.py \
  tests/test_api_v1_workboard.py \
  tests/test_api_v1_follow_ups.py \
  tests/test_api_v1_gate_assistant.py \
  tests/test_api_v1_meta.py \
  tests/test_api_v1_auth_me.py \
  -q
