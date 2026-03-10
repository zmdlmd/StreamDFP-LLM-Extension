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
CACHE="$ROOT/llm_cache_hms5c4040ble640_fs_robustv6_recall_20140901_20141109.jsonl"
BASELINE_CSV="$ROOT/hi7_example/example_hms5c4040ble640_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"

STATE_DIR="$ROOT/logs/cross_model_controller"
mkdir -p "$STATE_DIR"

PHASE1_SUMMARY_CSV="$ROOT/docs/hms_round10_policy_a_grid.csv"
PHASE1_SUMMARY_MD="$ROOT/docs/hms_round10_policy_a_grid.md"
PHASE1_STATE_JSON="$STATE_DIR/hms_round10_phase1_state.json"
PHASE2_SUMMARY_CSV="$ROOT/docs/hms_round10_dh_microgrid.csv"
PHASE2_SUMMARY_MD="$ROOT/docs/hms_round10_dh_microgrid.md"
PHASE2_STATE_JSON="$STATE_DIR/hms_round10_phase2_state.json"

SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"

if [[ ! -f "$CACHE" ]]; then
  echo "[round10] missing cache: $CACHE" >&2
  exit 2
fi
if [[ ! -f "$BASELINE_CSV" ]]; then
  echo "[round10] missing baseline csv: $BASELINE_CSV" >&2
  exit 2
fi

mk_policy_file() {
  local tag="$1"
  local file="$2"
  case "$tag" in
    P0_strict)
      cat > "$file" <<'YAML'
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
  hgsthms5c4040ble640:
    enabled: true
    min_q_score: 0.70
    min_rule_match: true
    min_mapped_event_ratio: 0.60
    drop_unknown_root: true
    allowed_root_causes: [power, temperature, media]
    keep_dims: event_top8_plus_meta
    llm_scale_alpha: 0.8
    fallback: nollm
YAML
      ;;
    P1_open_all)
      cat > "$file" <<'YAML'
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
  hgsthms5c4040ble640:
    enabled: true
    min_q_score: 0.00
    min_rule_match: false
    min_mapped_event_ratio: 0.00
    drop_unknown_root: false
    allowed_root_causes: []
    keep_dims: all
    llm_scale_alpha: 1.0
    fallback: nollm
YAML
      ;;
    P2_meta_root_compact)
      cat > "$file" <<'YAML'
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
  hgsthms5c4040ble640:
    enabled: true
    min_q_score: 0.00
    min_rule_match: false
    min_mapped_event_ratio: 0.00
    drop_unknown_root: false
    allowed_root_causes: []
    keep_dims: 0,1,2,3,4,6,7,9,11,12,13
    llm_scale_alpha: 1.0
    fallback: nollm
YAML
      ;;
    P3_evt8_meta_compact)
      cat > "$file" <<'YAML'
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
  hgsthms5c4040ble640:
    enabled: true
    min_q_score: 0.00
    min_rule_match: false
    min_mapped_event_ratio: 0.00
    drop_unknown_root: false
    allowed_root_causes: []
    keep_dims: 6,7,9,11,12,13,16,25,28,31,34,37,46,55
    llm_scale_alpha: 1.0
    fallback: nollm
YAML
      ;;
    *)
      echo "[round10] unknown policy tag: $tag" >&2
      exit 2
      ;;
  esac
}

