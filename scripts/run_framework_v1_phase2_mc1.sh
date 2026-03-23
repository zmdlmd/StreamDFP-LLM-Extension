#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3-4B-Instruct-2507}"
DATA_ROOT="${DATA_ROOT:-$ROOT/data/ssd_2018}"
FEATURES_PATH="${FEATURES_PATH:-$ROOT/pyloader/features_erg/mc1_all.txt}"
DISK_MODEL="${DISK_MODEL:-MC1}"
DATE_FORMAT="${DATE_FORMAT:-%Y%m%d}"
DISK_ID_PREFIX="${DISK_ID_PREFIX:-s}"

RULE_PROFILE="${RULE_PROFILE:-auto}"
RULE_PROFILE_DIR="${RULE_PROFILE_DIR:-$ROOT/llm/rules/profiles}"
RULE_MEDIUM="${RULE_MEDIUM:-ssd}"
RULE_CONFIG="${RULE_CONFIG:-}"

SUMMARY_SCHEMA="${SUMMARY_SCHEMA:-structured_v2}"
SUMMARY_ANOMALY_TOP_K="${SUMMARY_ANOMALY_TOP_K:-8}"
SUMMARY_EMIT_LEGACY_TEXT="${SUMMARY_EMIT_LEGACY_TEXT:-0}"

MAX_WINDOWS="${MAX_WINDOWS:-${MAX_PILOT_WINDOWS:-20000}}"
SAMPLE_MODE="${SAMPLE_MODE:-stratified_day_disk}"
SAMPLE_SEED="${SAMPLE_SEED:-42}"
REFERENCE_POOL_WINDOWS="${REFERENCE_POOL_WINDOWS:-$MAX_WINDOWS}"
REFERENCE_START_DATE="${REFERENCE_START_DATE:-2018-01-03}"
REFERENCE_END_DATE="${REFERENCE_END_DATE:-2018-01-31}"
OUTPUT_START_DATE="${OUTPUT_START_DATE:-}"
OUTPUT_END_DATE="${OUTPUT_END_DATE:-}"
REFERENCE_MIN_NON_UNKNOWN="${REFERENCE_MIN_NON_UNKNOWN:-3}"
REFERENCE_PER_CAUSE="${REFERENCE_PER_CAUSE:-1}"
REFERENCE_MAX_EXAMPLES="${REFERENCE_MAX_EXAMPLES:-6}"
FEWSHOT_PER_CAUSE_CAP="${FEWSHOT_PER_CAUSE_CAP:-1}"

BACKEND="${BACKEND:-vllm}"
API_BASE_URL="${API_BASE_URL:-${OPENAI_BASE_URL:-}}"
API_KEY_ENV="${API_KEY_ENV:-OPENAI_API_KEY}"
API_TIMEOUT="${API_TIMEOUT:-120}"
API_MAX_RETRIES="${API_MAX_RETRIES:-3}"
API_JSON_MODE="${API_JSON_MODE:-0}"
BATCH_SIZE="${BATCH_SIZE:-64}"
VLLM_GPU_MEM="${VLLM_GPU_MEM:-0.92}"
VLLM_TENSOR_PARALLEL_SIZE="${VLLM_TENSOR_PARALLEL_SIZE:-1}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"
VLLM_MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-16384}"
VLLM_ENFORCE_EAGER="${VLLM_ENFORCE_EAGER:-0}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-180}"
TEMPERATURE="${TEMPERATURE:-0}"
TOP_P="${TOP_P:-0.9}"

FLUSH_EVERY="${FLUSH_EVERY:-2048}"
LOG_EVERY_BATCHES="${LOG_EVERY_BATCHES:-50}"

RUN_TAG="${RUN_TAG:-pilot20k}"
EVENT_MAPPING_CONFIG="${EVENT_MAPPING_CONFIG:-$ROOT/llm/event_mapping_mc1.yaml}"
EXTRACT_COMBOS="${EXTRACT_COMBOS:-fs_legacy fs_structured_v2 zs_legacy zs_structured_v2}"
SKIP_EXTRACT="${SKIP_EXTRACT:-0}"
DRY_RUN="${DRY_RUN:-0}"

