#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
MODEL="${1:?model_key required}"
PIPE_PID="${2:?pipeline pid required}"
INTERVAL="${3:-30}"

WINDOW="$ROOT/llm/window_text_${MODEL}_20140901_20141109.jsonl"
FS="$ROOT/llm_cache_${MODEL}_fs_20140901_20141109_compare_map70.jsonl"
ZS="$ROOT/llm_cache_${MODEL}_zs_20140901_20141109_compare_map70.jsonl"

if [[ ! -f "$WINDOW" ]]; then
  echo "[watch-stop][ERROR] missing window file: $WINDOW" >&2
  exit 1
fi

TOTAL=$(wc -l < "$WINDOW" | tr -d ' ')
echo "[watch-stop] start $(date '+%F %T') model=$MODEL pid=$PIPE_PID total=$TOTAL"

while true; do
  if ! ps -p "$PIPE_PID" >/dev/null 2>&1; then
    echo "[watch-stop] pipeline pid=$PIPE_PID not running; exit"
    exit 0
  fi

  FS_N=0
  ZS_N=0
  [[ -f "$FS" ]] && FS_N=$(wc -l < "$FS" | tr -d ' ')
  [[ -f "$ZS" ]] && ZS_N=$(wc -l < "$ZS" | tr -d ' ')
  echo "[watch-stop] $(date '+%F %T') fs=$FS_N/$TOTAL zs=$ZS_N/$TOTAL"

  if [[ "$ZS_N" -ge "$TOTAL" ]]; then
    echo "[watch-stop] target reached; stopping pipeline pid=$PIPE_PID"
    pkill -TERM -P "$PIPE_PID" || true
    kill -TERM "$PIPE_PID" || true
    sleep 5
    if ps -p "$PIPE_PID" >/dev/null 2>&1; then
      kill -KILL "$PIPE_PID" || true
    fi
    echo "[watch-stop] stopped at $(date '+%F %T')"
    exit 0
  fi

  sleep "$INTERVAL"
done
