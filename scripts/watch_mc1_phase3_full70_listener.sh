#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"
RUN_TAG="${RUN_TAG:-pilot20k}"
SIM_ITER_DAYS="${SIM_ITER_DAYS:-10}"
JAVA_XMX="${JAVA_XMX:-44g}"
VALIDATION_WINDOW="${VALIDATION_WINDOW:-10}"

ROUND_LIMIT="${ROUND_LIMIT:-3}"      # combos per round
TARGET_COMBOS="${TARGET_COMBOS:-12}" # full70 total
MAX_EMPTY_ROUNDS="${MAX_EMPTY_ROUNDS:-6}"
SLEEP_SEC="${SLEEP_SEC:-10}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/mc1_full70_listener}"
STATUS_FILE="${STATUS_FILE:-$STATE_DIR/status.txt}"
mkdir -p "$STATE_DIR"

count_done() {
  find "$ROOT/mc1_mlp" -maxdepth 1 -type f \
    -name "phase3_mc1_full70_*_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${RUN_TAG}_i${SIM_ITER_DAYS}.csv" \
    | wc -l
}

cleanup_intermediates() {
  rm -f "$ROOT"/save_model/mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".pickle || true
  rm -rf "$ROOT"/pyloader/phase3_train_mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -rf "$ROOT"/pyloader/phase3_test_mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -f "$ROOT"/llm/framework_v1_mc1/phase3_variants/mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".jsonl || true
}

echo "[listener] start mode=$PHASE3_EXTRACT_MODE profile=$PHASE3_PROMPT_PROFILE tag=$RUN_TAG"
echo "[listener] target=$TARGET_COMBOS round_limit=$ROUND_LIMIT max_empty_rounds=$MAX_EMPTY_ROUNDS"
echo "[listener] sim_iter_days=$SIM_ITER_DAYS validation_window=$VALIDATION_WINDOW java_xmx=$JAVA_XMX"
df -h /root/autodl-tmp | sed -n '1,2p'

empty_rounds=0
round=0

while true; do
  done_before="$(count_done)"
  if [[ "$done_before" -ge "$TARGET_COMBOS" ]]; then
    echo "[listener] completed done=$done_before/$TARGET_COMBOS"
    printf "time=%s state=completed done=%s/%s empty_rounds=%s\n" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$done_before" "$TARGET_COMBOS" "$empty_rounds" > "$STATUS_FILE"
    break
  fi

  round=$((round + 1))
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  round_log="$STATE_DIR/round_${round}_${ts}.log"
  echo "[listener] round=$round start done_before=$done_before/$TARGET_COMBOS log=$round_log"
  printf "time=%s state=running round=%s done_before=%s/%s empty_rounds=%s\n" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$round" "$done_before" "$TARGET_COMBOS" "$empty_rounds" > "$STATUS_FILE"

  set +e
  env \
    PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
    PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
    PHASE3_DIM_KEYS="full70" \
    PHASE3_COMBO_LIMIT="$ROUND_LIMIT" \
    CONTINUE_ON_ERROR=1 \
    RUN_TAG="$RUN_TAG" \
    JAVA_XMX="$JAVA_XMX" \
    SIM_ITER_DAYS="$SIM_ITER_DAYS" \
    VALIDATION_WINDOW="$VALIDATION_WINDOW" \
    KEEP_ARFF=0 \
    KEEP_VARIANT=0 \
    MAX_ROUNDS=1 \
    STATE_DIR="$ROOT/logs/framework_v1_phase3_mc1_full70_rounds" \
    SUMMARY_CSV="$ROOT/docs/prearff_grid_mc1_full70_v1.csv" \
    SUMMARY_MD="$ROOT/docs/prearff_grid_mc1_full70_v1.md" \
    bash "$ROOT/scripts/run_mc1_phase3_full70_rounds.sh" > "$round_log" 2>&1
  rc=$?
  set -e

  done_after="$(count_done)"
  echo "[listener] round=$round rc=$rc done_after=$done_after/$TARGET_COMBOS"

  cleanup_intermediates
  df -h /root/autodl-tmp | sed -n '1,2p'

  if [[ "$done_after" -le "$done_before" ]]; then
    empty_rounds=$((empty_rounds + 1))
    echo "[listener] no progress (empty_rounds=$empty_rounds/$MAX_EMPTY_ROUNDS)"
  else
    empty_rounds=0
    echo "[listener] progress +$((done_after - done_before)) combos"
  fi

  printf "time=%s state=idle round=%s rc=%s done_after=%s/%s empty_rounds=%s\n" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$round" "$rc" "$done_after" "$TARGET_COMBOS" "$empty_rounds" > "$STATUS_FILE"

  if [[ "$empty_rounds" -ge "$MAX_EMPTY_ROUNDS" ]]; then
    echo "[listener] stop: reached max empty rounds"
    exit 3
  fi

  sleep "$SLEEP_SEC"
done
