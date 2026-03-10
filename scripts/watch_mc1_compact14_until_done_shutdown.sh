#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

TARGET="${TARGET:-12}"
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"
RUN_TAG="${RUN_TAG:-pilot20k}"
SIM_ITER_DAYS="${SIM_ITER_DAYS:-10}"
JAVA_XMX="${JAVA_XMX:-56g}"
VALIDATION_WINDOW="${VALIDATION_WINDOW:-30}"
SLEEP_SEC="${SLEEP_SEC:-20}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/mc1_compact14_watch}"
STATUS_FILE="$STATE_DIR/status.txt"
RUNNER_LOG="$STATE_DIR/runner.log"
mkdir -p "$STATE_DIR"

count_done() {
  find "$ROOT/mc1_mlp" -maxdepth 1 -type f \
    -name "phase3_mc1_compact14_*_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${RUN_TAG}_i${SIM_ITER_DAYS}.csv" \
    | wc -l
}

cleanup_intermediate() {
  rm -f "$ROOT"/save_model/mc1_compact14_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".pickle || true
  rm -rf "$ROOT"/pyloader/phase3_train_mc1_compact14_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -rf "$ROOT"/pyloader/phase3_test_mc1_compact14_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -f "$ROOT"/llm/framework_v1_mc1/phase3_variants/mc1_compact14_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".jsonl || true
}

echo "[compact14_watch] start target=$TARGET mode=$PHASE3_EXTRACT_MODE profile=$PHASE3_PROMPT_PROFILE tag=$RUN_TAG" | tee -a "$RUNNER_LOG"
echo "[compact14_watch] java_xmx=$JAVA_XMX validation_window=$VALIDATION_WINDOW sim_iter_days=$SIM_ITER_DAYS" | tee -a "$RUNNER_LOG"
df -h /root/autodl-tmp | sed -n '1,2p' | tee -a "$RUNNER_LOG"

while true; do
  done_now="$(count_done || echo 0)"
  printf "time=%s state=running done=%s/%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$done_now" "$TARGET" > "$STATUS_FILE"

  if [[ "$done_now" -ge "$TARGET" ]]; then
    echo "[compact14_watch] completed $done_now/$TARGET; shutdown now" | tee -a "$RUNNER_LOG"
    sync
    shutdown -h now
    exit 0
  fi

  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  batch_log="$STATE_DIR/batch_${ts}.log"
  echo "[compact14_watch] start one combo batch (done=$done_now/$TARGET) log=$batch_log" | tee -a "$RUNNER_LOG"
  set +e
  env \
    PHASE3_DIM_KEYS=compact14 \
    PHASE3_COMBO_LIMIT=1 \
    CONTINUE_ON_ERROR=1 \
    PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
    PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
    RUN_TAG="$RUN_TAG" \
    JAVA_XMX="$JAVA_XMX" \
    VALIDATION_WINDOW="$VALIDATION_WINDOW" \
    SIM_ITER_DAYS="$SIM_ITER_DAYS" \
    bash "$ROOT/scripts/run_framework_v1_phase3_grid_mc1.sh" > "$batch_log" 2>&1
  rc=$?
  set -u
  echo "[compact14_watch] batch rc=$rc" | tee -a "$RUNNER_LOG"

  cleanup_intermediate
  df -h /root/autodl-tmp | sed -n '1,2p' | tee -a "$RUNNER_LOG"
  sleep 3
done
