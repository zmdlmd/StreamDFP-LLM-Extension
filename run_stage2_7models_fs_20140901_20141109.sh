#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
DATE_TAG="20140901_20141109"
SUMMARY_TSV="logs/llm_extract_7models_fs_zs_${DATE_TAG}_sizes.tsv"
PROGRESS_LOG="logs/llm_extract_7models_fs_zs_${DATE_TAG}.progress.log"
EVENT_MAPPING_DIR="${EVENT_MAPPING_DIR:-$ROOT/llm/event_mappings/models_7_20140901_20141109}"
BATCH_SIZE="${BATCH_SIZE:-128}"
MAX_BATCHED_TOKENS="${MAX_BATCHED_TOKENS:-32768}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-160}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.92}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"

mkdir -p logs

echo -e "timestamp\tmodel_key\tmode\trows\tsize_bytes\tsize_h\tvector_dim\tevent_mapping\tout_file" > "$SUMMARY_TSV"
: > "$PROGRESS_LOG"

models=(
  st4000dm000
  hds5c3030ala630
  st3000dm001
  hms5c4040ble640
  st31500541as
  st4000dx000
  hds723030ala640
)

resolve_event_mapping() {
  local key="$1"
  local candidates=(
    "${EVENT_MAPPING_DIR}/event_mapping_${key}.yaml"
    "${EVENT_MAPPING_DIR}/event_mapping_hitachi_${key}.yaml"
    "${EVENT_MAPPING_DIR}/event_mapping_hgst_${key}.yaml"
    "${EVENT_MAPPING_DIR}/event_mapping_wdc_${key}.yaml"
    "${EVENT_MAPPING_DIR}/event_mapping_toshiba_${key}.yaml"
    "${EVENT_MAPPING_DIR}/event_mapping_samsung_${key}.yaml"
  )
  local f
  for f in "${candidates[@]}"; do
    if [[ -f "$f" ]]; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

read_vector_dim() {
  local mapping_file="$1"
  python - "$mapping_file" <<'PY'
import sys
import yaml
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    payload = yaml.safe_load(f) or {}
meta_dim = int(payload.get("meta_dim", 16))
features = payload.get("event_features") or []
types = payload.get("event_types") or []
print(meta_dim + len(features) * len(types))
PY
}

for key in "${models[@]}"; do
  in_file="llm/window_text_${key}_${DATE_TAG}.jsonl"
  ref_file="llm/reference_examples_${key}_0803_0831.json"
  event_mapping="$(resolve_event_mapping "$key" || true)"

  if [[ ! -f "$in_file" ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] MISSING input: $in_file" | tee -a "$PROGRESS_LOG"
    exit 1
  fi
  if [[ ! -f "$ref_file" ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] MISSING reference: $ref_file" | tee -a "$PROGRESS_LOG"
    exit 1
  fi
  if [[ -z "$event_mapping" ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] MISSING event mapping for key=$key under $EVENT_MAPPING_DIR" | tee -a "$PROGRESS_LOG"
    exit 1
  fi
  vector_dim="$(read_vector_dim "$event_mapping")"

  for mode in fs zs; do
    if [[ "$mode" == "fs" ]]; then
      fewshot_mode="force"
    else
      fewshot_mode="off"
    fi
    out_file="llm_cache_${key}_${mode}_${DATE_TAG}_compare.jsonl"
    run_log="logs/llm_extract_${key}_${mode}_${DATE_TAG}.log"

    rm -f "$out_file"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START key=$key mode=$mode" | tee -a "$PROGRESS_LOG"

    TIMEFORMAT='ELAPSED_SEC=%3R'; {
      time python llm/llm_offline_extract.py \
        --window_text_path "$in_file" \
        --reference_examples "$ref_file" \
        --out "$out_file" \
        --model "$MODEL_PATH" \
        --batch_size "$BATCH_SIZE" \
        --backend vllm \
        --vllm_max_model_len "$MAX_MODEL_LEN" \
        --vllm_max_num_batched_tokens "$MAX_BATCHED_TOKENS" \
        --vllm_gpu_memory_utilization "$GPU_MEM_UTIL" \
        --max_new_tokens "$MAX_NEW_TOKENS" \
        --temperature 0 \
        --top_p 0.9 \
        --flush_every 2048 \
        --log_every_batches 50 \
        --fewshot_mode "$fewshot_mode" \
        --fewshot_min_per_cause 1 \
        --rule_score_gate 0.8 \
        --event_mapping_config "$event_mapping" \
        --write_root_cause_pred \
        --show_progress
    } 2>&1 | tee "$run_log"

    rows=$(wc -l < "$out_file")
    size_bytes=$(stat -c%s "$out_file")
    size_h=$(du -h "$out_file" | awk '{print $1}')

    echo -e "$(date -u +%Y-%m-%dT%H:%M:%SZ)\t${key}\t${mode}\t${rows}\t${size_bytes}\t${size_h}\t${vector_dim}\t${event_mapping}\t${out_file}" | tee -a "$SUMMARY_TSV" "$PROGRESS_LOG"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE key=$key mode=$mode rows=$rows size=$size_h dim=$vector_dim" | tee -a "$PROGRESS_LOG"
  done
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ALL_DONE" | tee -a "$PROGRESS_LOG"
