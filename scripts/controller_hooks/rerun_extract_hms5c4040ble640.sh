#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_PARENT="$(cd "$DEFAULT_ROOT/.." && pwd)"
model="${1:-}"
round="${2:-0}"
root="${3:-$DEFAULT_ROOT}"

if [[ "$model" != "hms5c4040ble640" ]]; then
  echo "[hook][rerun_extract] skip model=$model"
  exit 0
fi

cd "$root"

window_path="llm/window_text_hms5c4040ble640_20140901_20141109.jsonl"
ref_path="llm/reference_examples_hms5c4040ble640_0803_0831.json"
out_cache="llm_cache_hms5c4040ble640_fs_robustv3_20140901_20141109.jsonl"
log_path="logs/hms5c4040ble640_rerun_extract_round${round}.log"
map_path="llm/event_mappings/models_7_20140901_20141109/event_mapping_hgst_hms5c4040ble640.yaml"
model_path="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"

for p in "$window_path" "$ref_path" "$map_path"; do
  if [[ ! -f "$p" ]]; then
    echo "[hook][rerun_extract] missing file: $p" >&2
    exit 2
  fi
done

total_rows="$(wc -l < "$window_path" | tr -d ' ')"
if [[ -f "$out_cache" ]]; then
  have_rows="$(wc -l < "$out_cache" | tr -d ' ')"
else
  have_rows=0
fi

if [[ "$have_rows" == "$total_rows" ]]; then
  echo "[hook][rerun_extract] cache already complete: $out_cache ($have_rows rows)"
  exit 0
fi

rm -f "$out_cache"
echo "[hook][rerun_extract] start round=$round -> $out_cache" | tee "$log_path"

TIMEFORMAT='ELAPSED_SEC=%3R'; {
  time python llm/llm_offline_extract.py \
    --window_text_path "$window_path" \
    --reference_examples "$ref_path" \
    --out "$out_cache" \
    --model "$model_path" \
    --backend vllm \
    --batch_size 128 \
    --vllm_max_model_len 4096 \
    --vllm_gpu_memory_utilization 0.92 \
    --vllm_max_num_batched_tokens 32768 \
    --max_new_tokens 160 \
    --temperature 0 \
    --top_p 0.9 \
    --fewshot_mode off \
    --rule_score_gate 0.45 \
    --rule_score_soft_gate 0.35 \
    --event_quality_gate 0.20 \
    --event_min_count 1 \
    --enforce_event_feature_whitelist \
    --emit_quality_meta \
    --event_mapping_config "$map_path" \
    --flush_every 2048 \
    --log_every_batches 50 \
    --write_root_cause_pred
} 2>&1 | tee -a "$log_path"

rows="$(wc -l < "$out_cache" | tr -d ' ')"
echo "[hook][rerun_extract] done rows=$rows/$total_rows" | tee -a "$log_path"

# Optional quick quality snapshot for this rerun cache.
python llm/scripts/build_model_quality_report.py \
  --cache_paths "$out_cache" \
  --window_text_paths "$window_path" \
  --out_dir "docs/model_quality_robustv3_round${round}" \
  --summary_csv "docs/model_quality_summary_robustv3_round${round}.csv" >/dev/null 2>&1 || true
