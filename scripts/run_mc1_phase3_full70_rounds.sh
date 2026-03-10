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
ROUND_LIMIT="${ROUND_LIMIT:-3}"          # user requested: 3 combos per round
TARGET_COMBOS="${TARGET_COMBOS:-12}"     # full70 grid = 3(q) * 2(sev) * 2(rule)
MAX_ROUNDS="${MAX_ROUNDS:-10}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_mc1_full70_rounds}"
SUMMARY_CSV="${SUMMARY_CSV:-$ROOT/docs/prearff_grid_mc1_full70_v1.csv}"
SUMMARY_MD="${SUMMARY_MD:-$ROOT/docs/prearff_grid_mc1_full70_v1.md}"
mkdir -p "$STATE_DIR"

count_done() {
  find "$ROOT/mc1_mlp" -maxdepth 1 -type f \
    -name "phase3_mc1_full70_*_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${RUN_TAG}_i${SIM_ITER_DAYS}.csv" \
    | wc -l
}

cleanup_round_artifacts() {
  rm -f "$ROOT"/save_model/mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".pickle || true
  rm -rf "$ROOT"/pyloader/phase3_train_mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -rf "$ROOT"/pyloader/phase3_test_mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG" || true
  rm -f "$ROOT"/llm/framework_v1_mc1/phase3_variants/mc1_full70_*_"$PHASE3_EXTRACT_MODE"_"$PHASE3_PROMPT_PROFILE"_"$RUN_TAG".jsonl || true
}

echo "[full70_rounds] start mode=$PHASE3_EXTRACT_MODE profile=$PHASE3_PROMPT_PROFILE tag=$RUN_TAG"
echo "[full70_rounds] round_limit=$ROUND_LIMIT target_combos=$TARGET_COMBOS max_rounds=$MAX_ROUNDS"
df -h /root/autodl-tmp | sed -n '1,2p'

prev_done=-1
round=0
while true; do
  done_now="$(count_done)"
  if [[ "$done_now" -ge "$TARGET_COMBOS" ]]; then
    echo "[full70_rounds] done all combos: $done_now/$TARGET_COMBOS"
    break
  fi
  if [[ "$round" -ge "$MAX_ROUNDS" ]]; then
    echo "[full70_rounds] hit MAX_ROUNDS=$MAX_ROUNDS, stop with done=$done_now"
    break
  fi
  if [[ "$done_now" -eq "$prev_done" && "$round" -gt 0 ]]; then
    echo "[full70_rounds] no progress since last round (done=$done_now), stop to avoid endless retry"
    break
  fi

  round=$((round + 1))
  prev_done="$done_now"
  round_ts="$(date -u +%Y%m%dT%H%M%SZ)"
  round_log="$STATE_DIR/round_${round}_${round_ts}.log"
  echo "[full70_rounds] round=$round begin done=$done_now/$TARGET_COMBOS log=$round_log"

  if ! stdbuf -oL -eL env \
    PHASE3_EXTRACT_MODE="$PHASE3_EXTRACT_MODE" \
    PHASE3_PROMPT_PROFILE="$PHASE3_PROMPT_PROFILE" \
    PHASE3_DIM_KEYS="full70" \
    PHASE3_COMBO_LIMIT="$ROUND_LIMIT" \
    CONTINUE_ON_ERROR=1 \
    RUN_TAG="$RUN_TAG" \
    JAVA_XMX="$JAVA_XMX" \
    SIM_ITER_DAYS="$SIM_ITER_DAYS" \
    KEEP_ARFF=0 \
    KEEP_VARIANT=0 \
    STATE_DIR="$STATE_DIR" \
    SUMMARY_CSV="$SUMMARY_CSV" \
    SUMMARY_MD="$SUMMARY_MD" \
    bash "$ROOT/scripts/run_framework_v1_phase3_grid_mc1.sh" > "$round_log" 2>&1; then
    echo "[full70_rounds] WARN round=$round returned non-zero; continue to cleanup and next round"
  fi

  done_after="$(count_done)"
  echo "[full70_rounds] round=$round end done=$done_after/$TARGET_COMBOS"

  echo "[full70_rounds] cleanup intermediates after round=$round"
  cleanup_round_artifacts
  df -h /root/autodl-tmp | sed -n '1,2p'
done

echo "[full70_rounds] finish"
