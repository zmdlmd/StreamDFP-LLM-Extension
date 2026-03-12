#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
DATA_ROOT_HDD="${DATA_ROOT_HDD:-$ROOT/data/data_2014/2014}"
FEATURES_HDD="${FEATURES_HDD:-$ROOT/pyloader/features_erg/hi7_all.txt}"
DISK_MODEL="${DISK_MODEL:?DISK_MODEL is required}"
MODEL_KEY="${MODEL_KEY:-}"
REUSE_PHASE1="${REUSE_PHASE1:-0}"

FEATURES_PATH="${FEATURES_PATH:-}"
FEATURE_CONTRACT_MODE="${FEATURE_CONTRACT_MODE:-auto}"   # auto|off|force
FEATURE_CONTRACT_AUTO_BUILD="${FEATURE_CONTRACT_AUTO_BUILD:-1}"
FEATURE_CONTRACT_DIR="${FEATURE_CONTRACT_DIR:-$ROOT/pyloader/features_erg/contracts}"
FEATURE_CONTRACT_SUMMARY_DIR="${FEATURE_CONTRACT_SUMMARY_DIR:-$ROOT/llm/contracts}"
FEATURE_CONTRACT_MIN_NON_NULL="${FEATURE_CONTRACT_MIN_NON_NULL:-0.99}"
FEATURE_CONTRACT_MIN_FEATURES="${FEATURE_CONTRACT_MIN_FEATURES:-5}"
FEATURE_CONTRACT_FALLBACK_RATIOS="${FEATURE_CONTRACT_FALLBACK_RATIOS:-0.95,0.9,0.8,0.5}"

DATE_FMT_HDD="${DATE_FMT_HDD:-%Y-%m-%d}"
OUT_START="${OUT_START:-2014-09-01}"
OUT_END="${OUT_END:-2014-11-09}"
REF_START="${REF_START:-2014-01-01}"
REF_END="${REF_END:-2014-08-31}"

RUN_TAG="${RUN_TAG:-pilot20k_onboard}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"
SAMPLE_MODE="${SAMPLE_MODE:-stratified_day_disk}"
SAMPLE_SEED="${SAMPLE_SEED:-42}"
REFERENCE_POOL_WINDOWS="${REFERENCE_POOL_WINDOWS:-$MAX_WINDOWS}"
SUMMARY_ANOMALY_TOP_K="${SUMMARY_ANOMALY_TOP_K:-5}"
REFERENCE_MAX_EXAMPLES="${REFERENCE_MAX_EXAMPLES:-6}"
FEWSHOT_PER_CAUSE_CAP="${FEWSHOT_PER_CAUSE_CAP:-1}"

BATCH_SIZE="${BATCH_SIZE:-8}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.80}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-3072}"
VLLM_MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-1024}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-128}"
TEMPERATURE="${TEMPERATURE:-0}"
TOP_P="${TOP_P:-0.9}"
RULE_SCORE_GATE="${RULE_SCORE_GATE:-0.8}"
RULE_SCORE_SOFT_GATE="${RULE_SCORE_SOFT_GATE:-0.55}"
OVERWRITE_OUTPUTS="${OVERWRITE_OUTPUTS:-1}"

EVENT_MAPPING_CONFIG="${EVENT_MAPPING_CONFIG:-}"
OUT_DIR="${OUT_DIR:-$ROOT/llm/framework_v1}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/framework_v1_single}"
QUALITY_DIR="${QUALITY_DIR:-$LOG_DIR/quality}"

normalize_model_key() {
  local raw="${1:-}"
  echo "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+//g'
}

if [[ -z "$MODEL_KEY" ]]; then
  MODEL_KEY="$(normalize_model_key "$DISK_MODEL")"
fi

if [[ -z "$EVENT_MAPPING_CONFIG" ]]; then
  EVENT_MAPPING_CONFIG="$ROOT/llm/event_mappings/onboarding/event_mapping_${MODEL_KEY}.yaml"
fi

mkdir -p "$OUT_DIR" "$LOG_DIR" "$QUALITY_DIR" "$FEATURE_CONTRACT_DIR" "$FEATURE_CONTRACT_SUMMARY_DIR"