run_phase1_one() {
  local tag="$1"
  local arf_a="$2"

  local train_dir="$ROOT/pyloader/hi7_train_hms5c4040ble640_r10_${tag}_a${arf_a}_${DATE_TAG}_aligned"
  local test_dir="$ROOT/pyloader/hi7_test_hms5c4040ble640_r10_${tag}_a${arf_a}_${DATE_TAG}_aligned"
  local out_txt="$ROOT/hi7_example/example_hms5c4040ble640_r10_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.txt"
  local out_time="$ROOT/hi7_example/time_example_hms5c4040ble640_r10_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.txt"
  local out_csv="$ROOT/hi7_example/example_hms5c4040ble640_r10_${tag}_a${arf_a}_D10_H05000_${DATE_TAG}_i10.csv"
  local policy_tmp="/tmp/hms_round10_${tag}.yaml"

  if [[ -s "$out_csv" ]]; then
    echo "[round10][phase1] skip $tag a=$arf_a (csv exists)"
    return
  fi

  mk_policy_file "$tag" "$policy_tmp"
  rm -rf "$train_dir" "$test_dir"
  mkdir -p "$train_dir" "$test_dir"

  echo "[round10][phase1] run.py $tag a=$arf_a"
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

  echo "[round10][phase1] simulate $tag a=$arf_a"
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

echo "[round10] Phase1 start"
for tag in P0_strict P1_open_all P2_meta_root_compact P3_evt8_meta_compact; do
  for arf_a in 6 12 18 24; do
    run_phase1_one "$tag" "$arf_a"
  done
done

python - <<'PY' "$ROOT" "$BASELINE_CSV" "$PHASE1_SUMMARY_CSV" "$PHASE1_SUMMARY_MD" "$PHASE1_STATE_JSON" "$DATE_TAG"
import json
from pathlib import Path
import pandas as pd
import sys

root = Path(sys.argv[1])
baseline_csv = Path(sys.argv[2])
out_csv = Path(sys.argv[3])
out_md = Path(sys.argv[4])
state_json = Path(sys.argv[5])
date_tag = sys.argv[6]

base = pd.read_csv(baseline_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())
acc_guard = base_acc - 1.0

rows = []
for tag in ["P0_strict", "P1_open_all", "P2_meta_root_compact", "P3_evt8_meta_compact"]:
    for arf_a in [6, 12, 18, 24]:
        csv = root / f"hi7_example/example_hms5c4040ble640_r10_{tag}_a{arf_a}_D10_H05000_{date_tag}_i10.csv"
        if not csv.exists():
            continue
        df = pd.read_csv(csv)
        df = df[df["date"].notna()]
        if df.empty:
            continue
        rec = float(df["l_Recall_c1"].mean())
        acc = float(df["l_clf_corrct"].mean())
        rows.append({
            "policy_tag": tag,
            "arf_a": arf_a,
            "csv": str(csv.relative_to(root)),
            "recall": rec,
            "acc": acc,
            "delta_recall": rec - base_recall,
            "delta_acc": acc - base_acc,
            "pass_acc_guard": bool(acc >= acc_guard),
        })

if not rows:
    raise SystemExit("phase1 produced no csv rows")

res = pd.DataFrame(rows).sort_values(["pass_acc_guard", "recall"], ascending=[False, False]).reset_index(drop=True)
res.to_csv(out_csv, index=False)

guard = res[res["pass_acc_guard"]]
if guard.empty:
    top2 = res.sort_values("recall", ascending=False).head(2).copy()
    top2["risk_flag"] = "HIGH"
else:
    top2 = guard.sort_values("recall", ascending=False).head(2).copy()
    if len(top2) < 2:
        fill = res[~res.index.isin(top2.index)].sort_values("recall", ascending=False).head(2 - len(top2)).copy()
        fill["risk_flag"] = "HIGH"
        top2["risk_flag"] = "OK"
        top2 = pd.concat([top2, fill], ignore_index=True)
    else:
        top2["risk_flag"] = "OK"

state = {
    "baseline": {
        "recall": base_recall,
        "acc": base_acc,
        "acc_guard": acc_guard,
    },
    "top2": top2[["policy_tag", "arf_a", "csv", "risk_flag"]].to_dict(orient="records"),
    "rows": rows,
}
state_json.parent.mkdir(parents=True, exist_ok=True)
state_json.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

md_lines = [
    "# HMS Round10 Phase1: Policy x ARF-a Grid",
    "",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}, acc_guard={acc_guard:.4f}",
    "",
    "| policy_tag | arf_a | recall | acc | Δrecall | Δacc | ACC_guard |",
    "|---|---:|---:|---:|---:|---:|:---:|",
]
for _, r in res.sort_values(["recall", "acc"], ascending=[False, False]).iterrows():
    md_lines.append(
        f"| {r['policy_tag']} | {int(r['arf_a'])} | {r['recall']:.4f} | {r['acc']:.4f} | {r['delta_recall']:+.4f} | {r['delta_acc']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} |"
    )
md_lines += ["", "## Top-2 for Phase2", "", "| rank | policy_tag | arf_a | risk_flag |", "|---:|---|---:|---|"]
for idx, r in enumerate(top2.itertuples(index=False), 1):
    md_lines.append(f"| {idx} | {r.policy_tag} | {int(r.arf_a)} | {r.risk_flag} |")
out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(out_csv)
print(out_md)
print(state_json)
PY

echo "[round10] Phase2 start"
python - <<'PY' "$ROOT" "$PHASE1_STATE_JSON" "$BASELINE_CSV" "$PHASE2_SUMMARY_CSV" "$PHASE2_SUMMARY_MD" "$PHASE2_STATE_JSON" "$DATE_TAG" "$SIM_CP"
import json
from pathlib import Path
import subprocess
import pandas as pd
import sys

root = Path(sys.argv[1])
phase1_state = Path(sys.argv[2])
baseline_csv = Path(sys.argv[3])
out_csv = Path(sys.argv[4])
out_md = Path(sys.argv[5])
phase2_state = Path(sys.argv[6])
date_tag = sys.argv[7]
sim_cp = sys.argv[8]

with phase1_state.open("r", encoding="utf-8") as f:
    p1 = json.load(f)
top2 = p1.get("top2", [])
if not top2:
    raise SystemExit("phase1 top2 empty")

