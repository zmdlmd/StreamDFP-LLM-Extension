#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

PHASE="${PHASE:-all}" # 0|1|2|3|4|5|all
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
DATA_ROOT_HDD="${DATA_ROOT_HDD:-$ROOT/data/data_2014/2014}"
FEATURES_HDD="${FEATURES_HDD:-$ROOT/pyloader/features_erg/hi7_all.txt}"
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
RUN_TAG="${RUN_TAG:-pilot20k}"
PHASE2_INPUT_TAG="${PHASE2_INPUT_TAG:-$RUN_TAG}"
PHASE2_REUSE_INPUTS="${PHASE2_REUSE_INPUTS:-0}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"
SAMPLE_MODE="${SAMPLE_MODE:-stratified_day_disk}"  # sequential|stratified_day_disk
SAMPLE_SEED="${SAMPLE_SEED:-42}"
REFERENCE_POOL_WINDOWS="${REFERENCE_POOL_WINDOWS:-$MAX_WINDOWS}"
SUMMARY_ANOMALY_TOP_K="${SUMMARY_ANOMALY_TOP_K:-5}"
REFERENCE_MAX_EXAMPLES="${REFERENCE_MAX_EXAMPLES:-6}"
FEWSHOT_PER_CAUSE_CAP="${FEWSHOT_PER_CAUSE_CAP:-1}"
BATCH_SIZE="${BATCH_SIZE:-64}"
VLLM_GPU_MEM="${VLLM_GPU_MEM:-0.92}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"
PHASE2_EXTRACT_COMBOS="${PHASE2_EXTRACT_COMBOS:-zs_structured_v2}" # e.g. "zs_structured_v2 fs_structured_v2"

declare -A MODEL_NAME
declare -A MODEL_EVENT_MAP
MODEL_NAME["hi7"]="Hitachi HDS722020ALA330"
MODEL_NAME["hds723030ala640"]="Hitachi HDS723030ALA640"
MODEL_NAME["st3000dm001"]="ST3000DM001"
MODEL_NAME["hms5c4040ble640"]="HGST HMS5C4040BLE640"
MODEL_NAME["st31500541as"]="ST31500541AS"

MODEL_EVENT_MAP["hi7"]="$ROOT/llm/event_mapping_hi7.yaml"
MODEL_EVENT_MAP["hds723030ala640"]="$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_hitachi_hds723030ala640.yaml"
MODEL_EVENT_MAP["st3000dm001"]="$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_st3000dm001.yaml"
MODEL_EVENT_MAP["hms5c4040ble640"]="$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_hgst_hms5c4040ble640.yaml"
MODEL_EVENT_MAP["st31500541as"]="$ROOT/llm/event_mappings/models_7_20140901_20141109/event_mapping_st31500541as.yaml"

M1_MODELS=("st3000dm001" "hms5c4040ble640")
M2_MODELS=("hi7" "hds723030ala640" "st3000dm001" "hms5c4040ble640" "st31500541as")

mkdir -p "$ROOT/llm/framework_v1" "$ROOT/docs" "$ROOT/logs/framework_v1"
mkdir -p "$FEATURE_CONTRACT_DIR" "$FEATURE_CONTRACT_SUMMARY_DIR"

normalize_model_key() {
  local raw="${1:-}"
  echo "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+//g'
}

