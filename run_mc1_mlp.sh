#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"

START_DATE="${START_DATE:-2018-02-01}"
TRAIN_PATH="${TRAIN_PATH:-${ROOT_DIR}/pyloader/mc1_train/}"
TEST_PATH="${TEST_PATH:-${ROOT_DIR}/pyloader/mc1_test/}"
ITER_DAYS="${ITER_DAYS:-10}"
VALIDATION_WINDOW="${VALIDATION_WINDOW:-30}"
CLASS_INDEX="${CLASS_INDEX:-43}"

CLF_NAME="${CLF_NAME:-meta.MultiLayerPerceptron}"
LEARNING_RATE="${LEARNING_RATE:-0.5}"
NUM_RESET="${NUM_RESET:-1000}"
THRESHOLD="${THRESHOLD:-0.5}"
DOWN_SAMPLE="${DOWN_SAMPLE:-2}"
SEED="${SEED:-1}"
JAVA_XMX="${JAVA_XMX:-40g}"

REPORT_DIR="${REPORT_DIR:-${ROOT_DIR}/mc1_mlp/}"
RES_NAME="${RES_NAME:-example.txt}"
PATH_REPORT="${PATH_REPORT:-${REPORT_DIR}${RES_NAME}}"
TIME_PATH="${TIME_PATH:-${REPORT_DIR}time_${RES_NAME}}"
PARSE_OUTPUT="${PARSE_OUTPUT:-1}"
DRY_RUN="${DRY_RUN:-0}"

SIM_CP="${SIM_CP:-simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar}"

mkdir -p "${REPORT_DIR}"

cmd=(
  java "-Xmx${JAVA_XMX}" -cp "${SIM_CP}"
  simulate.Simulate
  -s "${START_DATE}"
  -i "${ITER_DAYS}"
  -c "${CLASS_INDEX}"
  -p "${TRAIN_PATH}"
  -t "${TEST_PATH}"
  -a "(${CLF_NAME} -r ${LEARNING_RATE} -s ${NUM_RESET})"
  -H "${THRESHOLD}"
  -D "${DOWN_SAMPLE}"
  -V "${VALIDATION_WINDOW}"
  -r "${SEED}"
)

printf "[run_mc1_mlp] "
printf "%q " "${cmd[@]}"
echo

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[run_mc1_mlp] DRY_RUN=1, command printed only."
  exit 0
fi

if [[ ! -d "${TRAIN_PATH}" || ! -d "${TEST_PATH}" ]]; then
  echo "[run_mc1_mlp] Train/Test dir missing: ${TRAIN_PATH} / ${TEST_PATH}" >&2
  exit 2
fi
if [[ -z "$(find "${TRAIN_PATH}" -maxdepth 1 -name '*.arff' -print -quit)" ]]; then
  echo "[run_mc1_mlp] No ARFF found in train dir: ${TRAIN_PATH}" >&2
  exit 2
fi
if [[ -z "$(find "${TEST_PATH}" -maxdepth 1 -name '*.arff' -print -quit)" ]]; then
  echo "[run_mc1_mlp] No ARFF found in test dir: ${TEST_PATH}" >&2
  exit 2
fi

time (stdbuf -i0 -o0 -e0 "${cmd[@]}" > "${PATH_REPORT}") 2>> "${TIME_PATH}"

if [[ "${PARSE_OUTPUT}" == "1" && -f "${ROOT_DIR}/parse.py" ]]; then
  python "${ROOT_DIR}/parse.py" "${PATH_REPORT}" >/dev/null || true
fi
