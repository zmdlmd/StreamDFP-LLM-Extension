#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
RUN_TAG="${RUN_TAG:-pilot20k_qwen35}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"
TARGET_KEYS="${TARGET_KEYS:-}"
BATCH_SIZE="${BATCH_SIZE:-8}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.80}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-3072}"
VLLM_MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-1024}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-128}"
RETRY1_BATCH_SIZE="${RETRY1_BATCH_SIZE:-4}"
RETRY1_VLLM_GPU_MEMORY_UTILIZATION="${RETRY1_VLLM_GPU_MEMORY_UTILIZATION:-0.78}"
RETRY1_VLLM_MAX_NUM_BATCHED_TOKENS="${RETRY1_VLLM_MAX_NUM_BATCHED_TOKENS:-768}"
RETRY1_MAX_NEW_TOKENS="${RETRY1_MAX_NEW_TOKENS:-128}"
RETRY2_BATCH_SIZE="${RETRY2_BATCH_SIZE:-8}"
RETRY2_VLLM_GPU_MEMORY_UTILIZATION="${RETRY2_VLLM_GPU_MEMORY_UTILIZATION:-0.82}"
RETRY2_VLLM_MAX_NUM_BATCHED_TOKENS="${RETRY2_VLLM_MAX_NUM_BATCHED_TOKENS:-1024}"
RETRY2_MAX_NEW_TOKENS="${RETRY2_MAX_NEW_TOKENS:-128}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-1}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/framework_v1}"
OUT_DIR="${OUT_DIR:-$ROOT/llm/framework_v1}"
SUMMARY_TSV="${SUMMARY_TSV:-}"
RULE_SCORE_GATE="${RULE_SCORE_GATE:-0.8}"
RULE_SCORE_SOFT_GATE="${RULE_SCORE_SOFT_GATE:-0.55}"
RULE_SCORE_GATE_OVERRIDES="${RULE_SCORE_GATE_OVERRIDES:-}"
RULE_SCORE_SOFT_GATE_OVERRIDES="${RULE_SCORE_SOFT_GATE_OVERRIDES:-}"

mkdir -p "$LOG_DIR" "$OUT_DIR"

RUN_TS="$(date +%Y%m%d_%H%M%S)"
if [[ -z "$SUMMARY_TSV" ]]; then
  SUMMARY_TSV="$LOG_DIR/phase2_all12_${RUN_TAG}_${RUN_TS}.tsv"
fi

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

