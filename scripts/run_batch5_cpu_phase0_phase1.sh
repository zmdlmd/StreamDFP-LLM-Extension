#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

DATA_ROOT="$ROOT/data/data_2014/2014"
FEATURE_POOL="$ROOT/pyloader/features_erg/hi7_all.txt"
CONTRACT_DIR="$ROOT/pyloader/features_erg/contracts"
RULE_PROFILE_DIR="$ROOT/llm/rules/profiles"

OUT_START="2014-09-01"
OUT_END="2014-11-09"
REF_START="2014-08-03"
REF_END="2014-08-31"

MODEL_KEYS=(
  "hgsthms5c4040ale640"
  "st31500341as"
  "hitachihds5c4040ale630"
  "wdcwd30efrx"
  "wdcwd10eads"
)
MODEL_NAMES=(
  "HGST HMS5C4040ALE640"
  "ST31500341AS"
  "Hitachi HDS5C4040ALE630"
  "WDC WD30EFRX"
  "WDC WD10EADS"
)

MODELS_CSV="HGST HMS5C4040ALE640,ST31500341AS,Hitachi HDS5C4040ALE630,WDC WD30EFRX,WDC WD10EADS"

mkdir -p "$ROOT/logs" "$CONTRACT_DIR"

echo "[INFO] $(date -Is) build contracts for batch5"
python llm/scripts/build_feature_contracts.py \
  --data_root "$DATA_ROOT" \
  --features_path "$FEATURE_POOL" \
  --train_start_date 2014-01-01 \
  --train_end_date 2014-08-31 \
  --disk_models "$MODELS_CSV" \
  --out_dir "$CONTRACT_DIR" \
  --summary_out "$ROOT/docs/framework_v1_quality_newmodels_pre_gpu/batch5_contracts_train_0101_0831.json" \
  --overwrite

fail_count=0
for idx in "${!MODEL_KEYS[@]}"; do
  key="${MODEL_KEYS[$idx]}"
  model="${MODEL_NAMES[$idx]}"
  echo "[INFO] $(date -Is) ==== model=$model key=$key ===="

  contract="$CONTRACT_DIR/${key}.txt"
  if [[ ! -f "$contract" ]]; then
    echo "[ERROR] missing contract: $contract"
    fail_count=$((fail_count+1))
    continue
  fi

  win_out="$ROOT/llm/window_text_${key}_${OUT_START//-/}_${OUT_END//-/}.jsonl"
  ref_out="$ROOT/llm/reference_examples_${key}_0803_0831.json"
  ref_q="$ROOT/llm/reference_quality_${key}_0803_0831.json"
  ref_tmp="$ROOT/llm/window_text_${key}_reference_pool_0803_0831_tmp.jsonl"

  if [[ ! -f "$win_out" ]]; then
    echo "[INFO] $(date -Is) stage1-main window_to_text -> $win_out"
    python llm/window_to_text.py \
      --data_root "$DATA_ROOT" \
      --features_path "$contract" \
      --disk_model "$model" \
      --rule_profile auto \
      --rule_profile_dir "$RULE_PROFILE_DIR" \
      --rule_medium auto \
      --output_start_date "$OUT_START" \
      --output_end_date "$OUT_END" \
      --out "$win_out"
  else
    echo "[SKIP] existing $win_out"
  fi

  if [[ ! -f "$ref_out" || ! -f "$ref_q" ]]; then
    echo "[INFO] $(date -Is) stage1-ref window_to_text -> $ref_out"
    python llm/window_to_text.py \
      --data_root "$DATA_ROOT" \
      --features_path "$contract" \
      --disk_model "$model" \
      --rule_profile auto \
      --rule_profile_dir "$RULE_PROFILE_DIR" \
      --rule_medium auto \
      --output_start_date "$REF_START" \
      --output_end_date "$REF_START" \
      --max_windows 1 \
      --out "$ref_tmp" \
      --reference_out "$ref_out" \
      --reference_quality_report_out "$ref_q" \
      --reference_per_cause 1 \
      --reference_strategy stratified \
      --reference_start_date "$REF_START" \
      --reference_end_date "$REF_END" \
      --reference_pool_windows 500000 \
      --reference_min_non_unknown 3 \
      --sample_mode stratified_day_disk \
      --sample_seed 42
    rm -f "$ref_tmp"
  else
    echo "[SKIP] existing $ref_out and $ref_q"
  fi

  train_dir="$ROOT/pyloader/hi7_train_${key}_nollm_20140901_20141109_compare_aligned/"
  test_dir="$ROOT/pyloader/hi7_test_${key}_nollm_20140901_20141109_compare_aligned/"
  mkdir -p "$train_dir" "$test_dir"

  out_txt="$ROOT/hi7_example/example_${key}_nollm_20140901_20141109_compare_aligned_i10.txt"
  out_time="$ROOT/hi7_example/time_example_${key}_nollm_20140901_20141109_compare_aligned_i10.txt"
  out_csv="$ROOT/hi7_example/example_${key}_nollm_20140901_20141109_compare_aligned_i10.csv"

  if [[ ! -f "$out_csv" ]]; then
    echo "[INFO] $(date -Is) phase1-nollm run.py + simulate + parse"
    python pyloader/run.py \
      -s 2014-09-01 \
      -p "$DATA_ROOT/" \
      -d "$model" \
      -i 10 \
      -c "$contract" \
      -r "$train_dir" \
      -e "$test_dir" \
      -o 4 \
      -t sliding \
      -w 30 \
      -V 30 \
      -L 7 \
      -a 20 \
      -U 0

    stdbuf -i0 -o0 -e0 java -Xmx40g \
      -cp simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar \
      simulate.Simulate \
      -s 2014-09-30 \
      -i 10 \
      -p "$train_dir" \
      -t "$test_dir" \
      -a \(meta.AdaptiveRandomForest -a 6 -s 30 -l \(ARFHoeffdingTree -g 50 -c 1e-7\) -j -1 -x \(ADWINChangeDetector -a 1e-5\) -p \(ADWINChangeDetector -a 1e-4\)\) \
      -D 10 \
      -V 30 \
      -r 1 \
      > "$out_txt" \
      2> "$out_time"

    python parse.py "$out_txt" >/dev/null
  else
    echo "[SKIP] existing $out_csv"
  fi

  if [[ -f "$out_csv" ]]; then
    echo "[OK] $(date -Is) $key baseline csv ready"
  else
    echo "[ERROR] $(date -Is) $key baseline csv missing"
    fail_count=$((fail_count+1))
  fi

done

echo "[INFO] $(date -Is) batch5 cpu phase0/1 done; fail_count=${fail_count}"
exit 0
