#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
cd "$ROOT"

CHECK_INTERVAL="${CHECK_INTERVAL:-60}"
STALL_MINUTES="${STALL_MINUTES:-20}"
TARGET_COMBOS="${TARGET_COMBOS:-180}"

PHASE3_MODELS="${PHASE3_MODELS:-all}"
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-fs}"
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-fsv1}"
FEATURE_CONTRACT_MODE="${FEATURE_CONTRACT_MODE:-auto}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_fs}"
RECORDS_TSV="${RECORDS_TSV:-$STATE_DIR/phase3_combo_records.tsv}"
SUMMARY_CSV="${SUMMARY_CSV:-$ROOT/docs/prearff_grid_5models_fs_v1.csv}"
SUMMARY_MD="${SUMMARY_MD:-$ROOT/docs/prearff_grid_5models_fs_v1.md}"

LOG_DIR="${LOG_DIR:-$ROOT/logs}"
mkdir -p "$STATE_DIR" "$LOG_DIR"

count_done() {
  if [[ ! -f "$RECORDS_TSV" ]]; then
    echo 0
    return
  fi
  local lines
  lines=$(wc -l < "$RECORDS_TSV")
  if (( lines <= 1 )); then
    echo 0
  else
    echo $((lines - 1))
  fi
}

find_phase3_pid() {
  pgrep -f "bash scripts/run_framework_v1_phase3_grid.sh" | head -n 1 || true
}

launch_phase3_once() {
  local attempt="$1"
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  local log_path="$LOG_DIR/phase3_fs_resume_attempt${attempt}_${stamp}.log"
  echo "[auto-resume-phase3-fs] launch attempt=${attempt} log=${log_path}" >&2
  nohup env \
    PHASE3_MODELS="$PHASE3_MODELS" \
    PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
    PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
    PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
    FEATURE_CONTRACT_MODE="$FEATURE_CONTRACT_MODE" \
    STATE_DIR="$STATE_DIR" \
    RECORDS_TSV="$RECORDS_TSV" \
    SUMMARY_CSV="$SUMMARY_CSV" \
    SUMMARY_MD="$SUMMARY_MD" \
    stdbuf -oL -eL bash "$ROOT/scripts/run_framework_v1_phase3_grid.sh" \
    > "$log_path" 2>&1 < /dev/null &
  echo $!
}

kill_phase3_stack() {
  echo "[auto-resume-phase3-fs] kill stale phase3 stack" >&2
  pkill -f "bash scripts/run_framework_v1_phase3_grid.sh" || true
  pkill -f "pyloader/run.py.*${PHASE3_TAG_SUFFIX}" || true
  pkill -f "simulate.Simulate.*${PHASE3_TAG_SUFFIX}" || true
}

ensure_summary() {
  if [[ -s "$SUMMARY_CSV" && -s "$SUMMARY_MD" ]]; then
    return
  fi
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  local log_path="$LOG_DIR/phase3_fs_resume_finalize_${stamp}.log"
  echo "[auto-resume-phase3-fs] summary missing; finalizing via one more pass log=${log_path}" >&2
  env \
    PHASE3_MODELS="$PHASE3_MODELS" \
    PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
    PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
    PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
    FEATURE_CONTRACT_MODE="$FEATURE_CONTRACT_MODE" \
    STATE_DIR="$STATE_DIR" \
    RECORDS_TSV="$RECORDS_TSV" \
    SUMMARY_CSV="$SUMMARY_CSV" \
    SUMMARY_MD="$SUMMARY_MD" \
    bash "$ROOT/scripts/run_framework_v1_phase3_grid.sh" \
    > "$log_path" 2>&1 || true
}

attempt=0
done_count="$(count_done)"
last_done="$done_count"
last_change_ts="$(date +%s)"
child_pid=""

echo "[auto-resume-phase3-fs] start done=${done_count}/${TARGET_COMBOS}"

while (( done_count < TARGET_COMBOS )); do
  if [[ -z "$child_pid" ]] || ! kill -0 "$child_pid" 2>/dev/null; then
    ext_pid="$(find_phase3_pid)"
    if [[ -n "$ext_pid" ]]; then
      child_pid="$ext_pid"
      echo "[auto-resume-phase3-fs] attach existing pid=${child_pid}"
    else
      attempt=$((attempt + 1))
      child_pid="$(launch_phase3_once "$attempt")"
      echo "[auto-resume-phase3-fs] launched pid=${child_pid}"
    fi
  fi

  sleep "$CHECK_INTERVAL"

  done_count="$(count_done)"
  if (( done_count > last_done )); then
    last_done="$done_count"
    last_change_ts="$(date +%s)"
    echo "[auto-resume-phase3-fs] progress done=${done_count}/${TARGET_COMBOS}"
  fi

  if (( done_count >= TARGET_COMBOS )); then
    break
  fi

  now_ts="$(date +%s)"
  if (( now_ts - last_change_ts > STALL_MINUTES * 60 )); then
    echo "[auto-resume-phase3-fs] stall detected (>${STALL_MINUTES}m without progress)"
    kill_phase3_stack
    child_pid=""
    last_change_ts="$now_ts"
    sleep 5
  fi
done

ensure_summary
echo "[auto-resume-phase3-fs] done=${done_count}/${TARGET_COMBOS} summary_csv=${SUMMARY_CSV}"