resolve_target_keys() {
  if [[ -z "$TARGET_KEYS" ]]; then
    printf "%s\n" "${ALL_KEYS[@]}"
    return 0
  fi

  local -a raw
  local key item found
  IFS=',' read -r -a raw <<< "$TARGET_KEYS"
  if [[ ${#raw[@]} -eq 0 ]]; then
    echo "[phase2_all12] empty TARGET_KEYS after parsing: $TARGET_KEYS" >&2
    return 2
  fi

  for key in "${raw[@]}"; do
    found=0
    for item in "${ALL_KEYS[@]}"; do
      if [[ "$item" == "$key" ]]; then
        found=1
        break
      fi
    done
    if [[ "$found" != "1" ]]; then
      echo "[phase2_all12] unknown target key: $key" >&2
      return 2
    fi
  done

  printf "%s\n" "${raw[@]}"
}

resolve_rule_override() {
  local key="$1"
  local default_value="$2"
  local overrides="$3"
  local -a items
  local item override_key override_val

  if [[ -z "$overrides" ]]; then
    echo "$default_value"
    return 0
  fi

  IFS=',' read -r -a items <<< "$overrides"
  for item in "${items[@]}"; do
    override_key="${item%%=*}"
    override_val="${item#*=}"
    if [[ "$override_key" == "$key" && "$override_val" != "$item" && -n "$override_val" ]]; then
      echo "$override_val"
      return 0
    fi
  done

  echo "$default_value"
}

export LD_LIBRARY_PATH="/root/miniconda3/lib/python3.12/site-packages/torch/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
if ! [[ "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export OMP_NUM_THREADS=8
fi
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"

echo -e "model\tstatus\trows\texpected\tsize\tout_path\tlog_path\tattempt\tprofile" > "$SUMMARY_TSV"
echo "[phase2_all12] start $(date '+%F %T')"
echo "[phase2_all12] run_tag=$RUN_TAG summary=$SUMMARY_TSV"
echo "[phase2_all12] model_path=$MODEL_PATH"
echo "[phase2_all12] batch_size=$BATCH_SIZE max_windows=$MAX_WINDOWS max_model_len=$VLLM_MAX_MODEL_LEN max_batched_tokens=$VLLM_MAX_NUM_BATCHED_TOKENS max_new_tokens=$MAX_NEW_TOKENS"
echo "[phase2_all12] rule_score_gate=$RULE_SCORE_GATE rule_score_soft_gate=$RULE_SCORE_SOFT_GATE"
if [[ -n "$TARGET_KEYS" ]]; then
  echo "[phase2_all12] target_keys=$TARGET_KEYS"
fi

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
    echo "$OUT_DIR/window_text_${key}_pilot20k.jsonl"
  else
    echo "$OUT_DIR/window_text_${key}_pilot20000.jsonl"
  fi
}

reference_path_for() {
  local key="$1"
  if is_core_key "$key"; then
    echo "$OUT_DIR/reference_${key}_pilot20k.json"
  else
    echo "$ROOT/llm/reference_examples_${key}_0803_0831.json"
  fi
}

mapping_path_for() {
  local key="$1"
  case "$key" in
    hi7) echo "$ROOT/llm/event_mapping_hi7.yaml" ;;
    hds723030ala640) echo "$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_hitachi_hds723030ala640.yaml" ;;
    st3000dm001) echo "$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_st3000dm001.yaml" ;;
    hms5c4040ble640) echo "$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_hgst_hms5c4040ble640.yaml" ;;
    st31500541as) echo "$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_st31500541as.yaml" ;;
    hgsthms5c4040ale640) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hgst_hms5c4040ale640.yaml" ;;
    st31500341as) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_st31500341as.yaml" ;;
    hitachihds5c4040ale630) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hitachi_hds5c4040ale630.yaml" ;;
    wdcwd30efrx) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_wdc_wd30efrx.yaml" ;;
    wdcwd10eads) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_wdc_wd10eads.yaml" ;;
    st4000dm000) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_st4000dm000.yaml" ;;
    hds5c3030ala630) echo "$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hitachi_hds5c3030ala630.yaml" ;;
    *) return 1 ;;
  esac
}

expected_rows_for() {
  local win="$1"
  local rows
  rows="$(wc -l < "$win" | tr -d ' ')"
  if [[ "$MAX_WINDOWS" != "0" && "$rows" -gt "$MAX_WINDOWS" ]]; then
    rows="$MAX_WINDOWS"
  fi
  echo "$rows"
}

profile_values_for() {
  local attempt="$1"
  case "$attempt" in
    1)
      PROFILE_NAME="normal_primary"
      PROFILE_BATCH_SIZE="$BATCH_SIZE"
      PROFILE_GPU_UTIL="$VLLM_GPU_MEMORY_UTILIZATION"
      PROFILE_MAX_BATCHED="$VLLM_MAX_NUM_BATCHED_TOKENS"
      PROFILE_MAX_NEW="$MAX_NEW_TOKENS"
      PROFILE_ENFORCE_EAGER="0"
      ;;
    2)
      PROFILE_NAME="normal_retry1"
      PROFILE_BATCH_SIZE="$RETRY1_BATCH_SIZE"
      PROFILE_GPU_UTIL="$RETRY1_VLLM_GPU_MEMORY_UTILIZATION"
      PROFILE_MAX_BATCHED="$RETRY1_VLLM_MAX_NUM_BATCHED_TOKENS"
      PROFILE_MAX_NEW="$RETRY1_MAX_NEW_TOKENS"
      PROFILE_ENFORCE_EAGER="0"
      ;;
    3)
      PROFILE_NAME="eager_fallback"
      PROFILE_BATCH_SIZE="$RETRY2_BATCH_SIZE"
      PROFILE_GPU_UTIL="$RETRY2_VLLM_GPU_MEMORY_UTILIZATION"
      PROFILE_MAX_BATCHED="$RETRY2_VLLM_MAX_NUM_BATCHED_TOKENS"
      PROFILE_MAX_NEW="$RETRY2_MAX_NEW_TOKENS"
      PROFILE_ENFORCE_EAGER="1"
      ;;
    *)
      return 1
      ;;
  esac
}

