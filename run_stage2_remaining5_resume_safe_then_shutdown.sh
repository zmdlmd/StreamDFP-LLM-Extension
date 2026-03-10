#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
MAPPING_DIR="$ROOT/llm/event_mappings/models_7_20140901_20141109"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# OOM-safe profile (resume run).
SAFE_BATCH_SIZE=96
SAFE_MAX_BATCHED_TOKENS=24576
SAFE_MAX_MODEL_LEN=4096
SAFE_GPU_MEM_UTIL=0.90
SAFE_MAX_NEW_TOKENS=140

# Conservative fallback if safe profile still fails.
FALLBACK_BATCH_SIZE=64
FALLBACK_MAX_BATCHED_TOKENS=16384
FALLBACK_MAX_MODEL_LEN=4096
FALLBACK_GPU_MEM_UTIL=0.90
FALLBACK_MAX_NEW_TOKENS=128

TOP_P=0.9
TEMPERATURE=0
FLUSH_EVERY=2048
LOG_EVERY_BATCHES=50
RULE_SCORE_GATE=0.8

RUN_TS="$(date +%Y%m%d_%H%M%S)"
SUMMARY_TSV="$LOG_DIR/stage2_remaining5_resume_safe_summary_${RUN_TS}.tsv"

# Remaining 5 models in small->large order.
MODELS=(
  "hds723030ala640"
  "st31500541as"
  "hms5c4040ble640"
  "hds5c3030ala630"
  "st4000dm000"
)

echo -e "model\tmode\tstatus\trows\tsize\tprofile\tcache_path" > "$SUMMARY_TSV"
echo "[resume] start at $(date '+%F %T')"
echo "[resume] summary => $SUMMARY_TSV"
echo "[resume] queue => ${MODELS[*]}"

# Reduce fragmentation risk for long vLLM runs.
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

resolve_mapping() {
  local model_key="$1"
  local direct="$MAPPING_DIR/event_mapping_${model_key}.yaml"
  if [[ -f "$direct" ]]; then
    echo "$direct"
    return 0
  fi
  local candidates=("$MAPPING_DIR"/event_mapping_*"${model_key}".yaml)
  if [[ -f "${candidates[0]:-}" ]]; then
    echo "${candidates[0]}"
    return 0
  fi
  return 1
}

count_lines() {
  wc -l < "$1" | tr -d ' '
}

run_extract_once() {
  local model_key="$1"
  local mode="$2"
  local fewshot_mode="$3"
  local out_path="$4"
  local map_path="$5"
  local batch_size="$6"
  local max_tokens="$7"
  local model_len="$8"
  local gpu_util="$9"
  local max_new="${10}"
  local run_tag="${11}"

  local window_path="$ROOT/llm/window_text_${model_key}_20140901_20141109.jsonl"
  local ref_path="$ROOT/llm/reference_examples_${model_key}_0803_0831.json"

  rm -f "$out_path"
  echo "[resume][$model_key][$mode][$run_tag] start => $(date '+%F %T')"
  TIMEFORMAT='[resume]['"$model_key"']['"$mode"']['"$run_tag"'] elapsed=%3R sec'
  time python llm/llm_offline_extract.py \
    --window_text_path "$window_path" \
    --reference_examples "$ref_path" \
    --out "$out_path" \
    --model "$MODEL_PATH" \
    --batch_size "$batch_size" \
    --backend vllm \
    --vllm_max_model_len "$model_len" \
    --vllm_gpu_memory_utilization "$gpu_util" \
    --vllm_max_num_batched_tokens "$max_tokens" \
    --event_mapping_config "$map_path" \
    --max_new_tokens "$max_new" \
    --temperature "$TEMPERATURE" \
    --top_p "$TOP_P" \
    --flush_every "$FLUSH_EVERY" \
    --log_every_batches "$LOG_EVERY_BATCHES" \
    --fewshot_mode "$fewshot_mode" \
    --fewshot_min_per_cause 1 \
    --rule_score_gate "$RULE_SCORE_GATE" \
    --write_root_cause_pred
}

