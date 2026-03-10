#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

EXPECTED_TOTAL="${EXPECTED_TOTAL:-432}"
SLEEP_SEC="${SLEEP_SEC:-60}"
PHASE3_PATTERN="${PHASE3_PATTERN:-run_framework_v1_phase3_grid|run_framework_v1_phase3_grid_batch7|run_phase3_all_pilot20k_qwen35|simulate.Simulate|pyloader/run.py|build_cache_variant.py}"

CORE_TSV="${CORE_TSV:-$ROOT/logs/framework_v1_phase3/phase3_combo_records_pilot20k_qwen35.tsv}"
BATCH7_TSV="${BATCH7_TSV:-$ROOT/logs/framework_v1_phase3_batch7/phase3_batch7_combo_records_pilot20k_qwen35.tsv}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_watch}"
LOG_PATH="$STATE_DIR/watch_phase3_all_qwen35_then_shutdown.log"
STATUS_FILE="$STATE_DIR/watch_phase3_all_qwen35_then_shutdown.status"
mkdir -p "$STATE_DIR"

log() {
  echo "[phase3-watch] $(date '+%F %T %z') $*" | tee -a "$LOG_PATH"
}

rows_in_file() {
  local path="$1"
  local lines=0
  if [[ -f "$path" ]]; then
    lines="$(wc -l < "$path" | tr -d ' ')"
  fi
  if [[ "$lines" -gt 0 ]]; then
    echo $((lines - 1))
  else
    echo 0
  fi
}

count_total_rows() {
  local core_rows batch7_rows
  core_rows="$(rows_in_file "$CORE_TSV")"
  batch7_rows="$(rows_in_file "$BATCH7_TSV")"
  echo $((core_rows + batch7_rows))
}

list_active() {
  pgrep -af "$PHASE3_PATTERN" || true
}

count_active() {
  local active="$1"
  if [[ -z "$active" ]]; then
    echo 0
  else
    printf '%s\n' "$active" | wc -l | tr -d ' '
  fi
}

log "started expected_total=$EXPECTED_TOTAL sleep_sec=$SLEEP_SEC"
log "core_tsv=$CORE_TSV"
log "batch7_tsv=$BATCH7_TSV"

while true; do
  total_rows="$(count_total_rows)"
  active_list="$(list_active)"
  active_count="$(count_active "$active_list")"

  {
    printf "time=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf "total_rows=%s\n" "$total_rows"
    printf "expected_total=%s\n" "$EXPECTED_TOTAL"
    printf "active_count=%s\n" "$active_count"
  } > "$STATUS_FILE"

  if [[ -n "$active_list" ]]; then
    printf "%s\n" "$active_list" >> "$STATUS_FILE"
  fi

  if [[ "$total_rows" -ge "$EXPECTED_TOTAL" ]]; then
    if [[ "$active_count" -eq 0 ]]; then
      log "completed total_rows=$total_rows/$EXPECTED_TOTAL active_count=0; sync then shutdown"
      sync
      shutdown -h now || /sbin/poweroff || poweroff || halt -p
      exit 0
    fi
    log "target reached total_rows=$total_rows/$EXPECTED_TOTAL but active_count=$active_count; waiting"
    sleep "$SLEEP_SEC"
    continue
  fi

  if [[ "$active_count" -eq 0 ]]; then
    log "phase3 inactive before reaching target total_rows=$total_rows/$EXPECTED_TOTAL; exiting without shutdown"
    exit 1
  fi

  log "running total_rows=$total_rows/$EXPECTED_TOTAL active_count=$active_count"
  sleep "$SLEEP_SEC"
done
