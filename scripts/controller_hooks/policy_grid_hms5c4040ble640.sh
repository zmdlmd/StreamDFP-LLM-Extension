#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
model="${1:-}"
round="${2:-0}"
root="${3:-$DEFAULT_ROOT}"

if [[ "$model" != "hms5c4040ble640" ]]; then
  echo "[hook][policy_grid] skip model=$model"
  exit 0
fi

cd "$root"

state_dir="$root/logs/cross_model_controller"
mkdir -p "$state_dir"

data_root="$root/data/data_2014/2014/"
features="$root/pyloader/features_erg/hi7_all.txt"
disk_model="HGST HMS5C4040BLE640"
policy_key="hgsthms5c4040ble640"
policy_file="$root/llm/calibration/models/hgsthms5c4040ble640.yaml"
policy_tmp="/tmp/hms_policy_grid_round${round}.yaml"

cache_v6="$root/llm_cache_hms5c4040ble640_fs_robustv6_recall_20140901_20141109.jsonl"
cache_v5="$root/llm_cache_hms5c4040ble640_fs_robustv5_20140901_20141109.jsonl"
cache_v4="$root/llm_cache_hms5c4040ble640_fs_robustv4_targeted_20140901_20141109.jsonl"
cache_v3="$root/llm_cache_hms5c4040ble640_fs_robustv3_20140901_20141109.jsonl"
cache_v2="$root/llm_cache_hms5c4040ble640_fs_robustv2_20140901_20141109.jsonl"
if [[ -f "$cache_v6" ]]; then
  cache="$cache_v6"
elif [[ -f "$cache_v5" ]]; then
  cache="$cache_v5"
elif [[ -f "$cache_v4" ]]; then
  cache="$cache_v4"
elif [[ -f "$cache_v3" ]]; then
  cache="$cache_v3"
else
  cache="$cache_v2"
fi

if [[ ! -f "$cache" ]]; then
  echo "[hook][policy_grid] missing cache: $cache" >&2
  exit 2
fi

nollm_csv="$root/hi7_example/example_hms5c4040ble640_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
if [[ ! -f "$nollm_csv" ]]; then
  echo "[hook][policy_grid] missing baseline: $nollm_csv" >&2
  exit 2
fi

# tag|q|rule|map|alpha|keep|drop_unknown|allowed_roots
GRID=(
  "strict_070_r1_m60_a08_top8|0.70|true|0.60|0.8|event_top8_plus_meta|true|[power, temperature, media]"
  "mid_050_r1_m30_a08_top8|0.50|true|0.30|0.8|event_top8_plus_meta|true|[power, temperature, media]"
  "open_000_r0_m00_a10_all|0.00|false|0.00|1.0|all|false|[]"
  "open_000_r0_m00_a10_top8|0.00|false|0.00|1.0|event_top8_plus_meta|false|[]"
  "open_000_r0_m00_a10_top3|0.00|false|0.00|1.0|event_top3_plus_meta|false|[]"
  "open_000_r0_m00_a10_evt8|0.00|false|0.00|1.0|16,34,46,25,31,55,28,37|false|[]"
)

echo "[hook][policy_grid] model=$model round=$round cache=$(basename "$cache")"

for item in "${GRID[@]}"; do
  IFS='|' read -r tag q rule map alpha keep drop_unknown allowed_roots <<< "$item"

  train_dir="$root/pyloader/hi7_train_hms5c4040ble640_hookpg_r${round}_${tag}_20140901_20141109_aligned"
  test_dir="$root/pyloader/hi7_test_hms5c4040ble640_hookpg_r${round}_${tag}_20140901_20141109_aligned"
  out_txt="$root/hi7_example/example_hms5c4040ble640_hookpg_r${round}_${tag}_20140901_20141109_aligned_i10.txt"
  out_time="$root/hi7_example/time_example_hms5c4040ble640_hookpg_r${round}_${tag}_20140901_20141109_aligned_i10.txt"
  out_csv="$root/hi7_example/example_hms5c4040ble640_hookpg_r${round}_${tag}_20140901_20141109_aligned_i10.csv"

  if [[ -s "$out_csv" ]]; then
    echo "[hook][policy_grid] skip tag=$tag (csv exists)"
    continue
  fi

cat > "$policy_tmp" <<YAML
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
  $policy_key:
    enabled: true
    min_q_score: $q
    min_rule_match: $rule
    min_mapped_event_ratio: $map
    drop_unknown_root: $drop_unknown
    allowed_root_causes: $allowed_roots
    keep_dims: $keep
    llm_scale_alpha: $alpha
    fallback: nollm
YAML

  rm -rf "$train_dir" "$test_dir"
  mkdir -p "$train_dir" "$test_dir"

  python pyloader/run.py \
    -s 2014-09-01 \
    -p "$data_root" \
    -d "$disk_model" \
    -i 10 \
    -c "$features" \
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
    -M 70 \
    --llm_policy_config "$policy_tmp" \
    --llm_policy_model_key "$policy_key" \
    --llm_fallback_mode nollm

  stdbuf -i0 -o0 -e0 java -Xmx40g \
    -cp simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar \
    simulate.Simulate \
    -s 2014-09-30 \
    -i 10 \
    -p "$train_dir/" \
    -t "$test_dir/" \
    -a "(meta.AdaptiveRandomForest -a 6 -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
    -D 10 \
    -V 30 \
    -H 0.5000 \
    -r 1 > "$out_txt" 2> "$out_time"

  python parse.py "$out_txt" >/dev/null
done

summary_json="$state_dir/hms_policy_grid_round${round}_summary.json"
summary_md="$root/docs/hms_policy_grid_round${round}_summary.md"
python - <<'PY' "$root" "$round" "$nollm_csv" "$summary_json" "$summary_md"
import json
import pandas as pd
from pathlib import Path
import sys

