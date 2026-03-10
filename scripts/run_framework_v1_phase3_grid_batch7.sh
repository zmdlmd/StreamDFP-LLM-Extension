#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/data_2014/2014/}"
FEATURES="${FEATURES:-$ROOT/pyloader/features_erg/hi7_all.txt}"
FEATURE_CONTRACT_MODE="${FEATURE_CONTRACT_MODE:-auto}"   # auto|off|force
FEATURE_CONTRACT_AUTO_BUILD="${FEATURE_CONTRACT_AUTO_BUILD:-1}"
FEATURE_CONTRACT_DIR="${FEATURE_CONTRACT_DIR:-$ROOT/pyloader/features_erg/contracts}"
FEATURE_CONTRACT_SUMMARY_DIR="${FEATURE_CONTRACT_SUMMARY_DIR:-$ROOT/llm/contracts}"
FEATURE_CONTRACT_MIN_NON_NULL="${FEATURE_CONTRACT_MIN_NON_NULL:-0.99}"
FEATURE_CONTRACT_MIN_FEATURES="${FEATURE_CONTRACT_MIN_FEATURES:-5}"
FEATURE_CONTRACT_FALLBACK_RATIOS="${FEATURE_CONTRACT_FALLBACK_RATIOS:-0.95,0.9,0.8,0.5}"
CONTRACT_TRAIN_START="${CONTRACT_TRAIN_START:-2014-01-01}"
CONTRACT_TRAIN_END="${CONTRACT_TRAIN_END:-2014-08-31}"
CONTRACT_DATE_FORMAT="${CONTRACT_DATE_FORMAT:-%Y-%m-%d}"

START_DATE="${START_DATE:-2014-09-01}"
SIM_START="${SIM_START:-2014-09-30}"
ITER_DAYS="${ITER_DAYS:-10}"
VALID_WINDOW="${VALID_WINDOW:-30}"
SIM_D="${SIM_D:-10}"
SIM_H="${SIM_H:-0.5000}"
JAVA_XMX="${JAVA_XMX:-40g}"
MAX_WINDOWS="${MAX_WINDOWS:-20000}"

KEEP_VARIANT="${KEEP_VARIANT:-0}"
KEEP_ARFF="${KEEP_ARFF:-0}"
PHASE3_EXTRACT_MODE="${PHASE3_EXTRACT_MODE:-zs}"          # fs|zs
PHASE3_PROMPT_PROFILE="${PHASE3_PROMPT_PROFILE:-structured_v2}"  # legacy|structured_v2
PHASE3_MODELS="${PHASE3_MODELS:-all}"                    # all|csv(list)
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-b7zs}"            # output suffix to avoid overwriting
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-pilot20k}"              # pilot20k|full|custom tag used in phase2 artifacts

SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"

declare -A MODEL_NAME
declare -A BASELINE_CSV

MODEL_NAME["hgsthms5c4040ale640"]="HGST HMS5C4040ALE640"
MODEL_NAME["st31500341as"]="ST31500341AS"
MODEL_NAME["hitachihds5c4040ale630"]="Hitachi HDS5C4040ALE630"
MODEL_NAME["wdcwd30efrx"]="WDC WD30EFRX"
MODEL_NAME["wdcwd10eads"]="WDC WD10EADS"
MODEL_NAME["st4000dm000"]="ST4000DM000"
MODEL_NAME["hds5c3030ala630"]="Hitachi HDS5C3030ALA630"

BASELINE_CSV["hgsthms5c4040ale640"]="$ROOT/hi7_example/example_hgsthms5c4040ale640_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["st31500341as"]="$ROOT/hi7_example/example_st31500341as_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["hitachihds5c4040ale630"]="$ROOT/hi7_example/example_hitachihds5c4040ale630_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["wdcwd30efrx"]="$ROOT/hi7_example/example_wdcwd30efrx_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["wdcwd10eads"]="$ROOT/hi7_example/example_wdcwd10eads_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["st4000dm000"]="$ROOT/hi7_example/example_st4000dm000_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["hds5c3030ala630"]="$ROOT/hi7_example/example_hds5c3030ala630_nollm_20140901_20141109_compare_aligned_i10.csv"

ALL_MODELS=(
  "hgsthms5c4040ale640"
  "st31500341as"
  "hitachihds5c4040ale630"
  "wdcwd30efrx"
  "wdcwd10eads"
  "st4000dm000"
  "hds5c3030ala630"
)