base = pd.read_csv(baseline_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())
acc_guard = base_acc - 1.0

rows = []
for item in top2:
    tag = item["policy_tag"]
    arf_a = int(item["arf_a"])
    train_dir = root / f"pyloader/hi7_train_hms5c4040ble640_r10_{tag}_a{arf_a}_{date_tag}_aligned"
    test_dir = root / f"pyloader/hi7_test_hms5c4040ble640_r10_{tag}_a{arf_a}_{date_tag}_aligned"
    if not train_dir.exists() or not test_dir.exists():
        raise SystemExit(f"missing train/test for {tag} a={arf_a}")

    for d in [8, 10, 12]:
        for h in [0.4996, 0.4998, 0.5000, 0.5002]:
            hs = f"{h:.4f}".replace(".", "")
            txt = root / f"hi7_example/example_hms5c4040ble640_r10_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
            tim = root / f"hi7_example/time_example_hms5c4040ble640_r10_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
            csv = root / f"hi7_example/example_hms5c4040ble640_r10_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.csv"

            if not csv.exists() or csv.stat().st_size == 0:
                cmd = [
                    "java", "-Xmx40g", "-cp", sim_cp, "simulate.Simulate",
                    "-s", "2014-09-30",
                    "-i", "10",
                    "-p", str(train_dir) + "/",
                    "-t", str(test_dir) + "/",
                    "-a", f"(meta.AdaptiveRandomForest -a {arf_a} -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))",
                    "-D", str(d),
                    "-V", "30",
                    "-H", f"{h:.4f}",
                    "-r", "1",
                ]
                with txt.open("w", encoding="utf-8") as f_out, tim.open("w", encoding="utf-8") as f_err:
                    subprocess.run(cmd, check=True, cwd=str(root), stdout=f_out, stderr=f_err)
                subprocess.run(["python", "parse.py", str(txt)], check=True, cwd=str(root), stdout=subprocess.DEVNULL)

            df = pd.read_csv(csv)
            df = df[df["date"].notna()]
            if df.empty:
                continue
            rec = float(df["l_Recall_c1"].mean())
            acc = float(df["l_clf_corrct"].mean())
            rows.append({
                "policy_tag": tag,
                "arf_a": arf_a,
                "D": d,
                "H": h,
                "csv": str(csv.relative_to(root)),
                "recall": rec,
                "acc": acc,
                "delta_recall": rec - base_recall,
                "delta_acc": acc - base_acc,
                "pass_acc_guard": bool(acc >= acc_guard),
                "pass_recall_goal": bool(rec >= base_recall),
            })

if not rows:
    raise SystemExit("phase2 produced no rows")

res = pd.DataFrame(rows)
res.to_csv(out_csv, index=False)

both = res[(res["pass_acc_guard"]) & (res["pass_recall_goal"])]
if not both.empty:
    best = both.sort_values("recall", ascending=False).iloc[0].to_dict()
    decision = "PASS_BOTH"
else:
    guard = res[res["pass_acc_guard"]]
    if not guard.empty:
        best = guard.sort_values("recall", ascending=False).iloc[0].to_dict()
        decision = "PASS_ACC_ONLY"
    else:
        best = res.sort_values("recall", ascending=False).iloc[0].to_dict()
        decision = "FAIL_GUARD"

phase2_payload = {
    "baseline": {"recall": base_recall, "acc": base_acc, "acc_guard": acc_guard},
    "decision": decision,
    "best": best,
    "rows": rows,
}
phase2_state.parent.mkdir(parents=True, exist_ok=True)
phase2_state.write_text(json.dumps(phase2_payload, indent=2, ensure_ascii=False), encoding="utf-8")

md_lines = [
    "# HMS Round10 Phase2: D/H microgrid on Top-2",
    "",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}, acc_guard={acc_guard:.4f}",
    f"- decision={decision}",
    "",
    "| policy_tag | arf_a | D | H | recall | acc | Δrecall | Δacc | ACC_guard | Recall_goal |",
    "|---|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|",
]
for _, r in res.sort_values(["recall", "acc"], ascending=[False, False]).iterrows():
    md_lines.append(
        f"| {r['policy_tag']} | {int(r['arf_a'])} | {int(r['D'])} | {r['H']:.4f} | {r['recall']:.4f} | {r['acc']:.4f} | {r['delta_recall']:+.4f} | {r['delta_acc']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} | {'Y' if r['pass_recall_goal'] else 'N'} |"
    )
md_lines += [
    "",
    "## Selected Best",
    "",
    f"- policy_tag={best['policy_tag']}, arf_a={int(best['arf_a'])}, D={int(best['D'])}, H={best['H']:.4f}",
    f"- recall={best['recall']:.4f}, acc={best['acc']:.4f}",
]
out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(out_csv)
print(out_md)
print(phase2_state)
PY

echo "[round10] done phase1+phase2"