resolve_features_for_model() {
  local key="$1"
  local model_name="${MODEL_NAME[$key]}"
  local model_key
  local contract_path
  local summary_path

  if [[ "$FEATURE_CONTRACT_MODE" == "off" ]]; then
    echo "$FEATURES_HDD"
    return
  fi

  model_key="$(normalize_model_key "$model_name")"
  contract_path="$FEATURE_CONTRACT_DIR/${model_key}.txt"
  summary_path="$FEATURE_CONTRACT_SUMMARY_DIR/feature_contract_${model_key}_${REF_START//-/}_${REF_END//-/}.json"

  if [[ "$FEATURE_CONTRACT_MODE" == "force" || ! -s "$contract_path" ]]; then
    if [[ "$FEATURE_CONTRACT_AUTO_BUILD" == "1" ]]; then
      echo "[framework_v1] building feature contract for $key ($model_name)"
      python "$ROOT/llm/scripts/build_feature_contracts.py" \
        --data_root "$DATA_ROOT_HDD" \
        --features_path "$FEATURES_HDD" \
        --date_format "$DATE_FMT_HDD" \
        --train_start_date "$REF_START" \
        --train_end_date "$REF_END" \
        --disk_models "$model_name" \
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
  else
    echo "[framework_v1] WARN contract missing for $key, fallback to $FEATURES_HDD" >&2
    echo "$FEATURES_HDD"
  fi
}

