#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
MAPPING_DIR="$ROOT/llm/event_mappings/models_7_20140901_20141109"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# Tuned params from recent benchmark (throughput-oriented).
BATCH_SIZE=128
VLLM_MAX_BATCHED_TOKENS=32768
VLLM_MAX_MODEL_LEN=4096
VLLM_GPU_MEMORY_UTILIZATION=0.92
MAX_NEW_TOKENS=160
TOP_P=0.9
TEMPERATURE=0
FLUSH_EVERY=2048
LOG_EVERY_BATCHES=50
RULE_SCORE_GATE=0.8

RUN_TS="$(date +%Y%m%d_%H%M%S)"
SUMMARY_TSV="$LOG_DIR/stage2_remaining5_fs_zs_summary_${RUN_TS}.tsv"

# Remaining 5 models in small->large order by stage1 window count.
MODELS=(
  "hds723030ala640"
  "st31500541as"
  "hms5c4040ble640"
  "hds5c3030ala630"
  "st4000dm000"
)

echo -e "model\tmode\trows\tsize\tcache_path" > "$SUMMARY_TSV"
echo "[stage2] start at $(date '+%F %T')"
echo "[stage2] summary => $SUMMARY_TSV"
echo "[stage2] queue => ${MODELS[*]}"

run_extract() {
  local model_key="$1"
  local mode="$2"
  local fewshot_mode="$3"
  local out_path="$4"

  local window_path="$ROOT/llm/window_text_${model_key}_20140901_20141109.jsonl"
  local ref_path="$ROOT/llm/reference_examples_${model_key}_0803_0831.json"
  local map_path="$MAPPING_DIR/event_mapping_${model_key}.yaml"

  if [[ ! -f "$window_path" ]]; then
    echo "[stage2][ERROR] missing window_text: $window_path" >&2
    exit 1
  fi
  if [[ ! -f "$ref_path" ]]; then
    echo "[stage2][ERROR] missing reference_examples: $ref_path" >&2
    exit 1
  fi
  if [[ ! -f "$map_path" ]]; then
    # Fallback for vendor-prefixed mapping names, e.g. event_mapping_hitachi_hds5c3030ala630.yaml
    local candidates=("$MAPPING_DIR"/event_mapping_*"${model_key}".yaml)
    if [[ -f "${candidates[0]:-}" ]]; then
      map_path="${candidates[0]}"
    fi
  fi
  if [[ ! -f "$map_path" ]]; then
    echo "[stage2][ERROR] missing event mapping: $map_path" >&2
    exit 1
  fi

  rm -f "$out_path"

  echo "[stage2][$model_key][$mode] start => $(date '+%F %T')"
  TIMEFORMAT='[stage2]['"$model_key"']['"$mode"'] elapsed=%3R sec'
  time python llm/llm_offline_extract.py \
    --window_text_path "$window_path" \
    --reference_examples "$ref_path" \
    --out "$out_path" \
    --model "$MODEL_PATH" \
    --batch_size "$BATCH_SIZE" \
    --backend vllm \
    --vllm_max_model_len "$VLLM_MAX_MODEL_LEN" \
    --vllm_gpu_memory_utilization "$VLLM_GPU_MEMORY_UTILIZATION" \
    --vllm_max_num_batched_tokens "$VLLM_MAX_BATCHED_TOKENS" \
    --event_mapping_config "$map_path" \
    --max_new_tokens "$MAX_NEW_TOKENS" \
    --temperature "$TEMPERATURE" \
    --top_p "$TOP_P" \
    --flush_every "$FLUSH_EVERY" \
    --log_every_batches "$LOG_EVERY_BATCHES" \
    --fewshot_mode "$fewshot_mode" \
    --fewshot_min_per_cause 1 \
    --rule_score_gate "$RULE_SCORE_GATE" \
    --write_root_cause_pred

  local rows size_h
  rows="$(wc -l < "$out_path" | tr -d ' ')"
  size_h="$(du -sh "$out_path" | awk '{print $1}')"
  echo -e "${model_key}\t${mode}\t${rows}\t${size_h}\t${out_path}" >> "$SUMMARY_TSV"
  echo "[stage2][$model_key][$mode] done rows=${rows} size=${size_h}"
}

for model_key in "${MODELS[@]}"; do
  fs_out="$ROOT/llm_cache_${model_key}_fs_20140901_20141109_compare_map70.jsonl"
  zs_out="$ROOT/llm_cache_${model_key}_zs_20140901_20141109_compare_map70.jsonl"

  run_extract "$model_key" "fs" "force" "$fs_out"
  run_extract "$model_key" "zs" "off" "$zs_out"
done

echo "[stage2] all jobs finished at $(date '+%F %T')"
echo "[stage2] final summary:"
cat "$SUMMARY_TSV"
sync

echo "[stage2] triggering shutdown at $(date '+%F %T')"
shutdown -h now || /sbin/poweroff || halt -p
