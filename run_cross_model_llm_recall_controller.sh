#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
HOOK_DIR="$ROOT/scripts/controller_hooks"
STATE_DIR="$ROOT/logs/cross_model_controller"
REPORT_CSV="$ROOT/docs/llm_robust_eval_report_v2.csv"
REPORT_MD="$ROOT/docs/llm_robust_eval_report_v2.md"

# Defaults (override by CLI args).
MODELS=("hi7" "hds723030ala640" "st3000dm001" "hms5c4040ble640" "st31500541as")
DRY_RUN=1
MAX_ROUNDS=5
MIN_FREE_GB=10
MAX_MODEL_FAILURES=2
MAX_NO_PROGRESS_ROUNDS=2
SLEEP_BETWEEN_ROUNDS=15

mkdir -p "$STATE_DIR"

usage() {
  cat <<'EOF'
Usage:
  run_cross_model_llm_recall_controller.sh [options]

Options:
  --execute                    Actually run hook scripts (default: dry-run).
  --models a,b,c               Target model keys (default: hi7,hds723030ala640,st3000dm001,hms5c4040ble640,st31500541as).
  --max-rounds N               Max tuning rounds (default: 5).
  --min-free-gb N              Stop if free disk < N GB (default: 10).
  --max-model-failures N       Per-model failure threshold (default: 2).
  --max-no-progress-rounds N   Stop if PASS count unchanged for N rounds (default: 2).
  --sleep-seconds N            Sleep between rounds (default: 15).
  -h, --help                   Show this message.

Hook convention:
  scripts/controller_hooks/
    quality_report.sh
    policy_grid_<model>.sh
    microgrid_<model>.sh
    rerun_extract_<model>.sh
    policy_lock_<model>.sh

Each hook receives:
  $1=model_key  $2=round_index  $3=root_path
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      DRY_RUN=0
      shift
      ;;
    --models)
      IFS=',' read -r -a MODELS <<< "${2:-}"
      shift 2
      ;;
    --max-rounds)
      MAX_ROUNDS="${2:-5}"
      shift 2
      ;;
    --min-free-gb)
      MIN_FREE_GB="${2:-10}"
      shift 2
      ;;
    --max-model-failures)
      MAX_MODEL_FAILURES="${2:-2}"
      shift 2
      ;;
    --max-no-progress-rounds)
      MAX_NO_PROGRESS_ROUNDS="${2:-2}"
      shift 2
      ;;
    --sleep-seconds)
      SLEEP_BETWEEN_ROUNDS="${2:-15}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

log() {
  echo "[$(date '+%F %T')] $*"
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] $*"
    return 0
  fi
  "$@"
}

free_gb() {
  df -BG /root/autodl-tmp | awk 'NR==2 {gsub("G","",$4); print $4+0}'
}

check_disk_guard() {
  local free
  free="$(free_gb)"
  log "disk free: ${free}G (guard >= ${MIN_FREE_GB}G)"
  if (( free < MIN_FREE_GB )); then
    log "STOP: disk guard triggered"
    return 1
  fi
  return 0
}

run_preflight() {
  log "stage: preflight"
  if ! nvidia-smi >/dev/null 2>&1; then
    log "STOP: nvidia-smi failed, GPU unavailable"
    return 1
  fi
  check_disk_guard
}

run_final_report() {
  log "stage: final_report"
  run_cmd "$ROOT/run_robust_eval_report_v2.sh"
}

hook_path() {
  local stage="$1"
  local model="$2"
  if [[ -x "$HOOK_DIR/${stage}_${model}.sh" ]]; then
    echo "$HOOK_DIR/${stage}_${model}.sh"
    return 0
  fi
  if [[ -x "$HOOK_DIR/${stage}.sh" ]]; then
    echo "$HOOK_DIR/${stage}.sh"
    return 0
  fi
  return 1
}

run_hook() {
  local stage="$1"
  local model="$2"
  local round="$3"
  local hook
  if ! hook="$(hook_path "$stage" "$model")"; then
    log "hook missing: stage=$stage model=$model (skip)"
    return 0
  fi
  log "stage: $stage model=$model hook=$hook"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] $hook $model $round $ROOT"
    return 0
  fi
  "$hook" "$model" "$round" "$ROOT"
}

model_status() {
  local model="$1"
  if [[ ! -f "$REPORT_CSV" ]]; then
    echo ""
    return 0
  fi
  awk -F, -v m="$model" '$1==m {print $2; found=1; exit} END{if(!found) print ""}' "$REPORT_CSV"
}

pass_count() {
  if [[ ! -f "$REPORT_CSV" ]]; then
    echo 0
    return 0
  fi
  awk -F, 'NR>1 && $2=="PASS" {c++} END{print c+0}' "$REPORT_CSV"
}