run_attempt() {
  local key="$1"
  local win="$2"
  local ref="$3"
  local map_cfg="$4"
  local out="$5"
  local log_path="$6"
  local attempt="$7"
  local existing="$8"
  local rule_score_gate_local rule_score_soft_gate_local

  rule_score_gate_local="$(resolve_rule_override "$key" "$RULE_SCORE_GATE" "$RULE_SCORE_GATE_OVERRIDES")"
  rule_score_soft_gate_local="$(resolve_rule_override "$key" "$RULE_SCORE_SOFT_GATE" "$RULE_SCORE_SOFT_GATE_OVERRIDES")"

  profile_values_for "$attempt"
  {
    echo "[phase2_all12][ATTEMPT] $(date '+%F %T') key=$key attempt=$attempt profile=$PROFILE_NAME existing=$existing batch_size=$PROFILE_BATCH_SIZE gpu_util=$PROFILE_GPU_UTIL max_batched_tokens=$PROFILE_MAX_BATCHED max_new_tokens=$PROFILE_MAX_NEW rule_score_gate=$rule_score_gate_local rule_score_soft_gate=$rule_score_soft_gate_local"
  } >> "$log_path"

  local -a cmd=(
    python "$ROOT/llm/llm_offline_extract.py"
    --window_text_path "$win"
    --reference_examples "$ref"
    --out "$out"
    --model "$MODEL_PATH"
    --backend vllm
    --batch_size "$PROFILE_BATCH_SIZE"
    --vllm_gpu_memory_utilization "$PROFILE_GPU_UTIL"
    --vllm_max_model_len "$VLLM_MAX_MODEL_LEN"
    --vllm_max_num_batched_tokens "$PROFILE_MAX_BATCHED"
    --max_new_tokens "$PROFILE_MAX_NEW"
    --temperature 0
    --top_p 0.9
    --fewshot_mode off
    --fewshot_min_per_cause 1
    --prompt_profile structured_v2
    --rule_blend_mode three_stage
    --event_type_policy strict
    --rule_score_gate "$rule_score_gate_local"
    --rule_score_soft_gate "$rule_score_soft_gate_local"
    --event_mapping_config "$map_cfg"
    --enforce_event_feature_whitelist
    --emit_quality_meta
    --flush_every 512
    --log_every_batches 20
    --write_root_cause_pred
    --show_progress
  )
  if [[ "$PROFILE_ENFORCE_EAGER" == "1" ]]; then
    cmd+=(--vllm_enforce_eager)
  fi
  if [[ "$MAX_WINDOWS" != "0" ]]; then
    cmd+=(--max_windows "$MAX_WINDOWS")
  fi

  stdbuf -oL -eL "${cmd[@]}" >> "$log_path" 2>&1
}