resolve_phase2_models() {
  local selector="${PHASE2_MODELS:-m1}" # m1|m2|all|csv(list)
  local -a picked=()
  case "$selector" in
    m1)
      picked=("${M1_MODELS[@]}")
      ;;
    m2|all)
      picked=("${M2_MODELS[@]}")
      ;;
    *)
      IFS=',' read -r -a picked <<< "$selector"
      ;;
  esac
  if [[ ${#picked[@]} -eq 0 ]]; then
    echo "[framework_v1][phase2] no models resolved from PHASE2_MODELS=$selector" >&2
    exit 2
  fi
  local key
  for key in "${picked[@]}"; do
    if [[ -z "${MODEL_NAME[$key]:-}" ]]; then
      echo "[framework_v1][phase2] unknown model key: $key" >&2
      exit 2
    fi
  done
  printf "%s\n" "${picked[@]}"
}

run_phase0() {
  echo "[framework_v1][phase0] baseline lock + metric contract"
  python "$ROOT/llm/scripts/build_framework_baseline_lock.py" \
    --in_csv "$ROOT/docs/llm_robust_eval_report_v2.csv" \
    --out_csv "$ROOT/docs/framework_v1_baseline_lock.csv"
  echo "[framework_v1][phase0] done"
}

build_structured_window() {
  local key="$1"
  local max_windows="$2"
  local prefix="$3"
  local features_path="$4"
  local out_window="$ROOT/llm/framework_v1/window_text_${key}_${prefix}.jsonl"
  local out_ref="$ROOT/llm/framework_v1/reference_${key}_${prefix}.json"
  local out_ref_quality="$ROOT/llm/framework_v1/reference_${key}_${prefix}_quality.json"
  local input_window="$ROOT/llm/framework_v1/window_text_${key}_${PHASE2_INPUT_TAG}.jsonl"
  local input_ref="$ROOT/llm/framework_v1/reference_${key}_${PHASE2_INPUT_TAG}.json"
  local input_ref_quality="$ROOT/llm/framework_v1/reference_${key}_${PHASE2_INPUT_TAG}_quality.json"
  local -a cmd

  if [[ "$PHASE2_REUSE_INPUTS" == "1" && -s "$input_window" && -s "$input_ref" ]]; then
    echo "[framework_v1][phase2][$key] reusing phase1 inputs tag=$PHASE2_INPUT_TAG" >&2
    echo "$input_window;$input_ref;$input_ref_quality"
    return
  fi

  cmd=(python "$ROOT/llm/window_to_text.py" \
    --data_root "$DATA_ROOT_HDD" \
    --features_path "$features_path" \
    --date_format "$DATE_FMT_HDD" \
    --disk_model "${MODEL_NAME[$key]}" \
    --rule_profile auto \
    --rule_profile_dir "$ROOT/llm/rules/profiles" \
    --rule_medium auto \
    --summary_schema structured_v2 \
    --summary_anomaly_top_k "$SUMMARY_ANOMALY_TOP_K" \
    --out "$out_window" \
    --reference_out "$out_ref" \
    --reference_quality_report_out "$out_ref_quality" \
    --reference_start_date "$REF_START" \
    --reference_end_date "$REF_END" \
    --output_start_date "$OUT_START" \
    --output_end_date "$OUT_END" \
    --reference_min_non_unknown 3)
  if [[ -n "$max_windows" && "$max_windows" != "0" ]]; then
    cmd+=(--max_windows "$max_windows" --sample_mode "$SAMPLE_MODE" --sample_seed "$SAMPLE_SEED")
  fi
  if [[ -n "$REFERENCE_POOL_WINDOWS" && "$REFERENCE_POOL_WINDOWS" != "0" ]]; then
    cmd+=(--reference_pool_windows "$REFERENCE_POOL_WINDOWS")
  fi
  "${cmd[@]}"
  echo "$out_window;$out_ref;$out_ref_quality"
}

run_phase1() {
  echo "[framework_v1][phase1] structured_v2 schema smoke"
  local local_features
  for key in "${M1_MODELS[@]}"; do
    local_features="$(resolve_features_for_model "$key")"
    IFS=";" read -r out_window _ _ <<< "$(build_structured_window "$key" 32 "schema32" "$local_features")"
    python "$ROOT/llm/scripts/validate_summary_schema.py" \
      --window_text_path "$out_window" \
      --max_rows 32 \
      | tee "$ROOT/logs/framework_v1/summary_validate_${key}_schema32.json"
  done
  echo "[framework_v1][phase1] done"
}

run_extract_combo() {
  local key="$1"
  local mode="$2"           # fs|zs
  local prompt="$3"         # legacy|structured_v2
  local window_path="$4"
  local reference_path="$5"
  local out_cache="$ROOT/llm/framework_v1/cache_${key}_${mode}_${prompt}_${RUN_TAG}.jsonl"
  local fewshot_mode="off"
  if [[ "$mode" == "fs" ]]; then
    fewshot_mode="force"
  fi
  local -a max_window_arg=()
  if [[ -n "$MAX_WINDOWS" && "$MAX_WINDOWS" != "0" ]]; then
    max_window_arg+=(--max_windows "$MAX_WINDOWS")
  fi
  python "$ROOT/llm/llm_offline_extract.py" \
    --window_text_path "$window_path" \
    --reference_examples "$reference_path" \
    --out "$out_cache" \
    --model "$MODEL_PATH" \
    --backend vllm \
    --batch_size "$BATCH_SIZE" \
    --vllm_gpu_memory_utilization "$VLLM_GPU_MEM" \
    --vllm_max_model_len "$VLLM_MAX_MODEL_LEN" \
    --max_new_tokens 180 \
    --temperature 0 \
    --top_p 0.9 \
    --fewshot_mode "$fewshot_mode" \
    --fewshot_min_per_cause 1 \
    --fewshot_per_cause_cap "$FEWSHOT_PER_CAUSE_CAP" \
    --reference_max_examples "$REFERENCE_MAX_EXAMPLES" \
    --prompt_profile "$prompt" \
    --rule_blend_mode three_stage \
    --event_type_policy strict \
    --rule_score_gate 0.8 \
    --event_mapping_config "${MODEL_EVENT_MAP[$key]}" \
    --enforce_event_feature_whitelist \
    --emit_quality_meta \
    "${max_window_arg[@]}" \
    --flush_every 2048 \
    --log_every_batches 50 \
    --write_root_cause_pred
}

run_phase2() {
  mapfile -t phase2_models < <(resolve_phase2_models)
  echo "[framework_v1][phase2] extraction for models: ${phase2_models[*]} run_tag=${RUN_TAG} input_tag=${PHASE2_INPUT_TAG} reuse_inputs=${PHASE2_REUSE_INPUTS} max_windows=${MAX_WINDOWS}"
  local phase2_selector="${PHASE2_MODELS:-m1}"
  local summary_out
  local summary_prefix="pilot_extract_quality"
  if [[ "$RUN_TAG" != "pilot20k" ]]; then
    summary_prefix="extract_quality_${RUN_TAG}"
  fi
  case "$phase2_selector" in
    m1) summary_out="$ROOT/docs/${summary_prefix}_2models_v1.csv" ;;
    m2) summary_out="$ROOT/docs/${summary_prefix}_3models_m2_v1.csv" ;;
    all) summary_out="$ROOT/docs/${summary_prefix}_5models_all_v1.csv" ;;
    *) summary_out="$ROOT/docs/${summary_prefix}_custom_v1.csv" ;;
  esac

  local local_features
  local model_csvs=()
  for key in "${phase2_models[@]}"; do
    echo "[framework_v1][phase2][$key] prepare structured windows"
    local_features="$(resolve_features_for_model "$key")"
    echo "[framework_v1][phase2][$key] features_path=$local_features"
    IFS=";" read -r out_window out_ref _ <<< "$(build_structured_window "$key" "$MAX_WINDOWS" "$RUN_TAG" "$local_features")"
    local -a cache_paths=()
    for combo in $PHASE2_EXTRACT_COMBOS; do
      mode="${combo%%_*}"
      prompt="${combo#*_}"
      run_extract_combo "$key" "$mode" "$prompt" "$out_window" "$out_ref"
      cache_paths+=("$ROOT/llm/framework_v1/cache_${key}_${mode}_${prompt}_${RUN_TAG}.jsonl")
    done

    python "$ROOT/llm/scripts/build_model_quality_report.py" \
      --cache_paths "${cache_paths[@]}" \
      --window_text_paths "$out_window" \
      --out_dir "$ROOT/docs/framework_v1_quality_${key}" \
      --summary_csv "$ROOT/docs/${summary_prefix}_${key}_v1.csv"
    model_csvs+=("$ROOT/docs/${summary_prefix}_${key}_v1.csv")
  done
  python - <<'PY' "$summary_out" "${model_csvs[@]}"
