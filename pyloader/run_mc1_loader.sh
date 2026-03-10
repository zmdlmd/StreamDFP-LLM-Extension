#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Core loader settings
START_DATE="${START_DATE:-20180103}"
DATE_FORMAT="${DATE_FORMAT:-%Y%m%d}"
DISK_MODEL="${DISK_MODEL:-MC1}"
DATA_PATH="${DATA_PATH:-${ROOT_DIR}/data/ssd_2018/}"
TRAIN_PATH="${TRAIN_PATH:-${ROOT_DIR}/pyloader/mc1_train/}"
TEST_PATH="${TEST_PATH:-${ROOT_DIR}/pyloader/mc1_test/}"
ITER_DAYS="${ITER_DAYS:-10}"
FEATURES_PATH="${FEATURES_PATH:-${ROOT_DIR}/pyloader/features_erg/mc1_all.txt}"
PATH_FEATUERS="${PATH_FEATUERS:-}" # backward-compatible typo env
OPTIONS="${OPTIONS:-3,4,6}"
FORGET_TYPE="${FORGET_TYPE:-sliding}"
LABEL_DAYS="${LABEL_DAYS:-20}"
POSITIVE_WINDOW="${POSITIVE_WINDOW:-30}"
NEGATIVE_WINDOW="${NEGATIVE_WINDOW:-7}"
VALIDATION_WINDOW="${VALIDATION_WINDOW:-30}"

# Optional LLM feature injection
LLM_CACHE_PATH="${LLM_CACHE_PATH:-}"
LLM_DIM="${LLM_DIM:-79}"
USE_LLM_FEATURES="${USE_LLM_FEATURES:-auto}" # auto|0|1
LLM_POLICY_CONFIG="${LLM_POLICY_CONFIG:-}"
LLM_POLICY_MODEL_KEY="${LLM_POLICY_MODEL_KEY:-}"
LLM_FALLBACK_MODE="${LLM_FALLBACK_MODE:-nollm}"

# Output / bookkeeping
REPORT_NAME="${REPORT_NAME:-mc1}"
SAVE_DIR="${SAVE_DIR:-${ROOT_DIR}/save_model}"
PATH_LOAD="${PATH_LOAD:-${SAVE_DIR}/${REPORT_NAME}.pickle}"
PATH_SAVE="${PATH_SAVE:-${SAVE_DIR}/${REPORT_NAME}.pickle}"
TIME_PATH="${TIME_PATH:-${ROOT_DIR}/pyloader/time_${REPORT_NAME}.txt}"
DRY_RUN="${DRY_RUN:-0}"

if [[ -n "${PATH_FEATUERS}" ]]; then
  FEATURES_PATH="${PATH_FEATUERS}"
fi

mkdir -p "${TRAIN_PATH}" "${TEST_PATH}" "${SAVE_DIR}" "$(dirname "${TIME_PATH}")"

if [[ "${USE_LLM_FEATURES}" == "auto" ]]; then
  if [[ -n "${LLM_CACHE_PATH}" ]]; then
    USE_LLM_FEATURES="1"
  else
    USE_LLM_FEATURES="0"
  fi
fi

if [[ "${USE_LLM_FEATURES}" == "1" && -z "${LLM_CACHE_PATH}" ]]; then
  echo "[run_mc1_loader] USE_LLM_FEATURES=1 but LLM_CACHE_PATH is empty" >&2
  exit 2
fi
if [[ "${USE_LLM_FEATURES}" == "1" && ! -f "${LLM_CACHE_PATH}" ]]; then
  echo "[run_mc1_loader] LLM cache not found: ${LLM_CACHE_PATH}" >&2
  exit 2
fi

cmd=(
  python "${SCRIPT_DIR}/run.py"
  -s "${START_DATE}"
  -F "${DATE_FORMAT}"
  -p "${DATA_PATH}"
  -d "${DISK_MODEL}"
  -i "${ITER_DAYS}"
  -l "${PATH_LOAD}"
  -v "${PATH_SAVE}"
  -c "${FEATURES_PATH}"
  -r "${TRAIN_PATH}"
  -e "${TEST_PATH}"
  -o "${OPTIONS}"
  -t "${FORGET_TYPE}"
  -w "${POSITIVE_WINDOW}"
  -V "${VALIDATION_WINDOW}"
  -L "${NEGATIVE_WINDOW}"
  -a "${LABEL_DAYS}"
)

if [[ "${USE_LLM_FEATURES}" == "1" ]]; then
  cmd+=(-U 1 -C "${LLM_CACHE_PATH}" -M "${LLM_DIM}")
  if [[ -n "${LLM_POLICY_CONFIG}" ]]; then
    cmd+=(--llm_policy_config "${LLM_POLICY_CONFIG}")
  fi
  if [[ -n "${LLM_POLICY_MODEL_KEY}" ]]; then
    cmd+=(--llm_policy_model_key "${LLM_POLICY_MODEL_KEY}")
  fi
  cmd+=(--llm_fallback_mode "${LLM_FALLBACK_MODE}")
fi

printf "[run_mc1_loader] "
printf "%q " "${cmd[@]}"
echo
printf "%q " "${cmd[@]}" >> "${TIME_PATH}"
echo >> "${TIME_PATH}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[run_mc1_loader] DRY_RUN=1, command printed only."
  exit 0
fi

time ("${cmd[@]}") 2>> "${TIME_PATH}"
