#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
BATCH_SIZE="${BATCH_SIZE:-64}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/framework_v1}"
mkdir -p "$LOG_DIR" "$ROOT/llm/framework_v1"

map_cfg_for() {
  case "$1" in
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

keys=(
  hgsthms5c4040ale640
  st31500341as
  hitachihds5c4040ale630
  wdcwd30efrx
  wdcwd10eads
  st4000dm000
  hds5c3030ala630
)

idx=0
total=${#keys[@]}
for key in "${keys[@]}"; do
  idx=$((idx + 1))
  out="$ROOT/llm/framework_v1/cache_${key}_zs_structured_v2_pilot20k.jsonl"
  win="$ROOT/llm/window_text_${key}_20140901_20141109.jsonl"
  ref="$ROOT/llm/reference_examples_${key}_0803_0831.json"
  map_cfg="$(map_cfg_for "$key")"
  per_log="$LOG_DIR/phase2_${key}_zs_structured_v2_pilot20k.log"

  rows=0
  if [[ -f "$out" ]]; then
    rows=$(wc -l < "$out")
  fi
  if [[ "$rows" -ge "$MAX_WINDOWS" ]]; then
    echo "[SKIP][$idx/$total] $(date -Is) key=$key rows=$rows"
    continue
  fi

  echo "[START][$idx/$total] $(date -Is) key=$key rows=$rows"
  stdbuf -oL -eL python "$ROOT/llm/llm_offline_extract.py" \
    --window_text_path "$win" \
    --reference_examples "$ref" \
    --out "$out" \
    --model "$MODEL_PATH" \
    --backend vllm \
    --batch_size "$BATCH_SIZE" \
    --vllm_gpu_memory_utilization 0.92 \
    --vllm_max_model_len 4096 \
    --vllm_max_num_batched_tokens 16384 \
    --max_new_tokens 160 \
    --temperature 0 \
    --top_p 0.9 \
    --fewshot_mode off \
    --fewshot_min_per_cause 1 \
    --prompt_profile structured_v2 \
    --rule_blend_mode three_stage \
    --event_type_policy strict \
    --rule_score_gate 0.8 \
    --event_mapping_config "$map_cfg" \
    --enforce_event_feature_whitelist \
    --emit_quality_meta \
    --max_windows "$MAX_WINDOWS" \
    --flush_every 2048 \
    --log_every_batches 50 \
    --write_root_cause_pred \
    --show_progress \
    > "$per_log" 2>&1

  rows=$(wc -l < "$out")
  size=$(du -h "$out" | awk '{print $1}')
  echo "[DONE][$idx/$total] $(date -Is) key=$key rows=$rows size=$size"
done

echo "[ALL DONE] $(date -Is) batch7 phase2 zs reliable"
