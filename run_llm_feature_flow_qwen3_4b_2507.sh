#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-$ROOT/data/data_2014/2014}"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"
FEATURES_PATH="${FEATURES_PATH:-$ROOT/pyloader/features_erg/hi7_all.txt}"
EVENT_MAPPING_CONFIG="${EVENT_MAPPING_CONFIG:-$ROOT/llm/event_mapping_hi7.yaml}"
CACHE_OUT="${CACHE_OUT:-$ROOT/llm_cache_qwen3_4b_2507.jsonl}"
WINDOW_TEXT_OUT="${WINDOW_TEXT_OUT:-$ROOT/llm/window_text_qwen3_4b_2507.jsonl}"
REFERENCE_OUT="${REFERENCE_OUT:-$ROOT/llm/reference_examples_qwen3_4b_2507.json}"
REFERENCE_QUALITY_OUT="${REFERENCE_QUALITY_OUT:-$ROOT/llm/reference_quality_qwen3_4b_2507.json}"
TRAIN_OUT="${TRAIN_OUT:-$ROOT/pyloader/hi7_train_2014_qwen4b/}"
TEST_OUT="${TEST_OUT:-$ROOT/pyloader/hi7_test_2014_qwen4b/}"
DISK_MODEL="${DISK_MODEL:-Hitachi HDS722020ALA330}"
RULE_PROFILE="${RULE_PROFILE:-auto}"
RULE_PROFILE_DIR="${RULE_PROFILE_DIR:-$ROOT/llm/rules/profiles}"
SUMMARY_SCHEMA="${SUMMARY_SCHEMA:-structured_v2}"
SUMMARY_ANOMALY_TOP_K="${SUMMARY_ANOMALY_TOP_K:-8}"
SUMMARY_EMIT_LEGACY_TEXT="${SUMMARY_EMIT_LEGACY_TEXT:-0}"
REFERENCE_START_DATE="${REFERENCE_START_DATE:-2014-01-01}"
REFERENCE_END_DATE="${REFERENCE_END_DATE:-2014-08-31}"
REFERENCE_MIN_NON_UNKNOWN="${REFERENCE_MIN_NON_UNKNOWN:-3}"
REF_FAIL_ON_LOW_QUALITY="${REF_FAIL_ON_LOW_QUALITY:-0}"
LLM_BACKEND="${LLM_BACKEND:-vllm}"
LLM_BATCH_SIZE="${LLM_BATCH_SIZE:-8}"
VLLM_TP_SIZE="${VLLM_TP_SIZE:-1}"
VLLM_GPU_MEM="${VLLM_GPU_MEM:-0.9}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"

mkdir -p "${TRAIN_OUT}" "${TEST_OUT}"
REF_FAIL_ARGS=()
if [[ "${REF_FAIL_ON_LOW_QUALITY}" == "1" ]]; then
  REF_FAIL_ARGS=(--reference_fail_on_low_quality)
fi
SUMMARY_LEGACY_ARGS=()
if [[ "${SUMMARY_EMIT_LEGACY_TEXT}" == "1" ]]; then
  SUMMARY_LEGACY_ARGS=(--summary_emit_legacy_text)
fi

# 1) 按项目特征清单将滑窗样本转文本，并自动抽取真实 few-shot 参考
python "$ROOT/llm/window_to_text.py" \
  --data_root "${DATA_ROOT}" \
  --features_path "${FEATURES_PATH}" \
  --out "${WINDOW_TEXT_OUT}" \
  --reference_out "${REFERENCE_OUT}" \
  --reference_quality_report_out "${REFERENCE_QUALITY_OUT}" \
  --disk_model "${DISK_MODEL}" \
  --rule_profile "${RULE_PROFILE}" \
  --rule_profile_dir "${RULE_PROFILE_DIR}" \
  --rule_medium auto \
  --summary_schema "${SUMMARY_SCHEMA}" \
  --summary_anomaly_top_k "${SUMMARY_ANOMALY_TOP_K}" \
  "${SUMMARY_LEGACY_ARGS[@]}" \
  --reference_start_date "${REFERENCE_START_DATE}" \
  --reference_end_date "${REFERENCE_END_DATE}" \
  --reference_min_non_unknown "${REFERENCE_MIN_NON_UNKNOWN}" \
  "${REF_FAIL_ARGS[@]}" \
  --reference_per_cause 1

# 2) 全量离线提取 LLM 特征（读取文本样本 + few-shot）
python "$ROOT/llm/llm_offline_extract.py" \
  --window_text_path "${WINDOW_TEXT_OUT}" \
  --reference_examples "${REFERENCE_OUT}" \
  --dataset_profile hi7 \
  --fewshot_mode auto \
  --fewshot_min_per_cause 1 \
  --prompt_profile "${SUMMARY_SCHEMA}" \
  --rule_blend_mode three_stage \
  --event_type_policy strict \
  --event_mapping_config "${EVENT_MAPPING_CONFIG}" \
  --out "${CACHE_OUT}" \
  --model "${MODEL_PATH}" \
  --batch_size "${LLM_BATCH_SIZE}" \
  --backend "${LLM_BACKEND}" \
  --max_new_tokens 180 \
  --temperature 0.0 \
  --top_p 0.9 \
  --rule_score_gate 0.8 \
  --vllm_tensor_parallel_size "${VLLM_TP_SIZE}" \
  --vllm_gpu_memory_utilization "${VLLM_GPU_MEM}" \
  --vllm_max_model_len "${VLLM_MAX_MODEL_LEN}"

# 3) 用 cache 拼接 z_llm 生成 train/test
python "$ROOT/pyloader/run.py" \
  -s 2014-01-01 \
  -p "${DATA_ROOT}/" \
  -d "${DISK_MODEL}" \
  -i 1 \
  -c "${FEATURES_PATH}" \
  -r "${TRAIN_OUT}" \
  -e "${TEST_OUT}" \
  -o 4 \
  -t sliding \
  -w 2 -V 2 -L 1 -a 1 \
  -U 1 -C "${CACHE_OUT}" -M 67

# 4) 快速验收
wc -l "${CACHE_OUT}"
rg -n "z_llm_0" "${TRAIN_OUT}/2014-01-05.arff" | head -n 1

echo "Done. Full cache and train/test with z_llm have been generated."
