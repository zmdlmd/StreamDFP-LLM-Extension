#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${ROOT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LOG_PATH="$ROOT_DIR/logs/auto_shutdown_after_hms_robustv5.log"
EXTRACT_PATTERN='python llm/llm_offline_extract.py .*llm_cache_hms5c4040ble640_fs_robustv5_20140901_20141109.jsonl'
TARGET_PID="${1:-}"

echo "[watcher] started at $(date '+%F %T %z') pid=${TARGET_PID:-none}" >> "$LOG_PATH"

if [[ -n "$TARGET_PID" ]]; then
  while kill -0 "$TARGET_PID" 2>/dev/null; do
    echo "[watcher] pid=$TARGET_PID running at $(date '+%F %T %z')" >> "$LOG_PATH"
    sleep 60
  done
else
  while pgrep -f "$EXTRACT_PATTERN" >/dev/null; do
    echo "[watcher] extractor still running at $(date '+%F %T %z')" >> "$LOG_PATH"
    sleep 60
  done
fi

echo "[watcher] extractor ended at $(date '+%F %T %z'), syncing and shutdown" >> "$LOG_PATH"
sync
shutdown -h now || poweroff || systemctl poweroff