export LD_LIBRARY_PATH="/root/miniconda3/lib/python3.12/site-packages/torch/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
if ! [[ "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export OMP_NUM_THREADS=8
fi
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"

resolve_features_path() {
  if [[ -n "$FEATURES_PATH" ]]; then
    echo "$FEATURES_PATH"
    return 0
  fi

  if [[ "$FEATURE_CONTRACT_MODE" == "off" ]]; then
    echo "$FEATURES_HDD"
    return 0
  fi

  local contract_path="$FEATURE_CONTRACT_DIR/${MODEL_KEY}.txt"
  local summary_path="$FEATURE_CONTRACT_SUMMARY_DIR/feature_contract_${MODEL_KEY}_${REF_START//-/}_${REF_END//-/}.json"

  if [[ "$FEATURE_CONTRACT_MODE" == "force" || ! -s "$contract_path" ]]; then
    if [[ "$FEATURE_CONTRACT_AUTO_BUILD" == "1" ]]; then
      echo "[phase2-single] building feature contract for $DISK_MODEL"
      python "$ROOT/llm/scripts/build_feature_contracts.py" \
        --data_root "$DATA_ROOT_HDD" \
        --features_path "$FEATURES_HDD" \
        --date_format "$DATE_FMT_HDD" \
        --train_start_date "$REF_START" \
        --train_end_date "$REF_END" \
        --disk_models "$DISK_MODEL" \
        --out_dir "$FEATURE_CONTRACT_DIR" \
        --summary_out "$summary_path" \
        --min_non_null_ratio "$FEATURE_CONTRACT_MIN_NON_NULL" \
        --fallback_non_null_ratios "$FEATURE_CONTRACT_FALLBACK_RATIOS" \
        --min_features "$FEATURE_CONTRACT_MIN_FEATURES" \
        --overwrite
    fi
  fi

  if [[ -s "$contract_path" ]]; then
    echo "$contract_path"
    return 0
  fi

  echo "[phase2-single] WARN contract missing for $DISK_MODEL, fallback to $FEATURES_HDD" >&2
  echo "$FEATURES_HDD"
}

FEATURES_PATH="$(resolve_features_path)"

if [[ ! -f "$EVENT_MAPPING_CONFIG" ]]; then
  echo "[phase2-single] missing event mapping: $EVENT_MAPPING_CONFIG" >&2
  exit 2
fi

WINDOW_TEXT_OUT="$OUT_DIR/window_text_${MODEL_KEY}_${RUN_TAG}.jsonl"
REFERENCE_OUT="$OUT_DIR/reference_${MODEL_KEY}_${RUN_TAG}.json"
REFERENCE_QUALITY_OUT="$OUT_DIR/reference_${MODEL_KEY}_${RUN_TAG}_quality.json"
OUT_CACHE="$OUT_DIR/cache_${MODEL_KEY}_zs_structured_v2_${RUN_TAG}.jsonl"
LOG_PATH="$LOG_DIR/phase2_${MODEL_KEY}_zs_structured_v2_${RUN_TAG}.log"
QUALITY_SUMMARY_CSV="$QUALITY_DIR/extract_quality_${MODEL_KEY}_${RUN_TAG}.csv"
QUALITY_OUT_DIR="$QUALITY_DIR/${MODEL_KEY}_${RUN_TAG}"

if [[ "$OVERWRITE_OUTPUTS" == "1" ]]; then
  if [[ "$REUSE_PHASE1" != "1" ]]; then
    rm -f "$WINDOW_TEXT_OUT" "$REFERENCE_OUT" "$REFERENCE_QUALITY_OUT"
  fi
  rm -f "$OUT_CACHE" "$LOG_PATH" "$QUALITY_SUMMARY_CSV"
  rm -rf "$QUALITY_OUT_DIR"
fi

echo "[phase2-single] build window_text/reference model_key=$MODEL_KEY run_tag=$RUN_TAG"
if [[ "$REUSE_PHASE1" == "1" && -s "$WINDOW_TEXT_OUT" && -s "$REFERENCE_OUT" ]]; then
  echo "[phase2-single] reuse existing phase1 outputs"
else
  window_cmd=(python "$ROOT/llm/window_to_text.py" \
    --data_root "$DATA_ROOT_HDD" \
    --features_path "$FEATURES_PATH" \
    --date_format "$DATE_FMT_HDD" \
    --disk_model "$DISK_MODEL" \
    --rule_profile auto \
    --rule_profile_dir "$ROOT/llm/rules/profiles" \
    --rule_medium auto \
    --summary_schema structured_v2 \
    --summary_anomaly_top_k "$SUMMARY_ANOMALY_TOP_K" \
    --out "$WINDOW_TEXT_OUT" \
    --reference_out "$REFERENCE_OUT" \
    --reference_quality_report_out "$REFERENCE_QUALITY_OUT" \
    --reference_start_date "$REF_START" \
    --reference_end_date "$REF_END" \
    --output_start_date "$OUT_START" \
    --output_end_date "$OUT_END" \
    --reference_min_non_unknown 3)

  if [[ -n "$MAX_WINDOWS" && "$MAX_WINDOWS" != "0" ]]; then
    window_cmd+=(--max_windows "$MAX_WINDOWS" --sample_mode "$SAMPLE_MODE" --sample_seed "$SAMPLE_SEED")
  fi
  if [[ -n "$REFERENCE_POOL_WINDOWS" && "$REFERENCE_POOL_WINDOWS" != "0" ]]; then
    window_cmd+=(--reference_pool_windows "$REFERENCE_POOL_WINDOWS")
  fi
  "${window_cmd[@]}"
fi

echo "[phase2-single] extract root-cause cache model_key=$MODEL_KEY run_tag=$RUN_TAG"
extract_cmd=(stdbuf -oL -eL python "$ROOT/llm/llm_offline_extract.py" \
  --window_text_path "$WINDOW_TEXT_OUT" \
  --reference_examples "$REFERENCE_OUT" \
  --out "$OUT_CACHE" \
  --model "$MODEL_PATH" \
  --backend vllm \
  --batch_size "$BATCH_SIZE" \
  --vllm_gpu_memory_utilization "$VLLM_GPU_MEMORY_UTILIZATION" \
  --vllm_max_model_len "$VLLM_MAX_MODEL_LEN" \
  --vllm_max_num_batched_tokens "$VLLM_MAX_NUM_BATCHED_TOKENS" \
  --max_new_tokens "$MAX_NEW_TOKENS" \
  --temperature "$TEMPERATURE" \
  --top_p "$TOP_P" \
  --fewshot_mode off \
  --fewshot_min_per_cause 1 \
  --fewshot_per_cause_cap "$FEWSHOT_PER_CAUSE_CAP" \
  --reference_max_examples "$REFERENCE_MAX_EXAMPLES" \
  --prompt_profile structured_v2 \
  --rule_blend_mode three_stage \
  --event_type_policy strict \
  --rule_score_gate "$RULE_SCORE_GATE" \
  --rule_score_soft_gate "$RULE_SCORE_SOFT_GATE" \
  --event_mapping_config "$EVENT_MAPPING_CONFIG" \
  --enforce_event_feature_whitelist \
  --emit_quality_meta \
  --flush_every 512 \
  --log_every_batches 20 \
  --write_root_cause_pred \
  --show_progress)
if [[ -n "$MAX_WINDOWS" && "$MAX_WINDOWS" != "0" ]]; then
  extract_cmd+=(--max_windows "$MAX_WINDOWS")
fi
"${extract_cmd[@]}" > "$LOG_PATH" 2>&1

python "$ROOT/llm/scripts/build_model_quality_report.py" \
  --cache_paths "$OUT_CACHE" \
  --window_text_paths "$WINDOW_TEXT_OUT" \
  --out_dir "$QUALITY_OUT_DIR" \
  --summary_csv "$QUALITY_SUMMARY_CSV"

echo "[phase2-single] done"
echo "[phase2-single] window_text=$WINDOW_TEXT_OUT"
echo "[phase2-single] reference=$REFERENCE_OUT"
echo "[phase2-single] cache=$OUT_CACHE"
echo "[phase2-single] log=$LOG_PATH"
echo "[phase2-single] quality_summary=$QUALITY_SUMMARY_CSV"