OUT_DIR="${OUT_DIR:-$ROOT/llm/framework_v1_mc1}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/framework_v1_phase2_mc1}"
DOC_DIR="${DOC_DIR:-$ROOT/docs}"

mkdir -p "$OUT_DIR" "$LOG_DIR" "$DOC_DIR"

export LD_LIBRARY_PATH="/root/miniconda3/lib/python3.12/site-packages/torch/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
if ! [[ "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export OMP_NUM_THREADS=8
fi
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"

WINDOW_TEXT_OUT="$OUT_DIR/window_text_mc1_${RUN_TAG}.jsonl"
REFERENCE_OUT="$OUT_DIR/reference_mc1_${RUN_TAG}.json"
REFERENCE_QUALITY_OUT="$OUT_DIR/reference_mc1_${RUN_TAG}_quality.json"

rule_args=()
if [[ -n "$RULE_CONFIG" ]]; then
  rule_args+=(--rule_config "$RULE_CONFIG")
fi
legacy_args=()
if [[ "$SUMMARY_EMIT_LEGACY_TEXT" == "1" ]]; then
  legacy_args+=(--summary_emit_legacy_text)
fi
out_range_args=()
if [[ -n "$OUTPUT_START_DATE" ]]; then
  out_range_args+=(--output_start_date "$OUTPUT_START_DATE")
fi
if [[ -n "$OUTPUT_END_DATE" ]]; then
  out_range_args+=(--output_end_date "$OUTPUT_END_DATE")
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[phase2_mc1] DRY_RUN=1"
  echo "  DATA_ROOT=$DATA_ROOT"
  echo "  FEATURES_PATH=$FEATURES_PATH"
  echo "  WINDOW_TEXT_OUT=$WINDOW_TEXT_OUT"
  echo "  REFERENCE_OUT=$REFERENCE_OUT"
  echo "  EXTRACT_COMBOS=$EXTRACT_COMBOS"
  exit 0
fi

echo "[phase2_mc1] building window_text + reference"
window_cmd=(python "$ROOT/llm/window_to_text.py" \
  --data_root "$DATA_ROOT" \
  --features_path "$FEATURES_PATH" \
  --out "$WINDOW_TEXT_OUT" \
  --reference_out "$REFERENCE_OUT" \
  --reference_quality_report_out "$REFERENCE_QUALITY_OUT" \
  --date_format "$DATE_FORMAT" \
  --disk_model "$DISK_MODEL" \
  --disk_id_prefix "$DISK_ID_PREFIX" \
  --rule_profile "$RULE_PROFILE" \
  --rule_profile_dir "$RULE_PROFILE_DIR" \
  --rule_medium "$RULE_MEDIUM" \
  --summary_schema "$SUMMARY_SCHEMA" \
  --summary_anomaly_top_k "$SUMMARY_ANOMALY_TOP_K" \
  "${legacy_args[@]}" \
  "${rule_args[@]}" \
  --reference_start_date "$REFERENCE_START_DATE" \
  --reference_end_date "$REFERENCE_END_DATE" \
  "${out_range_args[@]}" \
  --reference_min_non_unknown "$REFERENCE_MIN_NON_UNKNOWN" \
  --reference_per_cause "$REFERENCE_PER_CAUSE")
if [[ -n "$MAX_WINDOWS" && "$MAX_WINDOWS" != "0" ]]; then
  window_cmd+=(--max_windows "$MAX_WINDOWS" --sample_mode "$SAMPLE_MODE" --sample_seed "$SAMPLE_SEED")
fi
if [[ -n "$REFERENCE_POOL_WINDOWS" && "$REFERENCE_POOL_WINDOWS" != "0" ]]; then
  window_cmd+=(--reference_pool_windows "$REFERENCE_POOL_WINDOWS")
fi
"${window_cmd[@]}"

if [[ "$SKIP_EXTRACT" == "1" ]]; then
  echo "[phase2_mc1] SKIP_EXTRACT=1, window_text/reference done."
  exit 0
fi

cache_paths=()
for combo in $EXTRACT_COMBOS; do
  mode="${combo%%_*}"
  prompt="${combo#*_}"
  out_cache="$OUT_DIR/cache_mc1_${mode}_${prompt}_${RUN_TAG}.jsonl"
  log_file="$LOG_DIR/mc1_${mode}_${prompt}_${RUN_TAG}.log"

  fewshot_mode="off"
  if [[ "$mode" == "fs" ]]; then
    fewshot_mode="force"
  fi

  echo "[phase2_mc1] extract ${combo} -> ${out_cache}"
  extract_cmd=(stdbuf -oL -eL python "$ROOT/llm/llm_offline_extract.py" \
    --window_text_path "$WINDOW_TEXT_OUT" \
    --reference_examples "$REFERENCE_OUT" \
    --dataset_profile mc1 \
    --fewshot_mode "$fewshot_mode" \
    --fewshot_min_per_cause 1 \
    --fewshot_per_cause_cap "$FEWSHOT_PER_CAUSE_CAP" \
    --reference_max_examples "$REFERENCE_MAX_EXAMPLES" \
    --prompt_profile "$prompt" \
    --rule_blend_mode three_stage \
    --event_type_policy strict \
    --event_mapping_config "$EVENT_MAPPING_CONFIG" \
    --enforce_event_feature_whitelist \
    --emit_quality_meta \
    --out "$out_cache" \
    --model "$MODEL_PATH" \
    --backend "$BACKEND" \
    --batch_size "$BATCH_SIZE" \
    --vllm_tensor_parallel_size "$VLLM_TENSOR_PARALLEL_SIZE" \
    --vllm_gpu_memory_utilization "$VLLM_GPU_MEM" \
    --vllm_max_model_len "$VLLM_MAX_MODEL_LEN" \
    --vllm_max_num_batched_tokens "$VLLM_MAX_NUM_BATCHED_TOKENS" \
    --max_new_tokens "$MAX_NEW_TOKENS" \
    --temperature "$TEMPERATURE" \
    --top_p "$TOP_P" \
    --rule_score_gate 0.8 \
    --flush_every "$FLUSH_EVERY" \
    --log_every_batches "$LOG_EVERY_BATCHES" \
    --write_root_cause_pred \
    --show_progress)
  if [[ "$BACKEND" == "openai" ]]; then
    extract_cmd+=(--api_key_env "$API_KEY_ENV" --api_timeout "$API_TIMEOUT" --api_max_retries "$API_MAX_RETRIES")
    if [[ -n "$API_BASE_URL" ]]; then
      extract_cmd+=(--api_base_url "$API_BASE_URL")
    fi
    if [[ "$API_JSON_MODE" == "1" ]]; then
      extract_cmd+=(--api_json_mode)
    fi
  fi
  if [[ "$VLLM_ENFORCE_EAGER" == "1" ]]; then
    extract_cmd+=(--vllm_enforce_eager)
  fi
  if [[ -n "$MAX_WINDOWS" && "$MAX_WINDOWS" != "0" ]]; then
    extract_cmd+=(--max_windows "$MAX_WINDOWS")
  fi
  "${extract_cmd[@]}" > "$log_file" 2>&1

  cache_paths+=("$out_cache")
done

echo "[phase2_mc1] build quality summary"
summary_csv="$DOC_DIR/pilot_extract_quality_mc1_v1.csv"
if [[ "$RUN_TAG" != "pilot20k" ]]; then
  summary_csv="$DOC_DIR/extract_quality_mc1_${RUN_TAG}_v1.csv"
fi
python "$ROOT/llm/scripts/build_model_quality_report.py" \
  --cache_paths "${cache_paths[@]}" \
  --window_text_paths "$WINDOW_TEXT_OUT" \
  --out_dir "$DOC_DIR/framework_v1_quality_mc1" \
  --summary_csv "$summary_csv"

echo "[phase2_mc1] done"
