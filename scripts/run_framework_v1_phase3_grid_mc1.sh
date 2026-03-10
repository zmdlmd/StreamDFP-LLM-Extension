#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

# MC1 data/loader params (align run_mc1_loader.sh)
DATA_PATH="${DATA_PATH:-$ROOT/data/ssd_2018/}"
FEATURES_PATH="${FEATURES_PATH:-$ROOT/pyloader/features_erg/mc1_all.txt}"
DISK_MODEL="${DISK_MODEL:-MC1}"
DATE_FORMAT="${DATE_FORMAT:-%Y%m%d}"
START_DATE="${START_DATE:-20180103}"
ITER_DAYS="${ITER_DAYS:-10}"
OPTIONS="${OPTIONS:-3,4,6}"
FORGET_TYPE="${FORGET_TYPE:-sliding}"
POSITIVE_WINDOW="${POSITIVE_WINDOW:-30}"
VALIDATION_WINDOW="${VALIDATION_WINDOW:-30}"
NEGATIVE_WINDOW="${NEGATIVE_WINDOW:-7}"
LABEL_DAYS="${LABEL_DAYS:-20}"

# Simulate params (align run_mc1_mlp.sh)
SIM_START="${SIM_START:-2018-02-01}"
SIM_ITER_DAYS="${SIM_ITER_DAYS:-10}"
CLASS_INDEX="${CLASS_INDEX:-43}"
CLF_NAME="${CLF_NAME:-meta.MultiLayerPerceptron}"
LEARNING_RATE="${LEARNING_RATE:-0.5}"
NUM_RESET="${NUM_RESET:-1000}"
THRESHOLD="${THRESHOLD:-0.5}"
DOWN_SAMPLE="${DOWN_SAMPLE:-2}"
SEED="${SEED:-1}"
JAVA_XMX="${JAVA_XMX:-40g}"

# Cache source + grid settings
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"       # fs|zs
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}" # legacy|structured_v2
PHASE3_DIM_KEYS="${PHASE3_DIM_KEYS:-compact9,compact14}" # comma-separated subset (full70 handled separately)
PHASE3_COMBO_LIMIT="${PHASE3_COMBO_LIMIT:-12}" # run N new combos per invocation (0 means no limit)
CONTINUE_ON_ERROR="${CONTINUE_ON_ERROR:-1}" # 1 continue grid on per-combo failure
RUN_TAG="${RUN_TAG:-pilot20k}"
KEEP_VARIANT="${KEEP_VARIANT:-0}"
KEEP_ARFF="${KEEP_ARFF:-0}"
TAG_SUFFIX="${TAG_SUFFIX:-}"
DRY_RUN="${DRY_RUN:-0}"

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_mc1}"
VARIANT_DIR="${VARIANT_DIR:-$ROOT/llm/framework_v1_mc1/phase3_variants}"
DOC_DIR="${DOC_DIR:-$ROOT/docs}"
OUT_DIR="${OUT_DIR:-$ROOT/llm/framework_v1_mc1}"
REPORT_DIR="${REPORT_DIR:-$ROOT/mc1_mlp}"
mkdir -p "$STATE_DIR" "$VARIANT_DIR" "$DOC_DIR" "$REPORT_DIR"

WINDOW_TEXT="${WINDOW_TEXT:-$OUT_DIR/window_text_mc1_${RUN_TAG}.jsonl}"
CACHE_IN="${CACHE_IN:-$OUT_DIR/cache_mc1_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${RUN_TAG}.jsonl}"
BASELINE_CSV="${BASELINE_CSV:-$ROOT/mc1_mlp/example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[phase3_mc1] DRY_RUN=1"
  echo "  CACHE_IN=$CACHE_IN"
  echo "  WINDOW_TEXT=$WINDOW_TEXT"
  echo "  BASELINE_CSV=$BASELINE_CSV"
  echo "  grid: 3 dims x 3 q x 2 sev x 2 rule = 36 combos"
  echo "  PHASE3_COMBO_LIMIT=$PHASE3_COMBO_LIMIT"
  echo "  CONTINUE_ON_ERROR=$CONTINUE_ON_ERROR"
  exit 0
fi

if [[ ! -f "$CACHE_IN" ]]; then
  echo "[phase3_mc1] missing cache: $CACHE_IN" >&2
  exit 2
fi
if [[ ! -f "$WINDOW_TEXT" ]]; then
  echo "[phase3_mc1] missing window_text: $WINDOW_TEXT" >&2
  exit 2
