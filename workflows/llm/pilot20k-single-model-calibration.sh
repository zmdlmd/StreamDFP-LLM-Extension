#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

load_public_env
cd_root

MODEL_KEY="${MODEL_KEY:?MODEL_KEY is required}"
RUN_TAG="${RUN_TAG:-pilot20k_qwen35_calib}"
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-$RUN_TAG}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-qwen35calib}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-0}"

is_core_model() {
  case "$1" in
    hi7|hds723030ala640|st3000dm001|hms5c4040ble640|st31500541as)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_batch7_model() {
  case "$1" in
    hgsthms5c4040ale640|st31500341as|hitachihds5c4040ale630|wdcwd30efrx|wdcwd10eads|st4000dm000|hds5c3030ala630)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_phase3_script() {
  local key="$1"
  if is_core_model "$key"; then
    echo "scripts/run_framework_v1_phase3_grid.sh"
    return 0
  fi
  if is_batch7_model "$key"; then
    echo "scripts/run_framework_v1_phase3_grid_batch7.sh"
    return 0
  fi
  echo "[pilot20k-single-model-calibration] unsupported MODEL_KEY=$key" >&2
  echo "[pilot20k-single-model-calibration] This wrapper currently supports only models already registered in the public pilot20k scripts." >&2
  return 2
}

echo "[pilot20k-single-model-calibration] start model=$MODEL_KEY run_tag=$RUN_TAG phase3_run_tag=$PHASE3_RUN_TAG suffix=$PHASE3_TAG_SUFFIX"
echo "[pilot20k-single-model-calibration] phase2: TARGET_KEYS=$MODEL_KEY"

AUTO_SHUTDOWN="$AUTO_SHUTDOWN" \
TARGET_KEYS="$MODEL_KEY" \
RUN_TAG="$RUN_TAG" \
bash scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh

phase3_script="$(resolve_phase3_script "$MODEL_KEY")"
echo "[pilot20k-single-model-calibration] phase3: script=$phase3_script model=$MODEL_KEY"

PHASE3_MODELS="$MODEL_KEY" \
PHASE3_RUN_TAG="$PHASE3_RUN_TAG" \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
bash "$phase3_script"

echo "[pilot20k-single-model-calibration] done model=$MODEL_KEY"
