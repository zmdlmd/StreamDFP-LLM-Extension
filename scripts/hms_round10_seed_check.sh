#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
cd "$ROOT"

DATE_TAG="20140901_20141109"
MODEL_KEY="hgsthms5c4040ble640"
POLICY_FILE="$ROOT/llm/calibration/models/hgsthms5c4040ble640.yaml"
BASELINE_CSV="$ROOT/hi7_example/example_hms5c4040ble640_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"
PHASE2_STATE_JSON="$ROOT/logs/cross_model_controller/hms_round10_phase2_state.json"
SEED_SUMMARY_CSV="$ROOT/docs/hms_round10_seed_stability.csv"
SEED_SUMMARY_MD="$ROOT/docs/hms_round10_seed_stability.md"
FINAL_DECISION_MD="$ROOT/docs/hms_round10_final_decision.md"
SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"

if [[ ! -f "$PHASE2_STATE_JSON" ]]; then
  echo "[round10-seed] missing phase2 state: $PHASE2_STATE_JSON" >&2
  exit 2
fi
if [[ ! -f "$BASELINE_CSV" ]]; then
  echo "[round10-seed] missing baseline csv: $BASELINE_CSV" >&2
  exit 2
fi

python - <<'PY' "$ROOT" "$PHASE2_STATE_JSON" "$BASELINE_CSV" "$SEED_SUMMARY_CSV" "$SEED_SUMMARY_MD" "$FINAL_DECISION_MD" "$POLICY_FILE" "$DATE_TAG" "$SIM_CP"
import json
from pathlib import Path
import shutil
import subprocess
import pandas as pd
import yaml
import sys

root = Path(sys.argv[1])
phase2_state = Path(sys.argv[2])
baseline_csv = Path(sys.argv[3])
seed_csv_out = Path(sys.argv[4])
seed_md_out = Path(sys.argv[5])
final_md_out = Path(sys.argv[6])
policy_file = Path(sys.argv[7])
date_tag = sys.argv[8]
sim_cp = sys.argv[9]

with phase2_state.open("r", encoding="utf-8") as f:
    p2 = json.load(f)
best = p2["best"]

tag = str(best["policy_tag"])
arf_a = int(best["arf_a"])
d = int(best["D"])
h = float(best["H"])
hs = f"{h:.4f}".replace(".", "")

train_dir = root / f"pyloader/hi7_train_hms5c4040ble640_r10_{tag}_a{arf_a}_{date_tag}_aligned"
test_dir = root / f"pyloader/hi7_test_hms5c4040ble640_r10_{tag}_a{arf_a}_{date_tag}_aligned"
if not train_dir.exists() or not test_dir.exists():
    raise SystemExit("missing train/test from phase1 for seed check")

base = pd.read_csv(baseline_csv)
base = base[base["date"].notna()]
base_recall = float(base["l_Recall_c1"].mean())
base_acc = float(base["l_clf_corrct"].mean())
acc_guard = base_acc - 1.0

rows = []
for seed in [1, 7, 13]:
    txt = root / f"hi7_example/example_hms5c4040ble640_r10_seed_s{seed}_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
    tim = root / f"hi7_example/time_example_hms5c4040ble640_r10_seed_s{seed}_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
    csv = root / f"hi7_example/example_hms5c4040ble640_r10_seed_s{seed}_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.csv"

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
            "-r", str(seed),
        ]
        with txt.open("w", encoding="utf-8") as f_out, tim.open("w", encoding="utf-8") as f_err:
            subprocess.run(cmd, check=True, cwd=str(root), stdout=f_out, stderr=f_err)
        subprocess.run(["python", "parse.py", str(txt)], check=True, cwd=str(root), stdout=subprocess.DEVNULL)

    df = pd.read_csv(csv)
    df = df[df["date"].notna()]
    if df.empty:
        continue
    recall = float(df["l_Recall_c1"].mean())
    acc = float(df["l_clf_corrct"].mean())
    rows.append({
        "seed": seed,
        "policy_tag": tag,
        "arf_a": arf_a,
        "D": d,
        "H": h,
        "csv": str(csv.relative_to(root)),
        "recall": recall,
        "acc": acc,
        "delta_recall": recall - base_recall,
        "delta_acc": acc - base_acc,
        "pass_acc_guard": bool(acc >= acc_guard),
        "pass_recall_goal": bool(recall >= base_recall),
    })

if not rows:
    raise SystemExit("seed check produced no rows")

seed_df = pd.DataFrame(rows)
seed_df.to_csv(seed_csv_out, index=False)

recall_mean = float(seed_df["recall"].mean())
acc_mean = float(seed_df["acc"].mean())
pass_final = bool((recall_mean >= base_recall) and (acc_mean >= acc_guard))

