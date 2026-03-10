#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
cd "$ROOT"

MODEL_KEY="hgsthms5c4040ble640"
DISK_MODEL="HGST HMS5C4040BLE640"
DATE_TAG="20140901_20141109"
DATA_ROOT="$ROOT/data/data_2014/2014/"
FEATURES="$ROOT/pyloader/features_erg/hi7_all.txt"
CACHE="$ROOT/llm_cache_hms5c4040ble640_zs_robustv6_recall_20140901_20141109.jsonl"
BASELINE_CSV="$ROOT/hi7_example/example_hms5c4040ble640_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"

RAW_CSV="$ROOT/docs/hms_round11_trainside_a_grid_zs_raw.csv"
OUT_CSV="$ROOT/docs/hms_round11_trainside_a_grid_zs.csv"
OUT_MD="$ROOT/docs/hms_round11_trainside_a_grid_zs.md"
STATE_JSON="$ROOT/logs/cross_model_controller/hms_round11_trainside_a_grid_zs_state.json"

SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"
mkdir -p "$ROOT/logs/cross_model_controller"

if [[ ! -f "$CACHE" ]]; then
  echo "[round11] missing cache: $CACHE" >&2
  exit 2
fi
if [[ ! -f "$BASELINE_CSV" ]]; then
  echo "[round11] missing baseline: $BASELINE_CSV" >&2
  exit 2
fi

make_policy() {
  local keep_dims="$1"
  local out="$2"
  cat > "$out" <<YAML
version: 1
default:
  enabled: true
  min_q_score: 0.0
  min_rule_match: false
  min_mapped_event_ratio: 0.0
  drop_unknown_root: false
  allowed_root_causes: []
  keep_dims: all
  llm_scale_alpha: 1.0
  fallback: nollm
models:
  ${MODEL_KEY}:
    enabled: true
    min_q_score: 0.0
    min_rule_match: false
    min_mapped_event_ratio: 0.0
    drop_unknown_root: false
    allowed_root_causes: []
    keep_dims: ${keep_dims}
    llm_scale_alpha: 1.0
    fallback: nollm
YAML
}

run_one() {
  local tag="$1"
  local keep="$2"
  local arf_a="$3"
  local policy_tmp="/tmp/hms_round11_${tag}.yaml"
  local train_dir="$ROOT/pyloader/hi7_train_hms5c4040ble640_r11_${tag}_a${arf_a}_${DATE_TAG}_aligned"
  local test_dir="$ROOT/pyloader/hi7_test_hms5c4040ble640_r11_${tag}_a${arf_a}_${DATE_TAG}_aligned"
  local out_txt="$ROOT/hi7_example/example_hms5c4040ble640_r11_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.txt"
  local out_time="$ROOT/hi7_example/time_example_hms5c4040ble640_r11_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.txt"
  local out_csv="$ROOT/hi7_example/example_hms5c4040ble640_r11_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.csv"

  if [[ -s "$out_csv" ]]; then
    echo "[round11] skip tag=$tag a=$arf_a (csv exists)"
    return
  fi

  make_policy "$keep" "$policy_tmp"
  rm -rf "$train_dir" "$test_dir"
  mkdir -p "$train_dir" "$test_dir"

  echo "[round11] run.py tag=$tag a=$arf_a"
  python pyloader/run.py \
    -s 2014-09-01 \
    -p "$DATA_ROOT" \
    -d "$DISK_MODEL" \
    -i 10 \
    -c "$FEATURES" \
    -r "${train_dir}/" \
    -e "${test_dir}/" \
    -o 4 \
    -t sliding \
    -w 30 \
    -V 30 \
    -L 7 \
    -a 20 \
    -U 1 \
    -C "$CACHE" \
    -M 70 \
    --llm_policy_config "$policy_tmp" \
    --llm_policy_model_key "$MODEL_KEY" \
    --llm_fallback_mode nollm

  echo "[round11] simulate tag=$tag a=$arf_a"
  stdbuf -i0 -o0 -e0 java -Xmx40g \
    -cp "$SIM_CP" simulate.Simulate \
    -s 2014-09-30 \
    -i 10 \
    -p "${train_dir}/" \
    -t "${test_dir}/" \
    -a "(meta.AdaptiveRandomForest -a ${arf_a} -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
    -D 10 \
    -V 30 \
    -H 0.5000 \
    -r 1 > "$out_txt" 2> "$out_time"

  python parse.py "$out_txt" >/dev/null
}

