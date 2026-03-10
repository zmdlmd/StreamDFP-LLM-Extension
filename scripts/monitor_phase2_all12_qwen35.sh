#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

RUN_TAG="${RUN_TAG:-pilot20k_qwen35}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/framework_v1}"
INTERVAL_SEC="${INTERVAL_SEC:-300}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"
SUMMARY_TSV="${SUMMARY_TSV:-}"

CORE_KEYS=(
  hi7
  hds723030ala640
  st3000dm001
  hms5c4040ble640
  st31500541as
)

BATCH7_KEYS=(
  hgsthms5c4040ale640
  st31500341as
  hitachihds5c4040ale630
  wdcwd30efrx
  wdcwd10eads
  st4000dm000
  hds5c3030ala630
)

ALL_KEYS=("${CORE_KEYS[@]}" "${BATCH7_KEYS[@]}")

resolve_summary() {
  if [[ -n "$SUMMARY_TSV" && -f "$SUMMARY_TSV" ]]; then
    echo "$SUMMARY_TSV"
    return 0
  fi
  local latest=""
  latest="$(ls -1t "$LOG_DIR"/phase2_all12_"$RUN_TAG"_*.tsv 2>/dev/null | head -n1 || true)"
  if [[ -n "$latest" ]]; then
    echo "$latest"
  fi
}

is_core_key() {
  local key="$1"
  local item
  for item in "${CORE_KEYS[@]}"; do
    if [[ "$item" == "$key" ]]; then
      return 0
    fi
  done
  return 1
}

window_path_for() {
  local key="$1"
  if is_core_key "$key"; then
    echo "$ROOT/llm/framework_v1/window_text_${key}_pilot20k.jsonl"
  else
    echo "$ROOT/llm/framework_v1/window_text_${key}_pilot20000.jsonl"
  fi
}

cache_path_for() {
  local key="$1"
  echo "$ROOT/llm/framework_v1/cache_${key}_zs_structured_v2_${RUN_TAG}.jsonl"
}

log_path_for() {
  local key="$1"
  echo "$LOG_DIR/phase2_${key}_zs_structured_v2_${RUN_TAG}.log"
}

expected_rows_for() {
  local key="$1"
  local win rows
  win="$(window_path_for "$key")"
  if [[ ! -f "$win" ]]; then
    echo "0"
    return 0
  fi
  rows="$(wc -l < "$win" | tr -d ' ')"
  if [[ "$MAX_WINDOWS" != "0" && "$rows" -gt "$MAX_WINDOWS" ]]; then
    rows="$MAX_WINDOWS"
  fi
  echo "$rows"
}

completed_count_for() {
  local summary="$1"
  if [[ ! -f "$summary" ]]; then
    echo "0"
    return 0
  fi
  awk 'NR>1 && NF>0 {count++} END{print count+0}' "$summary"
}

status_line_for() {
  local summary="$1"
  local key="$2"
  if [[ ! -f "$summary" ]]; then
    return 1
  fi
  awk -F '\t' -v k="$key" 'NR>1 && $1==k {print; found=1} END{if (!found) exit 1}' "$summary"
}

current_key_for() {
  local summary="$1"
  local key
  for key in "${ALL_KEYS[@]}"; do
    if ! status_line_for "$summary" "$key" >/dev/null 2>&1; then
      echo "$key"
      return 0
    fi
  done
  return 1
}

rows_for_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    wc -l < "$path" | tr -d ' '
  else
    echo "0"
  fi
}

mtime_age_sec() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "-1"
    return 0
  fi
  local now ts
  now="$(date +%s)"
  ts="$(stat -c %Y "$path")"
  echo $((now - ts))
}

gpu_line() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -n1 || true
  fi
}

main() {
  local summary monitor_log summary_base monitor_ts total_models done key cache_path per_log expected rows cache_age log_age gpu
  summary="$(resolve_summary)"
  if [[ -z "$summary" ]]; then
    echo "[monitor] no summary file found for run_tag=$RUN_TAG" >&2
    exit 1
  fi

  summary_base="$(basename "$summary" .tsv)"
  monitor_ts="$(date +%Y%m%d_%H%M%S)"
  monitor_log="$LOG_DIR/${summary_base}_monitor_${monitor_ts}.log"
  total_models="${#ALL_KEYS[@]}"

  echo "[monitor] start $(date '+%F %T') run_tag=$RUN_TAG summary=$summary interval=${INTERVAL_SEC}s" | tee -a "$monitor_log"

  while true; do
    done="$(completed_count_for "$summary")"
    key="$(current_key_for "$summary" || true)"
    gpu="$(gpu_line)"

    if [[ -z "$key" ]]; then
      echo "[monitor] $(date '+%F %T') completed=${done}/${total_models} state=all_done gpu=${gpu:-n/a}" | tee -a "$monitor_log"
      break
    fi

    cache_path="$(cache_path_for "$key")"
    per_log="$(log_path_for "$key")"
    expected="$(expected_rows_for "$key")"
    rows="$(rows_for_file "$cache_path")"
    cache_age="$(mtime_age_sec "$cache_path")"
    log_age="$(mtime_age_sec "$per_log")"

    echo "[monitor] $(date '+%F %T') completed=${done}/${total_models} current=${key} rows=${rows}/${expected} cache_age_s=${cache_age} log_age_s=${log_age} gpu=${gpu:-n/a}" | tee -a "$monitor_log"

    sleep "$INTERVAL_SEC"
  done
}

main "$@"