seed_md = [
    "# HMS Round10 Phase3: Seed Stability",
    "",
    f"- selected config: policy={tag}, arf_a={arf_a}, D={d}, H={h:.4f}",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}, acc_guard={acc_guard:.4f}",
    f"- mean recall={recall_mean:.4f}, mean acc={acc_mean:.4f}, pass_final={'Y' if pass_final else 'N'}",
    "",
    "| seed | recall | acc | Δrecall | Δacc | ACC_guard | Recall_goal |",
    "|---:|---:|---:|---:|---:|:---:|:---:|",
]
for _, r in seed_df.sort_values("seed").iterrows():
    seed_md.append(
        f"| {int(r['seed'])} | {r['recall']:.4f} | {r['acc']:.4f} | {r['delta_recall']:+.4f} | {r['delta_acc']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} | {'Y' if r['pass_recall_goal'] else 'N'} |"
    )
seed_md_out.write_text("\n".join(seed_md) + "\n", encoding="utf-8")

# Derive policy fields from selected tag.
policy_defs = {
    "P0_strict": {
        "enabled": True,
        "min_q_score": 0.70,
        "min_rule_match": True,
        "min_mapped_event_ratio": 0.60,
        "drop_unknown_root": True,
        "allowed_root_causes": ["power", "temperature", "media"],
        "keep_dims": "event_top8_plus_meta",
        "llm_scale_alpha": 0.8,
        "fallback": "nollm",
    },
    "P1_open_all": {
        "enabled": True,
        "min_q_score": 0.00,
        "min_rule_match": False,
        "min_mapped_event_ratio": 0.00,
        "drop_unknown_root": False,
        "allowed_root_causes": [],
        "keep_dims": "all",
        "llm_scale_alpha": 1.0,
        "fallback": "nollm",
    },
    "P2_meta_root_compact": {
        "enabled": True,
        "min_q_score": 0.00,
        "min_rule_match": False,
        "min_mapped_event_ratio": 0.00,
        "drop_unknown_root": False,
        "allowed_root_causes": [],
        "keep_dims": "0,1,2,3,4,6,7,9,11,12,13",
        "llm_scale_alpha": 1.0,
        "fallback": "nollm",
    },
    "P3_evt8_meta_compact": {
        "enabled": True,
        "min_q_score": 0.00,
        "min_rule_match": False,
        "min_mapped_event_ratio": 0.00,
        "drop_unknown_root": False,
        "allowed_root_causes": [],
        "keep_dims": "6,7,9,11,12,13,16,25,28,31,34,37,46,55",
        "llm_scale_alpha": 1.0,
        "fallback": "nollm",
    },
}

decision_lines = [
    "# HMS Round10 Final Decision",
    "",
    f"- selected config: policy={tag}, arf_a={arf_a}, D={d}, H={h:.4f}",
    f"- baseline recall={base_recall:.4f}, acc={base_acc:.4f}, acc_guard={acc_guard:.4f}",
    f"- seed mean recall={recall_mean:.4f}, seed mean acc={acc_mean:.4f}",
]

if pass_final:
    cfg = {}
    if policy_file.exists():
        with policy_file.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    cfg.update(policy_defs[tag])
    cfg["simulate_downsample_ratio"] = int(d)
    cfg["simulate_threshold_h"] = float(f"{h:.4f}")
    cfg["simulate_arf_a"] = int(arf_a)
    with policy_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=False)

    # Promote seed-1 run as official robustv2 input for robust report.
    src_csv = root / f"hi7_example/example_hms5c4040ble640_r10_seed_s1_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.csv"
    src_txt = root / f"hi7_example/example_hms5c4040ble640_r10_seed_s1_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
    src_time = root / f"hi7_example/time_example_hms5c4040ble640_r10_seed_s1_{tag}_a{arf_a}_D{d}_H{hs}_{date_tag}_i10.txt"
    dst_csv = root / f"hi7_example/example_hms5c4040ble640_fs_robustv2_{date_tag}_aligned_i10.csv"
    dst_txt = root / f"hi7_example/example_hms5c4040ble640_fs_robustv2_{date_tag}_aligned_i10.txt"
    dst_time = root / f"hi7_example/time_example_hms5c4040ble640_fs_robustv2_{date_tag}_aligned_i10.txt"
    shutil.copy2(src_csv, dst_csv)
    if src_txt.exists():
        shutil.copy2(src_txt, dst_txt)
    if src_time.exists():
        shutil.copy2(src_time, dst_time)

    # Refresh robust report.
    subprocess.run(["bash", "./run_robust_eval_report_v2.sh"], check=True, cwd=str(root))

    decision_lines += [
        "",
        "## Decision",
        "",
        "- PASS: 达到 `Recall>=no-LLM` 且 `ACC>=no-LLM-1.0pp`（按 seed mean）。",
        f"- 已更新 policy: `{policy_file}`",
        "- 已刷新 `docs/llm_robust_eval_report_v2.{csv,md}`。",
    ]
else:
    decision_lines += [
        "",
        "## Decision",
        "",
        "- FAIL: 未同时满足 Recall 与 ACC 守卫。",
        "- 维持 `FALLBACK=nollm`，不覆盖当前 robustv2 对外结果。",
        "- 建议进入下一轮单次定向重抽取（本轮不执行）。",
    ]

final_md_out.write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
print(seed_csv_out)
print(seed_md_out)
print(final_md_out)
PY

echo "[round10-seed] done"
