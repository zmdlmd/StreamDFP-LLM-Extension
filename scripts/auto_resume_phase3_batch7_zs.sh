#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
cd "$ROOT"

CHECK_INTERVAL="${CHECK_INTERVAL:-120}"
STALL_MINUTES="${STALL_MINUTES:-30}"
TARGET_COMBOS="${TARGET_COMBOS:-252}"  # 7 models * 36 combos
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-b7zs}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_batch7}"
SUMMARY_CSV="${SUMMARY_CSV:-$ROOT/docs/prearff_grid_batch7_zs_v1.csv}"
SUMMARY_MD="${SUMMARY_MD:-$ROOT/docs/prearff_grid_batch7_zs_v1.md}"
LOG_DIR="${LOG_DIR:-$ROOT/logs}"
mkdir -p "$STATE_DIR" "$LOG_DIR"

count_done() {
  find "$ROOT/hi7_example" -maxdepth 1 -type f -name "phase3b7_*_${PHASE3_TAG_SUFFIX}_D10_H05000_i10.csv" | wc -l
}

find_phase3_pid() {
  pgrep -f "bash $ROOT/scripts/run_framework_v1_phase3_grid_batch7.sh" | head -n 1 || true
}

launch_phase3_once() {
  local attempt="$1"
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  local log_path="$LOG_DIR/phase3_batch7_zs_resume_attempt${attempt}_${stamp}.log"
  echo "[auto-resume-phase3-batch7] launch attempt=${attempt} log=${log_path}" >&2
  nohup env \
    PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
    STATE_DIR="$STATE_DIR" \
    SUMMARY_CSV="$SUMMARY_CSV" \
    SUMMARY_MD="$SUMMARY_MD" \
    stdbuf -oL -eL bash "$ROOT/scripts/run_framework_v1_phase3_grid_batch7.sh" \
    > "$log_path" 2>&1 < /dev/null &
  echo $!
}

kill_phase3_stack() {
  echo "[auto-resume-phase3-batch7] kill stale phase3 stack" >&2
  pkill -f "bash $ROOT/scripts/run_framework_v1_phase3_grid_batch7.sh" || true
  pkill -f "pyloader/run.py.*phase3b7_" || true
  pkill -f "simulate.Simulate.*phase3b7_" || true
}

ensure_summary() {
  if [[ -s "$SUMMARY_CSV" && -s "$SUMMARY_MD" ]]; then
    return
  fi
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  local log_path="$LOG_DIR/phase3_batch7_zs_resume_finalize_${stamp}.log"
  echo "[auto-resume-phase3-batch7] summary missing; finalizing log=${log_path}" >&2
  env \
    PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
    STATE_DIR="$STATE_DIR" \
    SUMMARY_CSV="$SUMMARY_CSV" \
    SUMMARY_MD="$SUMMARY_MD" \
    bash "$ROOT/scripts/run_framework_v1_phase3_grid_batch7.sh" \
    > "$log_path" 2>&1 || true
}

attempt=0
done_count="$(count_done)"
last_done="$done_count"
last_change_ts="$(date +%s)"
child_pid=""

echo "[auto-resume-phase3-batch7] start done=${done_count}/${TARGET_COMBOS}"

while (( done_count < TARGET_COMBOS )); do
  if [[ -z "$child_pid" ]] || ! kill -0 "$child_pid" 2>/dev/null; then
    ext_pid="$(find_phase3_pid)"
    if [[ -n "$ext_pid" ]]; then
      child_pid="$ext_pid"
      echo "[auto-resume-phase3-batch7] attach existing pid=${child_pid}"
    else
      attempt=$((attempt + 1))
      child_pid="$(launch_phase3_once "$attempt")"
      echo "[auto-resume-phase3-batch7] launched pid=${child_pid}"
    fi
  fi

  sleep "$CHECK_INTERVAL"

  done_count="$(count_done)"
  if (( done_count > last_done )); then
    last_done="$done_count"
    last_change_ts="$(date +%s)"
    echo "[auto-resume-phase3-batch7] progress done=${done_count}/${TARGET_COMBOS}"
  fi

  if (( done_count >= TARGET_COMBOS )); then
    break
  fi

  now_ts="$(date +%s)"
  if (( now_ts - last_change_ts > STALL_MINUTES * 60 )); then
    echo "[auto-resume-phase3-batch7] stall detected (>${STALL_MINUTES}m without progress)"
    kill_phase3_stack
    child_pid=""
    last_change_ts="$now_ts"
    sleep 5
  fi
done

ensure_summary
echo "[auto-resume-phase3-batch7] done=${done_count}/${TARGET_COMBOS} summary_csv=${SUMMARY_CSV}"