import os
import sys
import pandas as pd

out = sys.argv[1]
paths = [p for p in sys.argv[2:] if os.path.exists(p)]
rows = []
for path in paths:
    rows.append(pd.read_csv(path))

if rows:
    all_df = pd.concat(rows, ignore_index=True)
    all_df.to_csv(out, index=False)
    print(f"wrote {out} rows={len(all_df)} from={len(paths)}")
else:
    print("no pilot csv found")
PY
  echo "[framework_v1][phase2] done"
}

run_phase3() {
  echo "[framework_v1][phase3] pre-ARFF auto calibration"
  echo "[framework_v1][phase3] use existing scripts with new cache variant semantics:"
  echo "  - llm/scripts/build_cache_variant.py --event_mapping_config --keep_event_keys --keep_meta_keys --compact_front"
  echo "  - pyloader/run.py -U 1 -C <variant_cache> -M <dim>"
  echo "  - simulate.Simulate + parse.py"
  echo "  - for full run: PHASE3_RUN_TAG=${RUN_TAG} bash scripts/run_framework_v1_phase3_grid.sh"
  echo "[framework_v1][phase3] NOTE: this phase is intentionally operator-driven due long runtime."
}

run_phase4() {
  echo "[framework_v1][phase4] extend to M2 models using same phase2/phase3 recipe."
  echo "[framework_v1][phase4] NOTE: execute after validating M1 gains."
}

run_phase5() {
  echo "[framework_v1][phase5] registry + final docs refresh"
  echo "See docs/cross_model_policy_registry_v1.md and docs/cross_model_llm_framework_v1_final.md"
}

case "$PHASE" in
  0) run_phase0 ;;
  1) run_phase1 ;;
  2) run_phase2 ;;
  3) run_phase3 ;;
  4) run_phase4 ;;
  5) run_phase5 ;;
  all)
    run_phase0
    run_phase1
    run_phase2
    run_phase3
    run_phase4
    run_phase5
    ;;
  *)
    echo "Unknown PHASE=$PHASE (expected: 0|1|2|3|4|5|all)" >&2
    exit 2
    ;;
esac