root = Path(sys.argv[1])
round_idx = sys.argv[2]
nollm_csv = Path(sys.argv[3])
summary_json = Path(sys.argv[4])
summary_md = Path(sys.argv[5])

grid = [
    ("strict_070_r1_m60_a08_top8", 0.70, True, 0.60, 0.8, "event_top8_plus_meta"),
    ("mid_050_r1_m30_a08_top8", 0.50, True, 0.30, 0.8, "event_top8_plus_meta"),
    ("open_000_r0_m00_a10_all", 0.00, False, 0.00, 1.0, "all"),
    ("open_000_r0_m00_a10_top8", 0.00, False, 0.00, 1.0, "event_top8_plus_meta"),
    ("open_000_r0_m00_a10_top3", 0.00, False, 0.00, 1.0, "event_top3_plus_meta"),
    ("open_000_r0_m00_a10_evt8", 0.00, False, 0.00, 1.0, "16,34,46,25,31,55,28,37"),
]

base = pd.read_csv(nollm_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())

rows = []
for tag, q, rule, mp, alpha, keep in grid:
    csv = root / f"hi7_example/example_hms5c4040ble640_hookpg_r{round_idx}_{tag}_20140901_20141109_aligned_i10.csv"
    if not csv.exists():
        continue
    df = pd.read_csv(csv)
    df = df[df["date"].notna()]
    if df.empty:
        continue
    rec = float(df["l_Recall_c1"].mean())
    acc = float(df["l_clf_corrct"].mean())
    rows.append({
        "tag": tag,
        "q": q,
        "rule": rule,
        "map": mp,
        "alpha": alpha,
        "keep": keep,
        "csv": str(csv),
        "recall": rec,
        "acc": acc,
        "d_recall": rec - base_recall,
        "d_acc": acc - base_acc,
        "pass_acc_guard": acc >= (base_acc - 1.0),
    })

if not rows:
    raise SystemExit("no policy-grid csv rows produced")

df = pd.DataFrame(rows)
df_acc = df[df["pass_acc_guard"]]
if not df_acc.empty:
    best = df_acc.sort_values("recall", ascending=False).iloc[0].to_dict()
else:
    best = df.sort_values("recall", ascending=False).iloc[0].to_dict()

payload = {
    "round": int(round_idx),
    "baseline": {"recall": base_recall, "acc": base_acc},
    "rows": rows,
    "best": best,
}
summary_json.parent.mkdir(parents=True, exist_ok=True)
summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

lines = [
    f"# HMS policy grid round {round_idx}",
    "",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}",
    "",
    "| tag | recall | acc | Δrecall | Δacc | acc_guard |",
    "|---|---:|---:|---:|---:|:---:|",
]
for r in sorted(rows, key=lambda x: x["recall"], reverse=True):
    lines.append(
        f"| {r['tag']} | {r['recall']:.4f} | {r['acc']:.4f} | {r['d_recall']:+.4f} | {r['d_acc']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} |"
    )
lines += [
    "",
    f"- selected: `{best['tag']}`",
]
summary_md.parent.mkdir(parents=True, exist_ok=True)
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_json)
PY

selected_tag="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["tag"])
PY
)"

selected_q="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["q"])
PY
)"
selected_rule="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(str(p["best"]["rule"]).lower())
PY
)"
selected_map="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["map"])
PY
)"
selected_alpha="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["alpha"])
PY
)"
selected_keep="$(python - <<'PY' "$summary_json"
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    p=json.load(f)
print(p["best"]["keep"])
PY
)"

selected_txt="$root/hi7_example/example_hms5c4040ble640_hookpg_r${round}_${selected_tag}_20140901_20141109_aligned_i10.txt"
selected_time="$root/hi7_example/time_example_hms5c4040ble640_hookpg_r${round}_${selected_tag}_20140901_20141109_aligned_i10.txt"
selected_csv="$root/hi7_example/example_hms5c4040ble640_hookpg_r${round}_${selected_tag}_20140901_20141109_aligned_i10.csv"
selected_train="$root/pyloader/hi7_train_hms5c4040ble640_hookpg_r${round}_${selected_tag}_20140901_20141109_aligned"
selected_test="$root/pyloader/hi7_test_hms5c4040ble640_hookpg_r${round}_${selected_tag}_20140901_20141109_aligned"

# Publish selected run as current robustv2 candidate.
cp -f "$selected_txt" "$root/hi7_example/example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.txt"
cp -f "$selected_time" "$root/hi7_example/time_example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.txt"
cp -f "$selected_csv" "$root/hi7_example/example_hms5c4040ble640_fs_robustv2_20140901_20141109_aligned_i10.csv"

# Update policy gate params to selected config.
cat > "$policy_file" <<YAML
enabled: true
min_q_score: $selected_q
min_rule_match: $selected_rule
min_mapped_event_ratio: $selected_map
drop_unknown_root: true
allowed_root_causes: [power, temperature, media]
keep_dims: $selected_keep
llm_scale_alpha: $selected_alpha
fallback: nollm
YAML

cat > "$state_dir/hms_selected_round${round}.json" <<JSON
{
  "round": $round,
  "cache": "$cache",
  "tag": "$selected_tag",
  "q": $selected_q,
  "rule": $selected_rule,
  "map": $selected_map,
  "alpha": $selected_alpha,
  "keep": "$selected_keep",
  "train_dir": "$selected_train",
  "test_dir": "$selected_test",
  "csv": "$selected_csv"
}
JSON

echo "[hook][policy_grid] selected tag=$selected_tag"
