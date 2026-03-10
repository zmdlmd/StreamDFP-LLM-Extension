#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
BATCH_SIZE="${BATCH_SIZE:-64}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"

mkdir -p "$ROOT/llm/framework_v1" "$ROOT/logs/framework_v1"

keys=(
  hgsthms5c4040ale640
  st31500341as
  hitachihds5c4040ale630
  wdcwd30efrx
  wdcwd10eads
  st4000dm000
  hds5c3030ala630
)

for key in "${keys[@]}"; do
  case "$key" in
    hgsthms5c4040ale640) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hgst_hms5c4040ale640.yaml" ;;
    st31500341as) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_st31500341as.yaml" ;;
    hitachihds5c4040ale630) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hitachi_hds5c4040ale630.yaml" ;;
    wdcwd30efrx) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_wdc_wd30efrx.yaml" ;;
    wdcwd10eads) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_wdc_wd10eads.yaml" ;;
    st4000dm000) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_st4000dm000.yaml" ;;
    hds5c3030ala630) map_cfg="$ROOT/llm/event_mappings/batch7_20140901_20141109/event_mapping_hitachi_hds5c3030ala630.yaml" ;;
    *) echo "[WARN] unknown key=$key"; continue ;;
  esac

  win="$ROOT/llm/window_text_${key}_20140901_20141109.jsonl"
  ref="$ROOT/llm/reference_examples_${key}_0803_0831.json"
  out="$ROOT/llm/framework_v1/cache_${key}_zs_structured_v2_pilot20k.jsonl"
  log="$ROOT/logs/framework_v1/phase2_${key}_zs_structured_v2_pilot20k.log"

  if [[ ! -s "$win" ]]; then
    echo "[ERROR] missing window_text: $win"
    continue
  fi
  if [[ ! -s "$ref" ]]; then
    echo "[ERROR] missing reference_examples: $ref"
    continue
  fi
  if [[ ! -s "$map_cfg" ]]; then
    echo "[ERROR] missing event_mapping_config: $map_cfg"
    continue
  fi

  existing=0
  if [[ -f "$out" ]]; then
    existing=$(wc -l < "$out" || echo 0)
  fi
  if [[ "$existing" -ge "$MAX_WINDOWS" ]]; then
    echo "[SKIP] $key existing_rows=$existing >= $MAX_WINDOWS"
    continue
  fi

  echo "[START] $(date -Is) key=$key out=$out"
  : > "$log"
  python "$ROOT/llm/llm_offline_extract.py" \
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
    > "$log" 2>&1

  lines=$(wc -l < "$out" || echo 0)
  size=$(du -h "$out" | awk '{print $1}')
  echo "[DONE] $(date -Is) key=$key rows=$lines size=$size"
done

echo "[ALL DONE] $(date -Is) batch7 phase2 zs structured_v2 pilot20k"