fi
if [[ ! -f "$BASELINE_CSV" ]]; then
  echo "[phase3_mc1] missing baseline csv: $BASELINE_CSV" >&2
  exit 2
fi

RECORDS_TSV="${RECORDS_TSV:-$STATE_DIR/phase3_mc1_combo_records.tsv}"
SUMMARY_CSV="${SUMMARY_CSV:-$DOC_DIR/prearff_grid_mc1_v1.csv}"
SUMMARY_MD="${SUMMARY_MD:-$DOC_DIR/prearff_grid_mc1_v1.md}"
: > "$RECORDS_TSV"
printf "dim_key\tq_gate\tsev_sum_gate\trequire_rule_match\tstatus\tvariant_cache\tresult_csv\tbaseline_csv\n" >> "$RECORDS_TSV"

all_dim_specs=("compact9:event_top3_plus_meta:9:1" "compact14:event_top8_plus_meta:14:1" "full70:all:79:0")
dim_specs=()
for dim_spec in "${all_dim_specs[@]}"; do
  dim_key="${dim_spec%%:*}"
  if [[ ",${PHASE3_DIM_KEYS}," == *",${dim_key},"* ]]; then
    dim_specs+=("$dim_spec")
  fi
done
if [[ "${#dim_specs[@]}" -eq 0 ]]; then
  echo "[phase3_mc1] no valid dim spec selected by PHASE3_DIM_KEYS=${PHASE3_DIM_KEYS}" >&2
  exit 2
fi

executed_new=0
stop_requested=0