echo "tag,arf_a,csv,recall,acc" > "$RAW_CSV"

TAGS=(
  "active10|6,7,9,11,12,13,31,34,37,46"
  "active10_root|0,1,2,3,4,6,7,9,11,12,13,31,34,37,46"
  "all|all"
)

for item in "${TAGS[@]}"; do
  IFS='|' read -r tag keep <<< "$item"
  for arf_a in 6 12 18 24; do
    run_one "$tag" "$keep" "$arf_a"
    csv_path="$ROOT/hi7_example/example_hms5c4040ble640_r11_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.csv"
    python - <<'PY' "$csv_path" "$RAW_CSV" "$tag" "$arf_a"
import pandas as pd
import sys

csv_path, raw_csv, tag, arf_a = sys.argv[1:5]
df = pd.read_csv(csv_path)
df = df[df["date"].notna()]
rec = float(df["l_Recall_c1"].mean()) if not df.empty else float("nan")
acc = float(df["l_clf_corrct"].mean()) if not df.empty else float("nan")
with open(raw_csv, "a", encoding="utf-8") as f:
    f.write(f"{tag},{arf_a},{csv_path},{rec:.10f},{acc:.10f}\n")
PY
  done
done

python - <<'PY' "$BASELINE_CSV" "$RAW_CSV" "$OUT_CSV" "$OUT_MD" "$STATE_JSON"
import json
import pandas as pd
from pathlib import Path
import sys

base_csv = Path(sys.argv[1])
raw_csv = Path(sys.argv[2])
out_csv = Path(sys.argv[3])
out_md = Path(sys.argv[4])
state_json = Path(sys.argv[5])

base = pd.read_csv(base_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())
acc_guard = base_acc - 1.0

raw = pd.read_csv(raw_csv)
raw = raw.drop_duplicates(subset=["tag", "arf_a"], keep="last")
raw["delta_recall"] = raw["recall"] - base_recall
raw["delta_acc"] = raw["acc"] - base_acc
raw["pass_acc_guard"] = raw["acc"] >= acc_guard
raw["pass_recall_goal"] = raw["recall"] >= base_recall

res = raw.sort_values(["pass_acc_guard", "recall"], ascending=[False, False]).reset_index(drop=True)
res.to_csv(out_csv, index=False)

guard = res[res["pass_acc_guard"]]
best = guard.sort_values("recall", ascending=False).head(1)
if best.empty:
    best = res.sort_values("recall", ascending=False).head(1)
best_row = best.iloc[0].to_dict()

payload = {
    "baseline": {"recall": base_recall, "acc": base_acc, "acc_guard": acc_guard},
    "rows": res.to_dict(orient="records"),
    "best": best_row,
}
state_json.parent.mkdir(parents=True, exist_ok=True)
state_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

lines = [
    "# HMS round11 train-side utilization grid (ZS cache)",
    "",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}, acc_guard={acc_guard:.4f}",
    "",
    "| tag | arf_a | recall | acc | Δrecall | Δacc | ACC守卫 | Recall目标 |",
    "|---|---:|---:|---:|---:|---:|:---:|:---:|",
]
for _, r in res.iterrows():
    lines.append(
        f"| {r['tag']} | {int(r['arf_a'])} | {r['recall']:.4f} | {r['acc']:.4f} | {r['delta_recall']:+.4f} | {r['delta_acc']:+.4f} | "
        f"{'Y' if bool(r['pass_acc_guard']) else 'N'} | {'Y' if bool(r['pass_recall_goal']) else 'N'} |"
    )
lines += [
    "",
    f"- best: tag={best_row['tag']}, arf_a={int(best_row['arf_a'])}, recall={best_row['recall']:.4f}, acc={best_row['acc']:.4f}",
]
out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out_csv)
print(out_md)
print(state_json)
PY

echo "[round11] done"
