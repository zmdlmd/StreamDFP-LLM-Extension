#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$ROOT"

DATA_ROOT="$ROOT/data/data_2014/2014/"
FEATURES="$ROOT/pyloader/features_erg/hi7_all.txt"
START_DATE="2014-09-01"
SIM_START="2014-09-30"
END_ARFF="2014-11-09.arff"

# If stage2 master is still alive, wait until it exits.
STAGE2_PID="${1:-48636}"

echo "[stage3-5] start at $(date '+%F %T'), waiting stage2 pid=$STAGE2_PID if alive"
while ps -p "$STAGE2_PID" >/dev/null 2>&1; do
  sleep 30
done
echo "[stage3-5] stage2 pid not running; continue."

declare -A MODEL_NAME
MODEL_NAME["st3000dm001"]="Seagate ST3000DM001"
MODEL_NAME["st31500541as"]="Seagate ST31500541AS"
MODEL_NAME["st4000dm000"]="Seagate ST4000DM000"
MODEL_NAME["st4000dx000"]="Seagate ST4000DX000"
MODEL_NAME["hds5c3030ala630"]="Hitachi HDS5C3030ALA630"
MODEL_NAME["hds723030ala640"]="Hitachi HDS723030ALA640"
MODEL_NAME["hms5c4040ble640"]="HGST HMS5C4040BLE640"

ALL_KEYS=(
  "st3000dm001"
  "st31500541as"
  "st4000dm000"
  "st4000dx000"
  "hds5c3030ala630"
  "hds723030ala640"
  "hms5c4040ble640"
)

COMPLETED_KEYS=()
for key in "${ALL_KEYS[@]}"; do
  w="$ROOT/llm/window_text_${key}_20140901_20141109.jsonl"
  fs="$ROOT/llm_cache_${key}_fs_20140901_20141109_compare_map70.jsonl"
  zs="$ROOT/llm_cache_${key}_zs_20140901_20141109_compare_map70.jsonl"
  [[ -f "$w" && -f "$fs" && -f "$zs" ]] || continue
  total=$(wc -l < "$w" | tr -d ' ')
  fs_n=$(wc -l < "$fs" | tr -d ' ')
  zs_n=$(wc -l < "$zs" | tr -d ' ')
  if [[ "$fs_n" -eq "$total" && "$zs_n" -eq "$total" ]]; then
    COMPLETED_KEYS+=("$key")
  fi
done

if [[ "${#COMPLETED_KEYS[@]}" -eq 0 ]]; then
  echo "[stage3-5] no model has complete fs+zs map70 cache. exit."
  exit 0
fi

echo "[stage3-5] completed keys: ${COMPLETED_KEYS[*]}"

run_loader_one() {
  local key="$1"
  local mode="$2"
  local use_llm="$3"
  local cache="$4"
  local train_dir="$ROOT/pyloader/hi7_train_${key}_${mode}_20140901_20141109_compare_map70_aligned"
  local test_dir="$ROOT/pyloader/hi7_test_${key}_${mode}_20140901_20141109_compare_map70_aligned"

  if [[ -f "$train_dir/$END_ARFF" ]]; then
    echo "[loader][$key][$mode] skip (train has $END_ARFF)"
    return 0
  fi

  # pyloader/run.py expects output directories to exist.
  mkdir -p "$train_dir" "$test_dir"

  echo "[loader][$key][$mode] start"
  if [[ "$use_llm" -eq 1 ]]; then
    python pyloader/run.py \
      -s "$START_DATE" \
      -p "$DATA_ROOT" \
      -d "${MODEL_NAME[$key]}" \
      -i 10 \
      -c "$FEATURES" \
      -r "$train_dir/" \
      -e "$test_dir/" \
      -o 4 \
      -t sliding \
      -w 30 \
      -V 30 \
      -L 7 \
      -a 20 \
      -U 1 \
      -C "$cache" \
      -M 70
  else
    python pyloader/run.py \
      -s "$START_DATE" \
      -p "$DATA_ROOT" \
      -d "${MODEL_NAME[$key]}" \
      -i 10 \
      -c "$FEATURES" \
      -r "$train_dir/" \
      -e "$test_dir/" \
      -o 4 \
      -t sliding \
      -w 30 \
      -V 30 \
      -L 7 \
      -a 20 \
      -U 0
  fi
  echo "[loader][$key][$mode] done"
}