for dim_spec in "${dim_specs[@]}"; do
  IFS=':' read -r dim_key keep_profile llm_dim compact_front <<< "$dim_spec"

  for qspec in "0.0:00" "0.35:35" "0.55:55"; do
    IFS=':' read -r q_gate q_tag <<< "$qspec"
    for sspec in "0.0:00" "0.8:08"; do
      IFS=':' read -r sev_gate sev_tag <<< "$sspec"
      for req in 0 1; do
        tag="mc1_${dim_key}_q${q_tag}_s${sev_tag}_r${req}_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${RUN_TAG}"
        if [[ -n "$TAG_SUFFIX" ]]; then
          tag="${tag}_${TAG_SUFFIX}"
        fi

        variant_cache="$VARIANT_DIR/${tag}.jsonl"
        train_dir="$ROOT/pyloader/phase3_train_${tag}"
        test_dir="$ROOT/pyloader/phase3_test_${tag}"
        out_txt="$REPORT_DIR/phase3_${tag}_i${SIM_ITER_DAYS}.txt"
        out_time="$REPORT_DIR/time_phase3_${tag}_i${SIM_ITER_DAYS}.txt"
        out_csv="$REPORT_DIR/phase3_${tag}_i${SIM_ITER_DAYS}.csv"

        if [[ -s "$out_csv" ]]; then
          echo "[phase3_mc1] skip existing csv $tag"
          printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$dim_key" "$q_gate" "$sev_gate" "$req" "existing" "$variant_cache" "$out_csv" "$BASELINE_CSV" >> "$RECORDS_TSV"
          continue
        fi

        if [[ "$PHASE3_COMBO_LIMIT" -gt 0 && "$executed_new" -ge "$PHASE3_COMBO_LIMIT" ]]; then
          stop_requested=1
          break
        fi

        echo "[phase3_mc1] run new combo $((executed_new + 1))/${PHASE3_COMBO_LIMIT} tag=$tag"
        status="ok"
        cache_variant_meta="$STATE_DIR/${tag}_cache_variant.json"

        echo "[phase3_mc1] build_cache_variant $tag"
        cmd=(python "$ROOT/llm/scripts/build_cache_variant.py"
          --in_cache "$CACHE_IN"
          --out_cache "$variant_cache"
          --q_gate "$q_gate"
          --sev_sum_gate "$sev_gate"
          --keep_profile "$keep_profile"
          --root_cause_field root_cause_pred
          --window_text_path "$WINDOW_TEXT"
        )
        if [[ "$req" == "1" ]]; then
          cmd+=(--require_rule_match)
        fi
        if [[ "$compact_front" == "1" ]]; then
          cmd+=(--compact_front)
        fi
        if ! "${cmd[@]}" > "$cache_variant_meta"; then
          status="cache_variant_fail"
        fi

        if [[ "$status" == "ok" ]]; then
          kept_count=$(python - <<'PY' "$cache_variant_meta"
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(int(data.get("kept", -1)))
except Exception:
    print(-1)
PY
)
          if [[ "$kept_count" == "0" ]]; then
            status="degenerate_skip"
            echo "[phase3_mc1] degenerate_skip tag=$tag kept=0"
          elif [[ "$kept_count" == "-1" ]]; then
            status="cache_meta_invalid"
            echo "[phase3_mc1] WARN cache meta parse failed: $cache_variant_meta"
          fi
        fi

        if [[ "$status" == "ok" ]]; then
          rm -rf "$train_dir" "$test_dir"
        fi

        if [[ "$status" == "ok" ]]; then
          echo "[phase3_mc1] run loader $tag"
          if ! START_DATE="$START_DATE" \
            DATE_FORMAT="$DATE_FORMAT" \
            DISK_MODEL="$DISK_MODEL" \
            DATA_PATH="$DATA_PATH" \
            ITER_DAYS="$ITER_DAYS" \
            FEATURES_PATH="$FEATURES_PATH" \
            OPTIONS="$OPTIONS" \
            FORGET_TYPE="$FORGET_TYPE" \
            POSITIVE_WINDOW="$POSITIVE_WINDOW" \
            VALIDATION_WINDOW="$VALIDATION_WINDOW" \
            NEGATIVE_WINDOW="$NEGATIVE_WINDOW" \
            LABEL_DAYS="$LABEL_DAYS" \
            TRAIN_PATH="${train_dir}/" \
            TEST_PATH="${test_dir}/" \
            REPORT_NAME="$tag" \
            TIME_PATH="$STATE_DIR/time_loader_${tag}.txt" \
            USE_LLM_FEATURES=1 \
            LLM_CACHE_PATH="$variant_cache" \
            LLM_DIM="$llm_dim" \
            bash "$ROOT/pyloader/run_mc1_loader.sh"; then
            status="loader_fail"
          fi
        fi

        if [[ "$status" == "ok" ]]; then
          echo "[phase3_mc1] run simulate $tag"
          if ! START_DATE="$SIM_START" \
            ITER_DAYS="$SIM_ITER_DAYS" \
            TRAIN_PATH="${train_dir}/" \
            TEST_PATH="${test_dir}/" \
            VALIDATION_WINDOW="$VALIDATION_WINDOW" \
            CLASS_INDEX="$CLASS_INDEX" \
            CLF_NAME="$CLF_NAME" \
            LEARNING_RATE="$LEARNING_RATE" \
            NUM_RESET="$NUM_RESET" \
            THRESHOLD="$THRESHOLD" \
            DOWN_SAMPLE="$DOWN_SAMPLE" \
            SEED="$SEED" \
            JAVA_XMX="$JAVA_XMX" \
            REPORT_DIR="${REPORT_DIR}/" \
            RES_NAME="$(basename "$out_txt")" \
            PATH_REPORT="$out_txt" \
            TIME_PATH="$out_time" \
            PARSE_OUTPUT=1 \
            bash "$ROOT/run_mc1_mlp.sh"; then
            status="simulate_fail"
          fi
        fi

        if [[ "$status" == "ok" && ! -s "$out_csv" ]]; then
          status="csv_missing"
        fi

        if [[ "$status" != "ok" ]]; then
          echo "[phase3_mc1] WARN status=$status tag=$tag"
        fi

        result_csv=""
        if [[ -s "$out_csv" ]]; then
          result_csv="$out_csv"
        fi
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$dim_key" "$q_gate" "$sev_gate" "$req" "$status" "$variant_cache" "$result_csv" "$BASELINE_CSV" >> "$RECORDS_TSV"
        executed_new=$((executed_new + 1))

        if [[ "$KEEP_ARFF" != "1" ]]; then
          rm -rf "$train_dir" "$test_dir"
        fi
        if [[ "$KEEP_VARIANT" != "1" ]]; then
          rm -f "$variant_cache"
        fi

        if [[ "$status" != "ok" && "$CONTINUE_ON_ERROR" != "1" ]]; then
          echo "[phase3_mc1] stop on error tag=$tag status=$status"
          stop_requested=1
          break
        fi
      done
      if [[ "$stop_requested" == "1" ]]; then
        break
      fi
    done
    if [[ "$stop_requested" == "1" ]]; then
      break
    fi
  done
  if [[ "$stop_requested" == "1" ]]; then
    break
  fi
done

echo "[phase3_mc1] executed_new=$executed_new (limit=$PHASE3_COMBO_LIMIT)"

python - <<'PY' "$RECORDS_TSV" "$SUMMARY_CSV" "$SUMMARY_MD"
import csv
import pandas as pd
import sys
from pathlib import Path