process_one() {
  local model_key="$1"
  local mode="$2"
  local fewshot_mode="$3"

  local window_path="$ROOT/llm/window_text_${model_key}_20140901_20141109.jsonl"
  local ref_path="$ROOT/llm/reference_examples_${model_key}_0803_0831.json"
  local out_path="$ROOT/llm_cache_${model_key}_${mode}_20140901_20141109_compare_map70.jsonl"
  local map_path

  if [[ ! -f "$window_path" ]]; then
    echo "[resume][ERROR] missing window_text: $window_path" >&2
    exit 1
  fi
  if [[ ! -f "$ref_path" ]]; then
    echo "[resume][ERROR] missing reference_examples: $ref_path" >&2
    exit 1
  fi
  map_path="$(resolve_mapping "$model_key")" || {
    echo "[resume][ERROR] missing event mapping for ${model_key}" >&2
    exit 1
  }

  local total existing
  total="$(count_lines "$window_path")"
  if [[ -f "$out_path" ]]; then
    existing="$(count_lines "$out_path")"
  else
    existing=0
  fi

  if [[ "$existing" -eq "$total" ]]; then
    local size_h
    size_h="$(du -sh "$out_path" | awk '{print $1}')"
    echo -e "${model_key}\t${mode}\tskip_complete\t${existing}\t${size_h}\t-\t${out_path}" >> "$SUMMARY_TSV"
    echo "[resume][$model_key][$mode] skip (already complete: ${existing}/${total})"
    return 0
  fi

  if [[ "$existing" -gt 0 ]]; then
    echo "[resume][$model_key][$mode] removing partial cache ${existing}/${total}: $out_path"
    rm -f "$out_path"
  fi

  if run_extract_once "$model_key" "$mode" "$fewshot_mode" "$out_path" "$map_path" \
      "$SAFE_BATCH_SIZE" "$SAFE_MAX_BATCHED_TOKENS" "$SAFE_MAX_MODEL_LEN" "$SAFE_GPU_MEM_UTIL" "$SAFE_MAX_NEW_TOKENS" "safe"; then
    :
  else
    echo "[resume][$model_key][$mode] safe profile failed, retry with fallback profile"
    run_extract_once "$model_key" "$mode" "$fewshot_mode" "$out_path" "$map_path" \
      "$FALLBACK_BATCH_SIZE" "$FALLBACK_MAX_BATCHED_TOKENS" "$FALLBACK_MAX_MODEL_LEN" "$FALLBACK_GPU_MEM_UTIL" "$FALLBACK_MAX_NEW_TOKENS" "fallback"
    local rows size_h
    rows="$(count_lines "$out_path")"
    size_h="$(du -sh "$out_path" | awk '{print $1}')"
    echo -e "${model_key}\t${mode}\tok\t${rows}\t${size_h}\tfallback\t${out_path}" >> "$SUMMARY_TSV"
    echo "[resume][$model_key][$mode] done rows=${rows}/${total} size=${size_h} profile=fallback"
    return 0
  fi

  local rows size_h
  rows="$(count_lines "$out_path")"
  size_h="$(du -sh "$out_path" | awk '{print $1}')"
  echo -e "${model_key}\t${mode}\tok\t${rows}\t${size_h}\tsafe\t${out_path}" >> "$SUMMARY_TSV"
  echo "[resume][$model_key][$mode] done rows=${rows}/${total} size=${size_h} profile=safe"
}

for model_key in "${MODELS[@]}"; do
  process_one "$model_key" "fs" "force"
  process_one "$model_key" "zs" "off"
done

echo "[resume] all jobs finished at $(date '+%F %T')"
echo "[resume] final summary:"
cat "$SUMMARY_TSV"
sync

echo "[resume] triggering shutdown at $(date '+%F %T')"
shutdown -h now || /sbin/poweroff || halt -p