run_one() {
  local key="$1"
  local win ref map_cfg out log_path expected existing size attempt
  win="$(window_path_for "$key")"
  ref="$(reference_path_for "$key")"
  map_cfg="$(mapping_path_for "$key")"
  out="$OUT_DIR/cache_${key}_zs_structured_v2_${RUN_TAG}.jsonl"
  log_path="$LOG_DIR/phase2_${key}_zs_structured_v2_${RUN_TAG}.log"

  [[ -s "$win" ]] || {
    echo "[phase2_all12][ERROR] missing window_text: $win"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "missing_window" "0" "0" "0" "$out" "$log_path" "0" "n/a" >> "$SUMMARY_TSV"
    return 1
  }
  [[ -s "$ref" ]] || {
    echo "[phase2_all12][ERROR] missing reference: $ref"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "missing_reference" "0" "0" "0" "$out" "$log_path" "0" "n/a" >> "$SUMMARY_TSV"
    return 1
  }
  [[ -s "$map_cfg" ]] || {
    echo "[phase2_all12][ERROR] missing mapping: $map_cfg"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "missing_mapping" "0" "0" "0" "$out" "$log_path" "0" "n/a" >> "$SUMMARY_TSV"
    return 1
  }

  expected="$(expected_rows_for "$win")"
  existing=0
  if [[ -f "$out" ]]; then
    existing="$(wc -l < "$out" | tr -d ' ')"
  fi

  if [[ "$existing" -ge "$expected" && "$expected" -gt 0 ]]; then
    size="$(du -h "$out" | awk '{print $1}')"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "skip_complete" "$existing" "$expected" "$size" "$out" "$log_path" "0" "existing" >> "$SUMMARY_TSV"
    echo "[phase2_all12][SKIP] key=$key rows=$existing/$expected"
    return 0
  fi

  echo "[phase2_all12][START] $(date '+%F %T') key=$key existing=$existing expected=$expected"
  : > "$log_path"

  for attempt in 1 2 3; do
    existing=0
    if [[ -f "$out" ]]; then
      existing="$(wc -l < "$out" | tr -d ' ')"
    fi
    if [[ "$existing" -ge "$expected" && "$expected" -gt 0 ]]; then
      profile_values_for "$attempt"
      size="$(du -h "$out" | awk '{print $1}')"
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "ok" "$existing" "$expected" "$size" "$out" "$log_path" "$((attempt-1))" "existing_after_retry" >> "$SUMMARY_TSV"
      echo "[phase2_all12][DONE] $(date '+%F %T') key=$key rows=$existing/$expected size=$size"
      return 0
    fi

    if run_attempt "$key" "$win" "$ref" "$map_cfg" "$out" "$log_path" "$attempt" "$existing"; then
      existing="$(wc -l < "$out" | tr -d ' ')"
      size="$(du -h "$out" | awk '{print $1}')"
      profile_values_for "$attempt"
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "ok" "$existing" "$expected" "$size" "$out" "$log_path" "$attempt" "$PROFILE_NAME" >> "$SUMMARY_TSV"
      echo "[phase2_all12][DONE] $(date '+%F %T') key=$key rows=$existing/$expected size=$size attempt=$attempt profile=$PROFILE_NAME"
      return 0
    fi

    existing=0
    if [[ -f "$out" ]]; then
      existing="$(wc -l < "$out" | tr -d ' ')"
    fi
    profile_values_for "$attempt"
    echo "[phase2_all12][RETRY] $(date '+%F %T') key=$key attempt=$attempt profile=$PROFILE_NAME rows=$existing/$expected"
    sleep 3
  done

  existing=0
  if [[ -f "$out" ]]; then
    existing="$(wc -l < "$out" | tr -d ' ')"
    size="$(du -h "$out" | awk '{print $1}')"
  else
    size="0"
  fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$key" "failed_after_retry" "$existing" "$expected" "$size" "$out" "$log_path" "3" "retry2" >> "$SUMMARY_TSV"
  echo "[phase2_all12][FAIL] $(date '+%F %T') key=$key rows=$existing/$expected log=$log_path"
  return 1
}

fail_count=0
mapfile -t selected_keys < <(resolve_target_keys)
for key in "${selected_keys[@]}"; do
  if ! run_one "$key"; then
    fail_count=$((fail_count + 1))
  fi
done

echo "[phase2_all12] finished $(date '+%F %T') fail_count=$fail_count"
echo "[phase2_all12] summary => $SUMMARY_TSV"
sync

if [[ "$AUTO_SHUTDOWN" == "1" ]]; then
  echo "[phase2_all12] all 12 models processed, shutting down (fail_count=$fail_count)"
  shutdown -h now || /sbin/poweroff || halt -p
fi

if [[ "$fail_count" -eq 0 ]]; then
  exit 0
fi
exit 1
