#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
model="${1:-}"
round="${2:-0}"
root="${3:-$DEFAULT_ROOT}"

if [[ "$model" != "hms5c4040ble640" ]]; then
  echo "[hook][microgrid] skip model=$model"
  exit 0
fi

cd "$root"

state_dir="$root/logs/cross_model_controller"
state_file="$state_dir/hms_selected_round${round}.json"
nollm_csv="$root/hi7_example/example_hms5c4040ble640_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
policy_file="$root/llm/calibration/models/hgsthms5c4040ble640.yaml"

if [[ ! -f "$state_file" ]]; then
  echo "[hook][microgrid] missing state file from policy_grid: $state_file" >&2
  exit 2
fi
if [[ ! -f "$nollm_csv" ]]; then
  echo "[hook][microgrid] missing baseline: $nollm_csv" >&2
  exit 2
fi

train_dir="$(python - <<'PY' "$state_file"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["train_dir"])
PY
)"
test_dir="$(python - <<'PY' "$state_file"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["test_dir"])
PY
)"

if [[ ! -d "$train_dir" || ! -d "$test_dir" ]]; then
  echo "[hook][microgrid] missing train/test dir from state file" >&2
  exit 2
fi

SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"

# d|h
GRID=(
  "10|0.5000"
  "12|0.5000"
  "8|0.5000"
  "10|0.5002"
  "10|0.4998"
  "12|0.5002"
  "12|0.4998"
)

echo "[hook][microgrid] model=$model round=$round"

for item in "${GRID[@]}"; do
  IFS='|' read -r d h <<< "$item"
  hs="${h/./}"
  out_txt="$root/hi7_example/example_hms5c4040ble640_hookmg_r${round}_D${d}_H${hs}_20140901_20141109_i10.txt"
  out_time="$root/hi7_example/time_example_hms5c4040ble640_hookmg_r${round}_D${d}_H${hs}_20140901_20141109_i10.txt"
  out_csv="$root/hi7_example/example_hms5c4040ble640_hookmg_r${round}_D${d}_H${hs}_20140901_20141109_i10.csv"

  if [[ -s "$out_csv" ]]; then
    echo "[hook][microgrid] skip D=$d H=$h (csv exists)"
    continue
  fi

  stdbuf -i0 -o0 -e0 java -Xmx40g \
    -cp "$SIM_CP" simulate.Simulate \
    -s 2014-09-30 \
    -i 10 \
    -p "${train_dir}/" \
    -t "${test_dir}/" \
    -a "(meta.AdaptiveRandomForest -a 6 -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
    -D "$d" \
    -V 30 \
    -H "$h" \
    -r 1 > "$out_txt" 2> "$out_time"

  python parse.py "$out_txt" >/dev/null
done

summary_json="$state_dir/hms_microgrid_round${round}_summary.json"
summary_md="$root/docs/hms_microgrid_round${round}_summary.md"
python - <<'PY' "$root" "$round" "$nollm_csv" "$summary_json" "$summary_md"
import json
import pandas as pd
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
round_idx = sys.argv[2]
nollm_csv = Path(sys.argv[3])
summary_json = Path(sys.argv[4])
summary_md = Path(sys.argv[5])

base = pd.read_csv(nollm_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())

pat = re.compile(rf"example_hms5c4040ble640_hookmg_r{round_idx}_D(\d+)_H([0-9]+)_20140901_20141109_i10\.csv$")
rows = []
for csv in sorted((root / "hi7_example").glob(f"example_hms5c4040ble640_hookmg_r{round_idx}_D*_H*_20140901_20141109_i10.csv")):
    m = pat.match(csv.name)
    if not m:
        continue
    d = int(m.group(1))
    hs = m.group(2)
    if len(hs) == 5:
        h = float(hs[0] + "." + hs[1:])
    else:
        h = float(hs[:1] + "." + hs[1:])

    df = pd.read_csv(csv)
    df = df[df["date"].notna()]
    if df.empty:
        continue
    rec = float(df["l_Recall_c1"].mean())
    acc = float(df["l_clf_corrct"].mean())
    rows.append({
        "d": d,
        "h": h,
        "csv": str(csv),
        "recall": rec,
        "acc": acc,
        "d_recall": rec - base_recall,
        "d_acc": acc - base_acc,
        "pass_acc_guard": acc >= (base_acc - 1.0),
        "pass_recall_goal": rec >= base_recall,
    })

if not rows:
    raise SystemExit("no microgrid csv rows produced")

df = pd.DataFrame(rows)
feasible = df[(df["pass_acc_guard"]) & (df["pass_recall_goal"])]
if not feasible.empty:
    best = feasible.sort_values("recall", ascending=False).iloc[0].to_dict()
else:
    guard = df[df["pass_acc_guard"]]
    if not guard.empty:
        best = guard.sort_values("recall", ascending=False).iloc[0].to_dict()
    else:
        best = df.sort_values("recall", ascending=False).iloc[0].to_dict()

payload = {
    "round": int(round_idx),
    "baseline": {"recall": base_recall, "acc": base_acc},
    "rows": rows,
    "best": best,
    "pass_found": bool((best["recall"] >= base_recall) and (best["acc"] >= base_acc - 1.0)),
}
summary_json.parent.mkdir(parents=True, exist_ok=True)
summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

lines = [
    f"# HMS microgrid round {round_idx}",
    "",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}",
    "",
    "| D | H | recall | acc | Δrecall | Δacc | ACC守卫 | Recall目标 |",
    "|---:|---:|---:|---:|---:|---:|:---:|:---:|",
]
for r in sorted(rows, key=lambda x: (x["d"], x["h"])):
    lines.append(
        f"| {r['d']} | {r['h']:.4f} | {r['recall']:.4f} | {r['acc']:.4f} | {r['d_recall']:+.4f} | {r['d_acc']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} | {'Y' if r['pass_recall_goal'] else 'N'} |"
    )
lines += ["", f"- selected: D={int(best['d'])}, H={best['h']:.4f}"]
summary_md.parent.mkdir(parents=True, exist_ok=True)
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_json)
PY

best_csv="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["csv"])
PY
)"
best_d="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(int(p["best"]["d"]))
PY
)"
best_h="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(float(p["best"]["h"]))
PY
)"
pass_found="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print("1" if p.get("pass_found") else "0")
PY
)"

best_txt="${best_csv%.csv}.txt"
best_time="${best_txt/example_/time_example_}"
cp -f "$best_csv" "$root/hi7_example/example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.csv"
if [[ -f "$best_txt" ]]; then
  cp -f "$best_txt" "$root/hi7_example/example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.txt"
fi
if [[ -f "$best_time" ]]; then
  cp -f "$best_time" "$root/hi7_example/time_example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.txt"
fi

# Record tuned D/H into policy only when a valid pass point is found.
if [[ "$pass_found" == "1" ]]; then
  python - <<'PY' "$policy_file" "$best_d" "$best_h"
import yaml,sys
path=sys.argv[1]
best_d=int(sys.argv[2])
best_h=float(sys.argv[3])
with open(path, "r", encoding="utf-8") as f:
    cfg=yaml.safe_load(f) or {}
cfg["simulate_downsample_ratio"]=best_d
cfg["simulate_threshold_h"]=float(f"{best_h:.4f}")
with open(path, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=False)
PY
fi

echo "[hook][microgrid] selected D=$best_d H=$best_h pass_found=$pass_found"