records_tsv = Path(sys.argv[1])
out_csv = Path(sys.argv[2])
out_md = Path(sys.argv[3])

with records_tsv.open() as f:
    rd = csv.DictReader(f, delimiter='\t')
    records = list(rd)

if not records:
    raise SystemExit("no phase3 records")

total_records = len(records)
degenerate_count = sum(1 for r in records if r.get("status") == "degenerate_skip")
effective_combo_count = sum(
    1
    for r in records
    if r.get("status") not in {"degenerate_skip", "cache_variant_fail", "cache_meta_invalid"}
)
effective_ratio = (effective_combo_count / total_records) if total_records else 0.0

baseline_path = Path(records[0]["baseline_csv"])
if not baseline_path.exists():
    raise SystemExit(f"baseline missing: {baseline_path}")

bdf = pd.read_csv(baseline_path)
bdf = bdf[bdf["date"].notna()]
base_recall = float(bdf["l_Recall_c1"].mean())
base_acc = float(bdf["l_clf_corrct"].mean())

rows = []
for r in records:
    result_csv = r.get("result_csv", "").strip()
    if not result_csv:
        continue
    csv_path = Path(result_csv)
    if not csv_path.exists():
        continue
    df = pd.read_csv(csv_path)
    df = df[df["date"].notna()]
    if df.empty:
        continue
    recall = float(df["l_Recall_c1"].mean())
    acc = float(df["l_clf_corrct"].mean())
    rows.append(
        {
            "dim_key": r["dim_key"],
            "q_gate": float(r["q_gate"]),
            "sev_sum_gate": float(r["sev_sum_gate"]),
            "require_rule_match": int(r["require_rule_match"]),
            "status": r.get("status", "ok"),
            "recall": recall,
            "acc": acc,
            "delta_recall_vs_nollm": recall - base_recall,
            "delta_acc_vs_nollm": acc - base_acc,
            "pass_acc_guard": bool(acc >= (base_acc - 1.0)),
            "result_csv": str(csv_path),
        }
    )

if not rows:
    out_df = pd.DataFrame(
        columns=[
            "dim_key",
            "q_gate",
            "sev_sum_gate",
            "require_rule_match",
            "status",
            "recall",
            "acc",
            "delta_recall_vs_nollm",
            "delta_acc_vs_nollm",
            "pass_acc_guard",
            "result_csv",
        ]
    )
    out_df.to_csv(out_csv, index=False)
    out_md.write_text(
        "# pre-ARFF Grid (MC1, v1)\n\n"
        f"total_rows=0\n"
        f"total_records={total_records}\n"
        f"degenerate_count={degenerate_count}\n"
        f"effective_combo_count={effective_combo_count}\n"
        f"effective_ratio={effective_ratio:.4f}\n"
        f"baseline_recall={base_recall:.4f}\n"
        f"baseline_acc={base_acc:.4f}\n\n"
        "No valid result csv produced in this batch (all combos failed or were interrupted).\n",
        encoding="utf-8",
    )
    print(f"wrote {out_csv} rows=0")
    print(f"wrote {out_md}")
    raise SystemExit(0)

out_df = pd.DataFrame(rows)
out_df = out_df.sort_values(
    ["pass_acc_guard", "delta_recall_vs_nollm", "delta_acc_vs_nollm"],
    ascending=[False, False, False],
)
out_df.to_csv(out_csv, index=False)

best = out_df.iloc[0]
lines = [
    "# pre-ARFF Grid (MC1, v1)",
    "",
    f"total_rows={len(out_df)}",
    f"total_records={total_records}",
    f"degenerate_count={degenerate_count}",
    f"effective_combo_count={effective_combo_count}",
    f"effective_ratio={effective_ratio:.4f}",
    f"baseline_recall={base_recall:.4f}",
    f"baseline_acc={base_acc:.4f}",
    "",
    f"- best: dim={best['dim_key']} q={best['q_gate']} sev={best['sev_sum_gate']} rule={int(best['require_rule_match'])}",
    f"- recall={best['recall']:.4f} (delta_vs_nollm={best['delta_recall_vs_nollm']:+.4f})",
    f"- acc={best['acc']:.4f} (delta_vs_nollm={best['delta_acc_vs_nollm']:+.4f})",
    f"- pass_acc_guard={bool(best['pass_acc_guard'])}",
    "",
]
out_md.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out_csv} rows={len(out_df)}")
print(f"wrote {out_md}")
PY

echo "[phase3_mc1] done"
