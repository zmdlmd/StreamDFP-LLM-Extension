#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"
python llm/llm_offline_extract.py \
  --window_text_path llm/window_text_hms5c4040ble640_20140901_20141109_v3.jsonl \
  --reference_examples llm/reference_examples_hms5c4040ble640_train_0101_0831_v3.json \
  --out llm_cache_hms5c4040ble640_zs_robustv7_refactor_20140901_20141109.jsonl \
  --model "${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}" \
  --backend vllm \
  --batch_size 64 \
  --vllm_max_model_len 4096 \
  --vllm_max_num_batched_tokens 16384 \
  --vllm_gpu_memory_utilization 0.92 \
  --max_new_tokens 180 \
  --temperature 0 \
  --top_p 0.9 \
  --fewshot_mode off \
  --rule_score_gate 0.45 \
  --rule_score_soft_gate 0.35 \
  --event_quality_gate 0.00 \
  --event_min_count 0 \
  --enforce_event_feature_whitelist \
  --emit_quality_meta \
  --event_mapping_config llm/event_mappings/models_7_20140901_20141109/event_mapping_hgst_hms5c4040ble640.yaml \
  --flush_every 2048 \
  --log_every_batches 50 \
  --write_root_cause_pred \
  --show_progress