resolve_phase3_models() {
  local selector="$PHASE3_MODELS"
  local -a picked=()
  local key
  case "$selector" in
    all)
      picked=("${ALL_MODELS[@]}")
      ;;
    *)
      IFS=',' read -r -a picked <<< "$selector"
      ;;
  esac
  if [[ ${#picked[@]} -eq 0 ]]; then
    echo "[phase3-batch7] no models resolved from PHASE3_MODELS=$selector" >&2
    exit 2
  fi
  for key in "${picked[@]}"; do
    if [[ -z "${MODEL_NAME[$key]:-}" ]]; then
      echo "[phase3-batch7] unknown model key: $key" >&2
      exit 2
    fi
  done
  printf "%s\n" "${picked[@]}"
}

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3_batch7}"
VARIANT_DIR="$ROOT/llm/framework_v1/phase3_variants_batch7"
WINDOW_PILOT_DIR="$ROOT/llm/framework_v1"
mkdir -p "$STATE_DIR" "$VARIANT_DIR" "$ROOT/docs" "$FEATURE_CONTRACT_DIR" "$FEATURE_CONTRACT_SUMMARY_DIR"

if [[ -z "${RECORDS_TSV:-}" ]]; then
  RECORDS_TSV="$STATE_DIR/phase3_batch7_combo_records_${PHASE3_RUN_TAG}.tsv"
fi
if [[ -z "${SUMMARY_CSV:-}" ]]; then
  if [[ "$PHASE3_RUN_TAG" == "pilot20k" ]]; then
    SUMMARY_CSV="$ROOT/docs/prearff_grid_batch7_zs_v1.csv"
  else
    SUMMARY_CSV="$ROOT/docs/prearff_grid_batch7_zs_${PHASE3_RUN_TAG}_v1.csv"
  fi
fi
if [[ -z "${SUMMARY_MD:-}" ]]; then
  if [[ "$PHASE3_RUN_TAG" == "pilot20k" ]]; then
    SUMMARY_MD="$ROOT/docs/prearff_grid_batch7_zs_v1.md"
  else
    SUMMARY_MD="$ROOT/docs/prearff_grid_batch7_zs_${PHASE3_RUN_TAG}_v1.md"
  fi
fi
: > "$RECORDS_TSV"
printf "model_key\tdim_key\tq_gate\tsev_sum_gate\trequire_rule_match\tvariant_cache\tresult_csv\tbaseline_csv\n" >> "$RECORDS_TSV"

normalize_model_key() {
  local raw="${1:-}"
  echo "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+//g'
}

resolve_features_for_model() {
  local model="$1"
  local model_name="${MODEL_NAME[$model]}"
  local model_key
  local contract_path
  local summary_path

  if [[ "$FEATURE_CONTRACT_MODE" == "off" ]]; then
    echo "$FEATURES"
    return
  fi

  model_key="$(normalize_model_key "$model_name")"
  contract_path="$FEATURE_CONTRACT_DIR/${model_key}.txt"
  summary_path="$FEATURE_CONTRACT_SUMMARY_DIR/feature_contract_${model_key}_${CONTRACT_TRAIN_START//-/}_${CONTRACT_TRAIN_END//-/}.json"

  if [[ "$FEATURE_CONTRACT_MODE" == "force" || ! -s "$contract_path" ]]; then
    if [[ "$FEATURE_CONTRACT_AUTO_BUILD" == "1" ]]; then
      echo "[phase3-batch7] building feature contract for $model ($model_name)"
      python "$ROOT/llm/scripts/build_feature_contracts.py" \
        --data_root "$DATA_ROOT" \
        --features_path "$FEATURES" \
        --date_format "$CONTRACT_DATE_FORMAT" \
        --train_start_date "$CONTRACT_TRAIN_START" \
        --train_end_date "$CONTRACT_TRAIN_END" \
        --disk_models "$model_name" \
        --out_dir "$FEATURE_CONTRACT_DIR" \
        --summary_out "$summary_path" \
        --min_non_null_ratio "$FEATURE_CONTRACT_MIN_NON_NULL" \
        --fallback_non_null_ratios "$FEATURE_CONTRACT_FALLBACK_RATIOS" \
        --min_features "$FEATURE_CONTRACT_MIN_FEATURES" \
        --overwrite
    fi
  fi

  if [[ -s "$contract_path" ]]; then
    echo "$contract_path"
  else
    echo "[phase3-batch7] WARN contract missing for $model, fallback to $FEATURES" >&2
    echo "$FEATURES"
  fi
}

ensure_window_input() {
  local model="$1"
  local preferred="$WINDOW_PILOT_DIR/window_text_${model}_${PHASE3_RUN_TAG}.jsonl"
  local pilot="$WINDOW_PILOT_DIR/window_text_${model}_pilot20k.jsonl"
  local pilot_numeric="$WINDOW_PILOT_DIR/window_text_${model}_pilot${MAX_WINDOWS}.jsonl"
  local src="$ROOT/llm/window_text_${model}_20140901_20141109.jsonl"
  if [[ -f "$preferred" ]]; then
    echo "$preferred"
    return 0
  fi
  if [[ "$PHASE3_RUN_TAG" == pilot20k* ]]; then
    if [[ -f "$pilot" ]]; then
      local cur
      cur=$(wc -l < "$pilot" || echo 0)
      if [[ "$cur" -ge "$MAX_WINDOWS" ]]; then
        echo "$pilot"
        return 0
      fi
    fi
    if [[ -f "$pilot_numeric" ]]; then
      local cur
      cur=$(wc -l < "$pilot_numeric" || echo 0)
      if [[ "$cur" -ge "$MAX_WINDOWS" ]]; then
        echo "$pilot_numeric"
        return 0
      fi
    fi
    if [[ ! -f "$src" ]]; then
      echo "[phase3-batch7] missing window_text source: $src" >&2
      return 1
    fi
    head -n "$MAX_WINDOWS" "$src" > "$pilot_numeric"
    echo "$pilot_numeric"
    return 0
  fi
  if [[ -f "$src" ]]; then
    echo "$src"
    return 0
  fi
  echo "[phase3-batch7] missing window_text source: $src" >&2
  return 1
}

mapfile -t MODELS < <(resolve_phase3_models)
echo "[phase3-batch7] models=${MODELS[*]} extract=${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE} run_tag=${PHASE3_RUN_TAG}"

for model in "${MODELS[@]}"; do
  disk_model="${MODEL_NAME[$model]}"
  features_path="$(resolve_features_for_model "$model")"
  window_text="$(ensure_window_input "$model")"
  cache_in="$ROOT/llm/framework_v1/cache_${model}_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${PHASE3_RUN_TAG}.jsonl"
  baseline_csv="${BASELINE_CSV[$model]}"

  if [[ ! -f "$cache_in" ]]; then
    echo "[phase3-batch7] missing cache: $cache_in" >&2
    exit 2
  fi
  if [[ ! -f "$baseline_csv" ]]; then
    echo "[phase3-batch7] missing baseline: $baseline_csv" >&2
    exit 2
  fi

  echo "[phase3-batch7][$model] features_path=$features_path window_text=$window_text"
  model_variant_dir="$VARIANT_DIR/$model"
  mkdir -p "$model_variant_dir"

  for dim_spec in "compact9:event_top3_plus_meta:9:1" "compact14:event_top8_plus_meta:14:1" "full70:all:70:0"; do
    IFS=':' read -r dim_key keep_profile llm_dim compact_front <<< "$dim_spec"

    for qspec in "0.0:00" "0.35:35" "0.55:55"; do
      IFS=':' read -r q_gate q_tag <<< "$qspec"
      for sspec in "0.0:00" "0.8:08"; do
        IFS=':' read -r sev_gate sev_tag <<< "$sspec"
        for req in 0 1; do
          tag="${model}_${dim_key}_q${q_tag}_s${sev_tag}_r${req}_${PHASE3_TAG_SUFFIX}"
          variant_cache="$model_variant_dir/${tag}.jsonl"
          train_dir="$ROOT/pyloader/phase3b7_train_${tag}"
          test_dir="$ROOT/pyloader/phase3b7_test_${tag}"
          out_txt="$ROOT/hi7_example/phase3b7_${tag}_D10_H05000_i10.txt"
          out_time="$ROOT/hi7_example/time_phase3b7_${tag}_D10_H05000_i10.txt"
          out_csv="$ROOT/hi7_example/phase3b7_${tag}_D10_H05000_i10.csv"

          if [[ -s "$out_csv" ]]; then
            echo "[phase3-batch7] skip existing csv $tag"
            printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "$variant_cache" "$out_csv" "$baseline_csv" >> "$RECORDS_TSV"
            continue
          fi

          echo "[phase3-batch7] build_cache_variant $tag"
          cmd=(python "$ROOT/llm/scripts/build_cache_variant.py"
            --in_cache "$cache_in"
            --out_cache "$variant_cache"
            --q_gate "$q_gate"
            --sev_sum_gate "$sev_gate"
            --keep_profile "$keep_profile"
            --root_cause_field root_cause_pred
            --window_text_path "$window_text"
          )
          if [[ "$req" == "1" ]]; then
            cmd+=(--require_rule_match)
          fi
          if [[ "$compact_front" == "1" ]]; then
            cmd+=(--compact_front)
          fi
          "${cmd[@]}" > "$STATE_DIR/${tag}_cache_variant.json"

          rm -rf "$train_dir" "$test_dir"
          mkdir -p "$train_dir" "$test_dir"

          echo "[phase3-batch7] run.py $tag"
          python "$ROOT/pyloader/run.py" \
            -s "$START_DATE" \
            -p "$DATA_ROOT" \
            -d "$disk_model" \
            -i "$ITER_DAYS" \
            -c "$features_path" \
            -r "${train_dir}/" \
            -e "${test_dir}/" \
            -o 4 \
            -t sliding \
            -w 30 \
            -V "$VALID_WINDOW" \
            -L 7 \
            -a 20 \
            -U 1 \
            -C "$variant_cache" \
            -M "$llm_dim"

          echo "[phase3-batch7] simulate $tag"
          stdbuf -i0 -o0 -e0 java -Xmx"$JAVA_XMX" \
            -cp "$SIM_CP" simulate.Simulate \
            -s "$SIM_START" \
            -i "$ITER_DAYS" \
            -p "${train_dir}/" \
            -t "${test_dir}/" \
            -a "(meta.AdaptiveRandomForest -a 20 -s 30 -l (ARFHoeffdingTree -g 50 -c 1e-7) -j -1 -x (ADWINChangeDetector -a 1e-5) -p (ADWINChangeDetector -a 1e-4))" \
            -D "$SIM_D" \
            -V "$VALID_WINDOW" \
            -H "$SIM_H" \
            -r 1 > "$out_txt" 2> "$out_time"

          python "$ROOT/parse.py" "$out_txt" >/dev/null
          printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "$variant_cache" "$out_csv" "$baseline_csv" >> "$RECORDS_TSV"

          if [[ "$KEEP_ARFF" != "1" ]]; then
            rm -rf "$train_dir" "$test_dir"
          fi
          if [[ "$KEEP_VARIANT" != "1" ]]; then
            rm -f "$variant_cache"
          fi
        done
      done
    done
  done
done

python - <<'PY' "$RECORDS_TSV" "$SUMMARY_CSV" "$SUMMARY_MD"
import csv
from pathlib import Path
import pandas as pd
import sys

records_tsv = Path(sys.argv[1])
out_csv = Path(sys.argv[2])
out_md = Path(sys.argv[3])
base_stats = {}
rows = []

with records_tsv.open() as f:
    rd = csv.DictReader(f, delimiter='\t')
    for r in rd:
        model = r['model_key']
        baseline_path = Path(r['baseline_csv'])
        csv_path = Path(r['result_csv'])
        if not baseline_path.exists() or not csv_path.exists():
            continue
        if model not in base_stats:
            bdf = pd.read_csv(baseline_path)
            bdf = bdf[bdf['date'].notna()]
            if bdf.empty:
                continue
            base_stats[model] = {
                'base_recall': float(bdf['l_Recall_c1'].mean()),
                'base_acc': float(bdf['l_clf_corrct'].mean()),
            }
        df = pd.read_csv(csv_path)
        df = df[df['date'].notna()]
        if df.empty:
            continue
        rec = float(df['l_Recall_c1'].mean())
        acc = float(df['l_clf_corrct'].mean())
        base = base_stats[model]
        rows.append({
            'model_key': model,
            'dim_key': r['dim_key'],
            'q_gate': float(r['q_gate']),
            'sev_sum_gate': float(r['sev_sum_gate']),
            'require_rule_match': int(r['require_rule_match']),
            'recall': rec,
            'acc': acc,
            'delta_recall_vs_nollm': rec - base['base_recall'],
            'delta_acc_vs_nollm': acc - base['base_acc'],
            'pass_acc_guard': bool(acc >= (base['base_acc'] - 1.0)),
            'result_csv': str(csv_path),
        })

if not rows:
    raise SystemExit('no rows to write')

out_df = pd.DataFrame(rows)
out_df = out_df.sort_values(
    ['model_key', 'pass_acc_guard', 'delta_recall_vs_nollm', 'delta_acc_vs_nollm'],
    ascending=[True, False, False, False],
)
out_df.to_csv(out_csv, index=False)

lines = [f'# pre-ARFF Grid batch7 ({out_df["model_key"].nunique()} models, zs)', '', f'total_rows={len(out_df)}', '']
for model in sorted(out_df['model_key'].unique()):
    md = out_df[out_df['model_key'] == model]
    best = md.iloc[0]
    lines.append(f'## {model}')
    lines.append(f"- best: dim={best['dim_key']} q={best['q_gate']} sev={best['sev_sum_gate']} rule={int(best['require_rule_match'])}")
    lines.append(f"- recall={best['recall']:.4f} (delta_vs_nollm={best['delta_recall_vs_nollm']:+.4f})")
    lines.append(f"- acc={best['acc']:.4f} (delta_vs_nollm={best['delta_acc_vs_nollm']:+.4f})")
    lines.append(f"- pass_acc_guard={bool(best['pass_acc_guard'])}")
    lines.append('')

out_md.write_text('\n'.join(lines), encoding='utf-8')
print(f'wrote {out_csv} rows={len(out_df)}')
print(f'wrote {out_md}')
PY

echo "[phase3-batch7] done"
