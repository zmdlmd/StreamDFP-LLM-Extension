#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_PARENT="$(cd "$ROOT/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-$ROOT/data/ssd_2018}"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3-4B-Instruct-2507}"
FEATURES_PATH="${FEATURES_PATH:-$ROOT/pyloader/features_erg/mc1_all.txt}"
RULE_CONFIG="${RULE_CONFIG:-}"
EVENT_MAPPING_CONFIG="${EVENT_MAPPING_CONFIG:-$ROOT/llm/event_mapping_mc1.yaml}"

WINDOW_TEXT_OUT="${WINDOW_TEXT_OUT:-$ROOT/llm/window_text_mc1_qwen3_4b_2507.jsonl}"
REFERENCE_OUT="${REFERENCE_OUT:-$ROOT/llm/reference_examples_mc1_qwen3_4b_2507.json}"
REFERENCE_QUALITY_OUT="${REFERENCE_QUALITY_OUT:-$ROOT/llm/reference_quality_mc1_qwen3_4b_2507.json}"
CACHE_OUT="${CACHE_OUT:-$ROOT/llm_cache_mc1_qwen3_4b_2507.jsonl}"

TRAIN_OUT="${TRAIN_OUT:-$ROOT/pyloader/mc1_train_qwen4b/}"
TEST_OUT="${TEST_OUT:-$ROOT/pyloader/mc1_test_qwen4b/}"

DISK_MODEL="MC1"
DATE_FORMAT="%Y%m%d"
DISK_ID_PREFIX="${DISK_ID_PREFIX:-s}"
RULE_PROFILE="${RULE_PROFILE:-auto}"
RULE_PROFILE_DIR="${RULE_PROFILE_DIR:-$ROOT/llm/rules/profiles}"
SUMMARY_SCHEMA="${SUMMARY_SCHEMA:-structured_v2}"
SUMMARY_ANOMALY_TOP_K="${SUMMARY_ANOMALY_TOP_K:-8}"
SUMMARY_EMIT_LEGACY_TEXT="${SUMMARY_EMIT_LEGACY_TEXT:-0}"
REFERENCE_START_DATE="${REFERENCE_START_DATE:-2018-01-03}"
REFERENCE_END_DATE="${REFERENCE_END_DATE:-2018-01-31}"
REFERENCE_MIN_NON_UNKNOWN="${REFERENCE_MIN_NON_UNKNOWN:-3}"
REF_FAIL_ON_LOW_QUALITY="${REF_FAIL_ON_LOW_QUALITY:-0}"
LLM_BACKEND="${LLM_BACKEND:-vllm}"
LLM_BATCH_SIZE="${LLM_BATCH_SIZE:-8}"
VLLM_TP_SIZE="${VLLM_TP_SIZE:-1}"
VLLM_GPU_MEM="${VLLM_GPU_MEM:-0.9}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"

mkdir -p "${TRAIN_OUT}" "${TEST_OUT}"
RULE_CONFIG_ARGS=()
if [[ -n "${RULE_CONFIG}" ]]; then
  RULE_CONFIG_ARGS=(--rule_config "${RULE_CONFIG}")
fi
REF_FAIL_ARGS=()
if [[ "${REF_FAIL_ON_LOW_QUALITY}" == "1" ]]; then
  REF_FAIL_ARGS=(--reference_fail_on_low_quality)
fi
SUMMARY_LEGACY_ARGS=()
if [[ "${SUMMARY_EMIT_LEGACY_TEXT}" == "1" ]]; then
  SUMMARY_LEGACY_ARGS=(--summary_emit_legacy_text)
fi

# 1) MC1 滑窗样本转文本 + 参考样本
python "$ROOT/llm/window_to_text.py" \
  --data_root "${DATA_ROOT}" \
  --features_path "${FEATURES_PATH}" \
  --out "${WINDOW_TEXT_OUT}" \
  --reference_out "${REFERENCE_OUT}" \
  --reference_quality_report_out "${REFERENCE_QUALITY_OUT}" \
  --date_format "${DATE_FORMAT}" \
  --disk_model "${DISK_MODEL}" \
  --disk_id_prefix "${DISK_ID_PREFIX}" \
  --rule_profile "${RULE_PROFILE}" \
  --rule_profile_dir "${RULE_PROFILE_DIR}" \
  --rule_medium ssd \
  --summary_schema "${SUMMARY_SCHEMA}" \
  --summary_anomaly_top_k "${SUMMARY_ANOMALY_TOP_K}" \
  "${SUMMARY_LEGACY_ARGS[@]}" \
  "${RULE_CONFIG_ARGS[@]}" \
  --reference_start_date "${REFERENCE_START_DATE}" \
  --reference_end_date "${REFERENCE_END_DATE}" \
  --reference_min_non_unknown "${REFERENCE_MIN_NON_UNKNOWN}" \
  "${REF_FAIL_ARGS[@]}" \
  --reference_per_cause 1

# 2) LLM 离线抽取 cache（按 MC1 事件映射）
python "$ROOT/llm/llm_offline_extract.py" \
  --window_text_path "${WINDOW_TEXT_OUT}" \
  --reference_examples "${REFERENCE_OUT}" \
  --dataset_profile mc1 \
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

# 3) 生成 train/test 并拼接 z_llm（MC1 维度=79）
python "$ROOT/pyloader/run.py" \
  -s 20180103 \
  -F "${DATE_FORMAT}" \
  -p "${DATA_ROOT}/" \
  -d "${DISK_MODEL}" \
  -i 10 \
  -c "${FEATURES_PATH}" \
  -r "${TRAIN_OUT}" \
  -e "${TEST_OUT}" \
  -o 3,4,6 \
  -t sliding \
  -w 30 -V 30 -L 7 -a 20 \
  -U 1 -C "${CACHE_OUT}" -M 79

echo "Done. MC1 cache and train/test with z_llm have been generated."
