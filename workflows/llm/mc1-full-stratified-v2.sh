#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

load_public_env
cd_root

WINDOW_TEXT_IN="${WINDOW_TEXT_IN:-$ROOT/llm/framework_v1_mc1/window_text_mc1_pilot20k_stratified_v2.jsonl}"
REFERENCE_IN="${REFERENCE_IN:-$ROOT/llm/framework_v1_mc1/reference_mc1_pilot20k_stratified_v2.json}"
BASELINE_CSV="${BASELINE_CSV:-$ROOT/mc1_mlp/example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv}"

PHASE2_RUN_TAG="${PHASE2_RUN_TAG:-pilot20k_stratified_v2_qwen3instruct2507}"
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-pilot20k_stratified_v2}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-qwen3instruct2507}"
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"
PHASE3_DIM_KEYS="${PHASE3_DIM_KEYS:-compact9,compact14}"
PHASE3_COMBO_LIMIT="${PHASE3_COMBO_LIMIT:-24}"

SKIP_WINDOW_BUILD=1 \
RUN_TAG="$PHASE2_RUN_TAG" \
WINDOW_TEXT_IN="$WINDOW_TEXT_IN" \
REFERENCE_IN="$REFERENCE_IN" \
bash scripts/run_framework_v1_phase2_mc1.sh

CACHE_IN="${CACHE_IN:-$ROOT/llm/framework_v1_mc1/cache_mc1_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${PHASE2_RUN_TAG}.jsonl}"

RUN_TAG="$PHASE3_RUN_TAG" \
WINDOW_TEXT="$WINDOW_TEXT_IN" \
CACHE_IN="$CACHE_IN" \
BASELINE_CSV="$BASELINE_CSV" \
TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
PHASE3_DIM_KEYS="$PHASE3_DIM_KEYS" \
PHASE3_COMBO_LIMIT="$PHASE3_COMBO_LIMIT" \
bash scripts/run_framework_v1_phase3_grid_mc1.sh
