#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
ROUND="${2:-9}"
RUN_ID="${3:-20260217T133101Z-14904}"
EXTRACT_PID="${4:-${EXTRACT_PID:-}}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-0}"
SHUTDOWN_DELAY_MIN="${SHUTDOWN_DELAY_MIN:-1}"

OUT_CACHE="$ROOT/llm_cache_hms5c4040ble640_fs_robustv6_recall_20140901_20141109.jsonl"
WINDOW_PATH="$ROOT/llm/window_text_hms5c4040ble640_20140901_20141109_v2.jsonl"
LOG_PATH="$ROOT/logs/llm_offline_extract.log"
PID_PATTERN="llm_offline_extract.py .*llm_cache_hms5c4040ble640_fs_robustv6_recall_20140901_20141109.jsonl"

cd "$ROOT"

if [[ ! -f "$WINDOW_PATH" ]]; then
  echo "[follow] missing window text: $WINDOW_PATH" >&2
  exit 2
fi

latest_progress_line() {
  rg "run_id=${RUN_ID}.*(Estimated total windows|Progress batches=|Flushed|Completed total=|Run finished)" "$LOG_PATH" | tail -n 1 || true
}

is_extract_running() {
  if [[ -n "${EXTRACT_PID}" ]]; then
    kill -0 "${EXTRACT_PID}" >/dev/null 2>&1
  else
    pgrep -f "$PID_PATTERN" >/dev/null 2>&1
  fi
}

echo "[follow] start monitor run_id=$RUN_ID round=$ROUND extract_pid=${EXTRACT_PID:-auto}"
last_line=""

while is_extract_running; do
  line="$(latest_progress_line)"
  if [[ -n "$line" && "$line" != "$last_line" ]]; then
    echo "[follow] $line"
    last_line="$line"
  fi
  sleep 120
done

echo "[follow] extract process exited, validating output ..."
if [[ ! -s "$OUT_CACHE" ]]; then
  echo "[follow] output cache missing/empty: $OUT_CACHE" >&2
  exit 3
fi

total_rows="$(wc -l < "$WINDOW_PATH" | tr -d ' ')"
cache_rows="$(wc -l < "$OUT_CACHE" | tr -d ' ')"
echo "[follow] rows cache=$cache_rows window=$total_rows"

python llm/scripts/build_model_quality_report.py \
  --cache_paths "$OUT_CACHE" \
  --window_text_paths "$WINDOW_PATH" \
  --log_paths "$LOG_PATH" \
  --out_dir "$ROOT/docs/model_quality_hms_robustv6_recall" \
  --summary_csv "$ROOT/docs/model_quality_summary_hms_robustv6_recall.csv"

echo "[follow] run policy grid (round=$ROUND)"
bash "$ROOT/scripts/controller_hooks/policy_grid_hms5c4040ble640.sh" hms5c4040ble640 "$ROUND" "$ROOT"

echo "[follow] run micro grid (round=$ROUND)"
bash "$ROOT/scripts/controller_hooks/microgrid_hms5c4040ble640.sh" hms5c4040ble640 "$ROUND" "$ROOT"

echo "[follow] refresh robust report"
bash "$ROOT/run_robust_eval_report_v2.sh"

echo "[follow] done"
echo "[follow] outputs:"
echo "  - $ROOT/docs/hms_policy_grid_round${ROUND}_summary.md"
echo "  - $ROOT/docs/hms_microgrid_round${ROUND}_summary.md"
echo "  - $ROOT/docs/llm_robust_eval_report_v2.md"

if [[ "$AUTO_SHUTDOWN" == "1" ]]; then
  echo "[follow] scheduling shutdown in ${SHUTDOWN_DELAY_MIN} minute(s)"
  shutdown -h +"$SHUTDOWN_DELAY_MIN"
fi
