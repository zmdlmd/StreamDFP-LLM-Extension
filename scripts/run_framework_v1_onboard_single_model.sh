#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

DISK_MODEL="${DISK_MODEL:?DISK_MODEL is required}"
MODEL_KEY="${MODEL_KEY:-}"

DATA_ROOT_HDD="${DATA_ROOT_HDD:-$ROOT/data/data_2014/2014}"
FEATURES_HDD="${FEATURES_HDD:-$ROOT/pyloader/features_erg/hi7_all.txt}"
DATE_FMT_HDD="${DATE_FMT_HDD:-%Y-%m-%d}"

REF_START="${REF_START:-2014-01-01}"
REF_END="${REF_END:-2014-08-31}"
OUT_START="${OUT_START:-2014-09-01}"
OUT_END="${OUT_END:-2014-11-09}"

RUN_TAG="${RUN_TAG:-}"
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-}"
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-onboard}"
MODEL_PATH="${MODEL_PATH:-}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"

BASELINE_START_DATE="${BASELINE_START_DATE:-2014-09-01}"
BASELINE_SIM_START="${BASELINE_SIM_START:-2014-09-30}"
ITER_DAYS="${ITER_DAYS:-10}"
VALID_WINDOW="${VALID_WINDOW:-30}"
NEGATIVE_WINDOW="${NEGATIVE_WINDOW:-7}"
LABEL_DAYS="${LABEL_DAYS:-20}"
JAVA_XMX="${JAVA_XMX:-40g}"
SIM_D="${SIM_D:-10}"
SIM_H="${SIM_H:-0.5000}"

FEATURE_CONTRACT_DIR="${FEATURE_CONTRACT_DIR:-$ROOT/pyloader/features_erg/contracts}"
FEATURE_CONTRACT_SUMMARY_DIR="${FEATURE_CONTRACT_SUMMARY_DIR:-$ROOT/llm/contracts}"
EVENT_MAPPING_OUT_DIR="${EVENT_MAPPING_OUT_DIR:-$ROOT/llm/event_mappings/onboarding}"
POLICY_SUGGEST_OUT_DIR="${POLICY_SUGGEST_OUT_DIR:-$ROOT/llm/calibration/generated}"

normalize_model_key() {
  local raw="${1:-}"
  echo "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+//g'
}

if [[ -z "$MODEL_KEY" ]]; then
  MODEL_KEY="$(normalize_model_key "$DISK_MODEL")"
fi

if [[ -z "$RUN_TAG" ]]; then
  RUN_TAG="pilot20k_onboard_${MODEL_KEY}"
fi
if [[ -z "$PHASE3_RUN_TAG" ]]; then
  PHASE3_RUN_TAG="$RUN_TAG"
fi

mkdir -p "$FEATURE_CONTRACT_DIR" "$FEATURE_CONTRACT_SUMMARY_DIR" "$EVENT_MAPPING_OUT_DIR" "$POLICY_SUGGEST_OUT_DIR"

CONTRACT_PATH="$FEATURE_CONTRACT_DIR/${MODEL_KEY}.txt"
CONTRACT_SUMMARY="$FEATURE_CONTRACT_SUMMARY_DIR/feature_contract_${MODEL_KEY}_${REF_START//-/}_${REF_END//-/}.json"
EVENT_MAPPING_CONFIG="$EVENT_MAPPING_OUT_DIR/event_mapping_${MODEL_KEY}.yaml"
EVENT_MAPPING_SUMMARY="$EVENT_MAPPING_OUT_DIR/summary_${MODEL_KEY}.json"

BASELINE_TAG="${OUT_START//-/}_${OUT_END//-/}_onboard_i${ITER_DAYS}"
BASELINE_TRAIN_DIR="$ROOT/pyloader/onboard_train_${MODEL_KEY}_${RUN_TAG}"
BASELINE_TEST_DIR="$ROOT/pyloader/onboard_test_${MODEL_KEY}_${RUN_TAG}"
BASELINE_TXT="$ROOT/hi7_example/example_${MODEL_KEY}_nollm_${BASELINE_TAG}.txt"
BASELINE_TIME="$ROOT/hi7_example/time_example_${MODEL_KEY}_nollm_${BASELINE_TAG}.txt"
BASELINE_CSV="${BASELINE_TXT%.txt}.csv"

PHASE3_SUMMARY_CSV="$ROOT/docs/prearff_grid_single_${MODEL_KEY}_${PHASE3_RUN_TAG}_v1.csv"
PHASE3_SUMMARY_MD="$ROOT/docs/prearff_grid_single_${MODEL_KEY}_${PHASE3_RUN_TAG}_v1.md"
POLICY_SUGGEST_YAML="$POLICY_SUGGEST_OUT_DIR/${MODEL_KEY}.yaml"
POLICY_SUGGEST_JSON="$POLICY_SUGGEST_OUT_DIR/${MODEL_KEY}.json"

