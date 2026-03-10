#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-pilot20k_qwen35}"
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-qwen35p20k}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"

echo "[phase3-all] start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[phase3-all] run_tag=$PHASE3_RUN_TAG extract=${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE} suffix=$PHASE3_TAG_SUFFIX max_windows=$MAX_WINDOWS"

PHASE3_RUN_TAG="$PHASE3_RUN_TAG" \
PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
PHASE3_MODELS=all \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
MAX_WINDOWS="$MAX_WINDOWS" \
bash scripts/run_framework_v1_phase3_grid.sh

echo "[phase3-all] core_models_done $(date -u +%Y-%m-%dT%H:%M:%SZ)"

PHASE3_RUN_TAG="$PHASE3_RUN_TAG" \
PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
MAX_WINDOWS="$MAX_WINDOWS" \
bash scripts/run_framework_v1_phase3_grid_batch7.sh

echo "[phase3-all] finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