all_models_done() {
  local model status
  for model in "${MODELS[@]}"; do
    status="$(model_status "$model")"
    if [[ "$status" != "PASS" && "$status" != "N/A" ]]; then
      return 1
    fi
  done
  return 0
}

print_status_snapshot() {
  local model status
  log "status snapshot:"
  for model in "${MODELS[@]}"; do
    status="$(model_status "$model")"
    [[ -z "$status" ]] && status="UNKNOWN"
    log "  - $model => $status"
  done
}

declare -A FAIL_COUNT
for m in "${MODELS[@]}"; do
  FAIL_COUNT["$m"]=0
done

NO_PROGRESS_ROUNDS=0
PREV_PASS=-1

log "controller start (dry_run=$DRY_RUN, models=${MODELS[*]})"

for (( round=1; round<=MAX_ROUNDS; round++ )); do
  log "========== round $round / $MAX_ROUNDS =========="

  run_preflight || exit 2

  run_hook "quality_report" "__global__" "$round" || true
  run_final_report || true
  print_status_snapshot

  for model in "${MODELS[@]}"; do
    check_disk_guard || exit 3
    status="$(model_status "$model")"

    if [[ "$status" == "PASS" || "$status" == "N/A" ]]; then
      log "skip model=$model (status=$status)"
      continue
    fi

    if (( FAIL_COUNT["$model"] >= MAX_MODEL_FAILURES )); then
      log "skip model=$model (failure cap reached: ${FAIL_COUNT[$model]})"
      continue
    fi

    # Stage 2: coarse policy grid
    if ! run_hook "policy_grid" "$model" "$round"; then
      FAIL_COUNT["$model"]=$(( FAIL_COUNT["$model"] + 1 ))
      log "model=$model policy_grid failed (count=${FAIL_COUNT[$model]})"
      continue
    fi
    run_final_report || true
    status="$(model_status "$model")"
    [[ "$status" == "PASS" || "$status" == "N/A" ]] && run_hook "policy_lock" "$model" "$round" || true
    if [[ "$status" == "PASS" || "$status" == "N/A" ]]; then
      continue
    fi

    # Stage 3: micro-grid near boundary
    if ! run_hook "microgrid" "$model" "$round"; then
      FAIL_COUNT["$model"]=$(( FAIL_COUNT["$model"] + 1 ))
      log "model=$model microgrid failed (count=${FAIL_COUNT[$model]})"
      continue
    fi
    run_final_report || true
    status="$(model_status "$model")"
    [[ "$status" == "PASS" || "$status" == "N/A" ]] && run_hook "policy_lock" "$model" "$round" || true
    if [[ "$status" == "PASS" || "$status" == "N/A" ]]; then
      continue
    fi

    # Stage 4: targeted re-extract (optional heavy path)
    if ! run_hook "rerun_extract" "$model" "$round"; then
      FAIL_COUNT["$model"]=$(( FAIL_COUNT["$model"] + 1 ))
      log "model=$model rerun_extract failed (count=${FAIL_COUNT[$model]})"
      continue
    fi

    # After re-extract, rerun policy grid + microgrid once.
    run_hook "policy_grid" "$model" "$round" || true
    run_hook "microgrid" "$model" "$round" || true
    run_final_report || true
    status="$(model_status "$model")"
    [[ "$status" == "PASS" || "$status" == "N/A" ]] && run_hook "policy_lock" "$model" "$round" || true
  done

  run_final_report || true
  print_status_snapshot

  CUR_PASS="$(pass_count)"
  if (( PREV_PASS >= 0 )) && (( CUR_PASS <= PREV_PASS )); then
    NO_PROGRESS_ROUNDS=$(( NO_PROGRESS_ROUNDS + 1 ))
  else
    NO_PROGRESS_ROUNDS=0
  fi
  PREV_PASS="$CUR_PASS"

  log "round metrics: pass_count=$CUR_PASS no_progress_rounds=$NO_PROGRESS_ROUNDS"

  if all_models_done; then
    log "STOP: all target models are PASS/N/A; report ready at $REPORT_MD"
    exit 0
  fi

  if (( NO_PROGRESS_ROUNDS >= MAX_NO_PROGRESS_ROUNDS )); then
    log "STOP: no progress for $NO_PROGRESS_ROUNDS rounds"
    exit 4
  fi

  check_disk_guard || exit 3
  log "round $round done; sleep ${SLEEP_BETWEEN_ROUNDS}s"
  sleep "$SLEEP_BETWEEN_ROUNDS"
done

log "STOP: reached max rounds ($MAX_ROUNDS)"
exit 5