echo "[onboard] start disk_model=$DISK_MODEL model_key=$MODEL_KEY run_tag=$RUN_TAG"

echo "[onboard] build feature contract"
python "$ROOT/llm/scripts/build_feature_contracts.py" \
  --data_root "$DATA_ROOT_HDD" \
  --features_path "$FEATURES_HDD" \
  --date_format "$DATE_FMT_HDD" \
  --train_start_date "$REF_START" \
  --train_end_date "$REF_END" \
  --disk_models "$DISK_MODEL" \
  --out_dir "$FEATURE_CONTRACT_DIR" \
  --summary_out "$CONTRACT_SUMMARY" \
  --min_non_null_ratio 0.99 \
  --fallback_non_null_ratios "0.95,0.9,0.8,0.5" \
  --min_features 5 \
  --overwrite

if [[ ! -s "$CONTRACT_PATH" ]]; then
  echo "[onboard] missing contract after build: $CONTRACT_PATH" >&2
  exit 2
fi

echo "[onboard] generate event mapping"
python "$ROOT/llm/scripts/generate_model_event_mappings.py" \
  --data_root "$DATA_ROOT_HDD" \
  --features_path "$CONTRACT_PATH" \
  --profile_dir "$ROOT/llm/rules/profiles" \
  --rule_medium auto \
  --date_format "$DATE_FMT_HDD" \
  --start_date "$REF_START" \
  --end_date "$OUT_END" \
  --disk_models "$DISK_MODEL" \
  --min_rows_per_model 1000 \
  --min_feature_presence_ratio 0.02 \
  --min_features 12 \
  --max_features 24 \
  --out_dir "$EVENT_MAPPING_OUT_DIR" \
  --overwrite \
  --summary_out "$EVENT_MAPPING_SUMMARY"

if [[ ! -f "$EVENT_MAPPING_CONFIG" ]]; then
  echo "[onboard] missing event mapping after generation: $EVENT_MAPPING_CONFIG" >&2
  exit 2
fi

echo "[onboard] run no-LLM baseline"
rm -rf "$BASELINE_TRAIN_DIR" "$BASELINE_TEST_DIR"
mkdir -p "$BASELINE_TRAIN_DIR" "$BASELINE_TEST_DIR"

python "$ROOT/pyloader/run.py" \
  -s "$BASELINE_START_DATE" \
  -p "$DATA_ROOT_HDD/" \
  -d "$DISK_MODEL" \
  -i "$ITER_DAYS" \
  -c "$CONTRACT_PATH" \
  -r "${BASELINE_TRAIN_DIR}/" \
  -e "${BASELINE_TEST_DIR}/" \
  -o 4 \
  -t sliding \
  -w 30 \
  -V "$VALID_WINDOW" \
  -L "$NEGATIVE_WINDOW" \
  -a "$LABEL_DAYS" \
  -U 0

stdbuf -i0 -o0 -e0 java -Xmx"$JAVA_XMX" \
  -cp simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar \
  simulate.Simulate \
  -s "$BASELINE_SIM_START" \
  -i "$ITER_DAYS" \
  -p "${BASELINE_TRAIN_DIR}/" \
  -t "${BASELINE_TEST_DIR}/" \
  -a "(meta.AdaptiveRandomForest -a 20 -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
  -D "$SIM_D" \
  -V "$VALID_WINDOW" \
  -H "$SIM_H" \
  -r 1 \
  > "$BASELINE_TXT" 2> "$BASELINE_TIME"

python "$ROOT/parse.py" "$BASELINE_TXT" >/dev/null

if [[ ! -f "$BASELINE_CSV" ]]; then
  echo "[onboard] missing baseline csv after parse: $BASELINE_CSV" >&2
  exit 2
fi

echo "[onboard] run phase2 extraction"
phase2_env=(
  "DISK_MODEL=$DISK_MODEL"
  "MODEL_KEY=$MODEL_KEY"
  "RUN_TAG=$RUN_TAG"
  "MAX_WINDOWS=$MAX_WINDOWS"
  "FEATURES_PATH=$CONTRACT_PATH"
  "EVENT_MAPPING_CONFIG=$EVENT_MAPPING_CONFIG"
)
if [[ -n "$MODEL_PATH" ]]; then
  phase2_env+=("MODEL_PATH=$MODEL_PATH")
