#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

MODEL_KEY="${MODEL_KEY:?MODEL_KEY is required}"
PHASE2_SUMMARY_TSV="${PHASE2_SUMMARY_TSV:?PHASE2_SUMMARY_TSV is required}"
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:?PHASE3_RUN_TAG is required}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-autonext}"
POLL_SEC="${POLL_SEC:-60}"
LOG_PATH="${LOG_PATH:-$ROOT/logs/framework_v1_phase3/watch_${MODEL_KEY}_${PHASE3_RUN_TAG}.log}"

mkdir -p "$(dirname "$LOG_PATH")"

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

echo "[watch_phase2_single_then_phase3] start $(date '+%F %T') model=$MODEL_KEY phase2_summary=$PHASE2_SUMMARY_TSV phase3_run_tag=$PHASE3_RUN_TAG" >> "$LOG_PATH"

while true; do
  if [[ ! -f "$PHASE2_SUMMARY_TSV" ]]; then
    echo "[watch_phase2_single_then_phase3] waiting for summary: $PHASE2_SUMMARY_TSV" >> "$LOG_PATH"
    sleep "$POLL_SEC"
    continue
  fi

  row="$(awk -F '\t' -v key="$MODEL_KEY" '$1==key {print $0}' "$PHASE2_SUMMARY_TSV" | tail -n 1)"
  if [[ -z "$row" ]]; then
    echo "[watch_phase2_single_then_phase3] waiting for model row: $MODEL_KEY" >> "$LOG_PATH"
    sleep "$POLL_SEC"
    continue
  fi

  status="$(printf '%s\n' "$row" | awk -F '\t' '{print $2}')"
  echo "[watch_phase2_single_then_phase3] status=$(date '+%F %T') model=$MODEL_KEY phase2_status=$status" >> "$LOG_PATH"

  if [[ "$status" == "ok" || "$status" == "skip_complete" ]]; then
    break
  fi

  if [[ "$status" == failed_after_retry || "$status" == missing_window || "$status" == missing_reference || "$status" == missing_mapping ]]; then
    echo "[watch_phase2_single_then_phase3] abort due to phase2_status=$status" >> "$LOG_PATH"
    exit 1
  fi

  sleep "$POLL_SEC"
done

if is_core_model "$MODEL_KEY"; then
  phase3_script="$ROOT/scripts/run_framework_v1_phase3_grid.sh"
else
  phase3_script="$ROOT/scripts/run_framework_v1_phase3_grid_batch7.sh"
fi

echo "[watch_phase2_single_then_phase3] launch phase3 $(date '+%F %T') script=$phase3_script model=$MODEL_KEY run_tag=$PHASE3_RUN_TAG tag_suffix=$PHASE3_TAG_SUFFIX" >> "$LOG_PATH"

PHASE3_MODELS="$MODEL_KEY" \
PHASE3_RUN_TAG="$PHASE3_RUN_TAG" \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
bash "$phase3_script" >> "$LOG_PATH" 2>&1

echo "[watch_phase2_single_then_phase3] done $(date '+%F %T') model=$MODEL_KEY" >> "$LOG_PATH"