run_simulate_one() {
  local key="$1"
  local mode="$2"
  local train_dir="$ROOT/pyloader/hi7_train_${key}_${mode}_20140901_20141109_compare_map70_aligned"
  local test_dir="$ROOT/pyloader/hi7_test_${key}_${mode}_20140901_20141109_compare_map70_aligned"
  local out_txt="$ROOT/hi7_example/example_${key}_${mode}_20140901_20141109_compare_map70_aligned_i10.txt"
  local out_time="$ROOT/hi7_example/time_example_${key}_${mode}_20140901_20141109_compare_map70_aligned_i10.txt"

  if [[ -s "$out_txt" ]]; then
    echo "[simulate][$key][$mode] skip (exists)"
    return 0
  fi

  # Some disk models output no incremental test split (new_inst_start_index==0).
  # In that case, fallback to train dir as test input to keep pipeline runnable.
  if ! compgen -G "${test_dir}/*.arff" > /dev/null; then
    echo "[simulate][$key][$mode] test arff missing; fallback to train dir"
    test_dir="$train_dir"
  fi

  echo "[simulate][$key][$mode] start"
  stdbuf -i0 -o0 -e0 java -Xmx40g \
    -cp simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar \
    simulate.Simulate \
    -s "$SIM_START" \
    -i 10 \
    -p "${train_dir}/" \
    -t "${test_dir}/" \
    -a "(meta.AdaptiveRandomForest -a 6 -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
    -D 10 \
    -V 30 \
    -r 1 \
    > "$out_txt" 2> "$out_time"
  echo "[simulate][$key][$mode] done"
}

run_parse_one() {
  local key="$1"
  local mode="$2"
  local txt="$ROOT/hi7_example/example_${key}_${mode}_20140901_20141109_compare_map70_aligned_i10.txt"
  echo "[parse][$key][$mode] start"
  python parse.py "$txt"
  echo "[parse][$key][$mode] done"
}

for key in "${COMPLETED_KEYS[@]}"; do
  fs_cache="$ROOT/llm_cache_${key}_fs_20140901_20141109_compare_map70.jsonl"
  zs_cache="$ROOT/llm_cache_${key}_zs_20140901_20141109_compare_map70.jsonl"

  run_loader_one "$key" "fs" 1 "$fs_cache"
  run_loader_one "$key" "zs" 1 "$zs_cache"
  run_loader_one "$key" "nollm" 0 "-"

  run_simulate_one "$key" "fs"
  run_simulate_one "$key" "zs"
  run_simulate_one "$key" "nollm"

  run_parse_one "$key" "fs"
  run_parse_one "$key" "zs"
  run_parse_one "$key" "nollm"
done

python - "$ROOT" <<'PY'
from pathlib import Path
import pandas as pd
import sys

root = Path(sys.argv[1])
out = root / 'hi7_example' / 'completed_models_threeway_summary_20140901_20141109_compare_map70_aligned_i10.md'

def summarize(csv_path: Path):
    df = pd.read_csv(csv_path)
    df = df[df['date'].notna()].copy()
    if df.empty:
        return None
    p = float(df['l_Precision_c1'].mean())
    r = float(df['l_Recall_c1'].mean())
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        'days': float(df['l_Days'].mean()),
        'fp': float(df['l_FP'].mean()),
        'fpr': float(df['l_FAR'].mean()),
        'p': p,
        'r': r,
        'f1': f1,
    }

rows = []
for csv in sorted((root / 'hi7_example').glob('example_*_fs_20140901_20141109_compare_map70_aligned_i10.csv')):
    key = csv.name.replace('example_', '').replace('_fs_20140901_20141109_compare_map70_aligned_i10.csv', '')
    fs = summarize(csv)
    zs = summarize(root / 'hi7_example' / f'example_{key}_zs_20140901_20141109_compare_map70_aligned_i10.csv')
    nl = summarize(root / 'hi7_example' / f'example_{key}_nollm_20140901_20141109_compare_map70_aligned_i10.csv')
    if not (fs and zs and nl):
        continue
    rows.append((key, fs, zs, nl))

lines = []
lines.append('# Completed Models Three-way Comparison (map70)')
lines.append('')
lines.append('Metric: local mean; F1 is computed from mean Precision/Recall.')
lines.append('')
for key, fs, zs, nl in rows:
    lines.append(f'## {key}')
    lines.append('')
    lines.append('| 方案 | days | FP | FPR | Precision | Recall | F1 |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|')
    for name, m in [('FS', fs), ('ZS', zs), ('NO-LLM', nl)]:
        lines.append(
            f"| {name} | {m['days']:.6f} | {m['fp']:.6f} | {m['fpr']:.6f} | {m['p']:.6f} | {m['r']:.6f} | {m['f1']:.6f} |"
        )
    lines.append('')
    lines.append(
        f"- Δ(ZS-FS): F1 {zs['f1']-fs['f1']:+.6f}, FP {zs['fp']-fs['fp']:+.6f}, FPR {zs['fpr']-fs['fpr']:+.6f}"
    )
    lines.append(
        f"- Δ(ZS-NO-LLM): F1 {zs['f1']-nl['f1']:+.6f}, FP {zs['fp']-nl['fp']:+.6f}, FPR {zs['fpr']-nl['fpr']:+.6f}"
    )
    lines.append('')

out.write_text('\n'.join(lines), encoding='utf-8')
print(out)
PY

echo "[stage3-5] done at $(date '+%F %T')"