fi
env "${phase2_env[@]}" bash "$ROOT/scripts/run_framework_v1_phase2_single_model.sh"

echo "[onboard] run phase3 calibration"
phase3_env=(
  "PHASE3_MODELS=$MODEL_KEY"
  "PHASE3_RUN_TAG=$PHASE3_RUN_TAG"
  "PHASE3_TAG_SUFFIX=$PHASE3_TAG_SUFFIX"
  "PHASE3_CUSTOM_MODEL_KEY=$MODEL_KEY"
  "PHASE3_CUSTOM_DISK_MODEL=$DISK_MODEL"
  "PHASE3_CUSTOM_BASELINE_CSV=$BASELINE_CSV"
  "SUMMARY_CSV=$PHASE3_SUMMARY_CSV"
  "SUMMARY_MD=$PHASE3_SUMMARY_MD"
)
env "${phase3_env[@]}" bash "$ROOT/scripts/run_framework_v1_phase3_grid.sh"

echo "[onboard] generate policy suggestion"
python - <<'PY' "$PHASE3_SUMMARY_CSV" "$POLICY_SUGGEST_YAML" "$POLICY_SUGGEST_JSON" "$DISK_MODEL" "$MODEL_KEY" "$PHASE3_RUN_TAG" "$EVENT_MAPPING_CONFIG" "$CONTRACT_PATH"
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

summary_csv = Path(sys.argv[1])
out_yaml = Path(sys.argv[2])
out_json = Path(sys.argv[3])
disk_model = sys.argv[4]
model_key = sys.argv[5]
run_tag = sys.argv[6]
event_mapping_config = sys.argv[7]
contract_path = sys.argv[8]

if not summary_csv.exists():
    raise SystemExit(f"missing phase3 summary: {summary_csv}")

df = pd.read_csv(summary_csv)
if df.empty:
    raise SystemExit("phase3 summary has no rows")

df = df.sort_values(
    ["pass_acc_guard", "delta_recall_vs_nollm", "delta_acc_vs_nollm"],
    ascending=[False, False, False],
).reset_index(drop=True)
best = df.iloc[0]
dim_key = str(best["dim_key"])
require_rule_match = bool(int(best["require_rule_match"]))
enabled = bool(bool(best["pass_acc_guard"]) and float(best["delta_recall_vs_nollm"]) >= 0.0)

keep_dims_map = {
    "compact9": "event_top3_plus_meta",
    "compact14": "event_top8_plus_meta",
    "full70": "all",
}

payload = {
    "enabled": enabled,
    "extract_profile": "zs",
    "cache_variant": dim_key,
    "q_gate": float(best["q_gate"]),
    "sev_sum_gate": float(best["sev_sum_gate"]),
    "require_rule_match": require_rule_match,
    "min_q_score": float(best["q_gate"]),
    "min_rule_match": require_rule_match,
    "min_mapped_event_ratio": 0.0,
    "keep_dims": keep_dims_map.get(dim_key, "all"),
    "llm_scale_alpha": 1.0,
    "fallback": "nollm",
}

sidecar = {
    "disk_model": disk_model,
    "model_key": model_key,
    "run_tag": run_tag,
    "event_mapping_config": event_mapping_config,
    "contract_path": contract_path,
    "phase3_summary_csv": str(summary_csv),
    "recommended_action": "llm_enabled" if enabled else "fallback",
    "best_row": {
        "dim_key": dim_key,
        "q_gate": float(best["q_gate"]),
        "sev_sum_gate": float(best["sev_sum_gate"]),
        "require_rule_match": int(best["require_rule_match"]),
        "recall": float(best["recall"]),
        "acc": float(best["acc"]),
        "delta_recall_vs_nollm": float(best["delta_recall_vs_nollm"]),
        "delta_acc_vs_nollm": float(best["delta_acc_vs_nollm"]),
        "pass_acc_guard": bool(best["pass_acc_guard"]),
        "result_csv": str(best["result_csv"]),
    },
}

out_yaml.parent.mkdir(parents=True, exist_ok=True)
out_json.parent.mkdir(parents=True, exist_ok=True)
out_yaml.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
out_json.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
print(out_yaml)
print(out_json)
PY

echo "[onboard] done"
echo "[onboard] contract=$CONTRACT_PATH"
echo "[onboard] event_mapping=$EVENT_MAPPING_CONFIG"
echo "[onboard] baseline_csv=$BASELINE_CSV"
echo "[onboard] phase3_summary=$PHASE3_SUMMARY_CSV"
echo "[onboard] policy_suggest_yaml=$POLICY_SUGGEST_YAML"
