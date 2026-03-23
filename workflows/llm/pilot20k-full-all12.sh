#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

load_public_env
cd_root

RUN_TAG="${RUN_TAG:-pilot20k_qwen3instruct2507}"
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-$RUN_TAG}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-qwen3instruct2507}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-0}"

AUTO_SHUTDOWN="$AUTO_SHUTDOWN" \
RUN_TAG="$RUN_TAG" \
bash scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh

PHASE3_RUN_TAG="$PHASE3_RUN_TAG" \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
bash scripts/run_phase3_all_pilot20k_qwen35.sh
