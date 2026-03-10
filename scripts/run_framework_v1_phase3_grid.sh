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
PHASE3_MODELS="${PHASE3_MODELS:-m1}" # m1|m2|all|csv(list)
PHASE3_TAG_SUFFIX="${PHASE3_TAG_SUFFIX:-}"  # optional output suffix to avoid fs/zs overwrite
PHASE3_RUN_TAG="${PHASE3_RUN_TAG:-pilot20k}" # pilot20k|full|custom tag used in phase2 artifacts

SIM_CP="simulate/target/simulate-2019.01.0-SNAPSHOT.jar:moa/target/moa-2019.01.0-SNAPSHOT.jar"

declare -A MODEL_NAME
declare -A BASELINE_CSV
MODEL_NAME["hi7"]="Hitachi HDS722020ALA330"
MODEL_NAME["hds723030ala640"]="Hitachi HDS723030ALA640"
MODEL_NAME["st3000dm001"]="ST3000DM001"
MODEL_NAME["hms5c4040ble640"]="HGST HMS5C4040BLE640"
MODEL_NAME["st31500541as"]="ST31500541AS"

BASELINE_CSV["hi7"]="$ROOT/hi7_example/example_hi7_nollm_20140901_20141109_compare_aligned_i10.csv"
BASELINE_CSV["hds723030ala640"]="$ROOT/hi7_example/example_hds723030ala640_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
BASELINE_CSV["st3000dm001"]="$ROOT/hi7_example/example_st3000dm001_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
BASELINE_CSV["hms5c4040ble640"]="$ROOT/hi7_example/example_hms5c4040ble640_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
BASELINE_ST315="${BASELINE_ST315:-$ROOT/hi7_example/example_st31500541as_nollm_contractfix_20140901_20141109_aligned_i10.csv}"
if [[ ! -f "$BASELINE_ST315" ]]; then
  BASELINE_ST315="$ROOT/hi7_example/example_st31500541as_nollm_20140901_20141109_compare_map70_aligned_i10.csv"
fi
BASELINE_CSV["st31500541as"]="$BASELINE_ST315"

M1_MODELS=("st3000dm001" "hms5c4040ble640")
M2_MODELS=("hi7" "hds723030ala640" "st31500541as")

resolve_phase3_models() {
  local selector="$PHASE3_MODELS"
  local -a picked=()
  case "$selector" in
    m1)
      picked=("${M1_MODELS[@]}")
      ;;
    m2)
      picked=("${M2_MODELS[@]}")
      ;;
    all)
      picked=("hi7" "hds723030ala640" "st3000dm001" "hms5c4040ble640" "st31500541as")
      ;;
    *)
      IFS=',' read -r -a picked <<< "$selector"
      ;;
  esac
  if [[ ${#picked[@]} -eq 0 ]]; then
    echo "[phase3] no models resolved from PHASE3_MODELS=$selector" >&2
    exit 2
  fi
  local key
  for key in "${picked[@]}"; do
    if [[ -z "${MODEL_NAME[$key]:-}" ]]; then
      echo "[phase3] unknown model key: $key" >&2
      exit 2
    fi
  done
  printf "%s\n" "${picked[@]}"
}

STATE_DIR="${STATE_DIR:-$ROOT/logs/framework_v1_phase3}"
VARIANT_DIR="$ROOT/llm/framework_v1/phase3_variants"
WINDOW_PILOT_DIR="$ROOT/llm/framework_v1"
mkdir -p "$STATE_DIR" "$VARIANT_DIR" "$WINDOW_PILOT_DIR" "$ROOT/docs" "$FEATURE_CONTRACT_DIR" "$FEATURE_CONTRACT_SUMMARY_DIR"

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
      echo "[phase3] building feature contract for $model ($model_name)"
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
    echo "[phase3] WARN contract missing for $model, fallback to $FEATURES" >&2
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
      echo "[phase3] missing window_text source: $src" >&2
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

  echo "[phase3] missing window_text source: $src" >&2
  return 1
}

if [[ -z "${RECORDS_TSV:-}" ]]; then
  RECORDS_TSV="$STATE_DIR/phase3_combo_records_${PHASE3_RUN_TAG}.tsv"
fi
if [[ -z "${SUMMARY_CSV:-}" ]]; then
  if [[ "$PHASE3_RUN_TAG" == "pilot20k" ]]; then
    SUMMARY_CSV="$ROOT/docs/prearff_grid_2models_v1.csv"
  else
    SUMMARY_CSV="$ROOT/docs/prearff_grid_2models_${PHASE3_RUN_TAG}_v1.csv"
  fi
fi
if [[ -z "${SUMMARY_MD:-}" ]]; then
  if [[ "$PHASE3_RUN_TAG" == "pilot20k" ]]; then
    SUMMARY_MD="$ROOT/docs/prearff_grid_2models_v1.md"
  else
    SUMMARY_MD="$ROOT/docs/prearff_grid_2models_${PHASE3_RUN_TAG}_v1.md"
  fi
fi
: > "$RECORDS_TSV"
printf "model_key\tdim_key\tq_gate\tsev_sum_gate\trequire_rule_match\tstatus\tvariant_cache\tcache_variant_meta\tresult_csv\tbaseline_csv\n" >> "$RECORDS_TSV"

mapfile -t models < <(resolve_phase3_models)
echo "[phase3] models=${models[*]} extract=${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE} run_tag=${PHASE3_RUN_TAG}"

for model in "${models[@]}"; do
  disk_model="${MODEL_NAME[$model]}"
  features_path="$(resolve_features_for_model "$model")"
  window_text="$(ensure_window_input "$model")"
  echo "[phase3][$model] features_path=$features_path"
  cache_in="$ROOT/llm/framework_v1/cache_${model}_${PHASE3_EXTRACT_MODE}_${PHASE3_PROMPT_PROFILE}_${PHASE3_RUN_TAG}.jsonl"
  baseline_csv="${BASELINE_CSV[$model]}"

  if [[ ! -f "$cache_in" ]]; then
    echo "[phase3] missing cache: $cache_in" >&2
    exit 2
  fi
  if [[ ! -f "$window_text" ]]; then
    echo "[phase3] missing window_text: $window_text" >&2
    exit 2
  fi
  if [[ ! -f "$baseline_csv" ]]; then
    echo "[phase3] missing baseline: $baseline_csv" >&2
    exit 2
  fi

  model_variant_dir="$VARIANT_DIR/$model"
  mkdir -p "$model_variant_dir"

  for dim_spec in "compact9:event_top3_plus_meta:9:1" "compact14:event_top8_plus_meta:14:1" "full70:all:70:0"; do
    IFS=':' read -r dim_key keep_profile llm_dim compact_front <<< "$dim_spec"

    for qspec in "0.0:00" "0.35:35" "0.55:55"; do
      IFS=':' read -r q_gate q_tag <<< "$qspec"
      for sspec in "0.0:00" "0.8:08"; do
        IFS=':' read -r sev_gate sev_tag <<< "$sspec"
        for req in 0 1; do
          tag="${model}_${dim_key}_q${q_tag}_s${sev_tag}_r${req}"
          if [[ -n "$PHASE3_TAG_SUFFIX" ]]; then
            tag="${tag}_${PHASE3_TAG_SUFFIX}"
          fi
          variant_cache="$model_variant_dir/${tag}.jsonl"
          train_dir="$ROOT/pyloader/phase3_train_${tag}"
          test_dir="$ROOT/pyloader/phase3_test_${tag}"
          out_txt="$ROOT/hi7_example/phase3_${tag}_D10_H05000_i10.txt"
          out_time="$ROOT/hi7_example/time_phase3_${tag}_D10_H05000_i10.txt"
          out_csv="$ROOT/hi7_example/phase3_${tag}_D10_H05000_i10.csv"

          if [[ -s "$out_csv" ]]; then
            echo "[phase3] skip existing csv $tag"
            printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "existing" "$variant_cache" "" "$out_csv" "$baseline_csv" >> "$RECORDS_TSV"
            continue
          fi

          echo "[phase3] build_cache_variant $tag"
          cache_variant_meta="$STATE_DIR/${tag}_cache_variant.json"
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
          "${cmd[@]}" > "$cache_variant_meta"

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
            echo "[phase3] degenerate_skip $tag (kept=0)"
            printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "degenerate_skip" "$variant_cache" "$cache_variant_meta" "" "$baseline_csv" >> "$RECORDS_TSV"
            if [[ "$KEEP_VARIANT" != "1" ]]; then
              rm -f "$variant_cache"
            fi
            continue
          fi
          if [[ "$kept_count" == "-1" ]]; then
            echo "[phase3] WARN cache variant meta parse failed: $cache_variant_meta" >&2
            printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "cache_meta_invalid" "$variant_cache" "$cache_variant_meta" "" "$baseline_csv" >> "$RECORDS_TSV"
            if [[ "$KEEP_VARIANT" != "1" ]]; then
              rm -f "$variant_cache"
            fi
            continue
          fi

          rm -rf "$train_dir" "$test_dir"
          mkdir -p "$train_dir" "$test_dir"

          echo "[phase3] run.py $tag"
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

          echo "[phase3] simulate $tag"
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
          printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$model" "$dim_key" "$q_gate" "$sev_gate" "$req" "ok" "$variant_cache" "$cache_variant_meta" "$out_csv" "$baseline_csv" >> "$RECORDS_TSV"

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
import sys
from pathlib import Path
import pandas as pd

records_tsv = Path(sys.argv[1])
out_csv = Path(sys.argv[2])
out_md = Path(sys.argv[3])
base_stats = {}
records = []

rows = []
with records_tsv.open() as f:
    rd = csv.DictReader(f, delimiter='\t')
    for r in rd:
        records.append(r)
        model = r['model_key']
        baseline_path = Path(r['baseline_csv'])
        result_csv = (r.get('result_csv') or '').strip()
        if not result_csv:
            continue
        csv_path = Path(result_csv)
        if not baseline_path.exists():
            continue
        if not csv_path.exists():
            continue
        if model not in base_stats:
            bdf = pd.read_csv(baseline_path)
            bdf = bdf[bdf['date'].notna()]
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
            'status': r.get('status', 'ok'),
            'recall': rec,
            'acc': acc,
            'delta_recall_vs_nollm': rec - base['base_recall'],
            'delta_acc_vs_nollm': acc - base['base_acc'],
            'pass_acc_guard': bool(acc >= (base['base_acc'] - 1.0)),
            'cache_variant_meta': r.get('cache_variant_meta', ''),
            'result_csv': str(csv_path),
        })

total_records = len(records)
degenerate_count = sum(1 for r in records if r.get('status') == 'degenerate_skip')
effective_combo_count = sum(
    1
    for r in records
    if r.get('status') not in {'degenerate_skip', 'cache_variant_fail', 'cache_meta_invalid'}
)
effective_ratio = (effective_combo_count / total_records) if total_records else 0.0

if not rows:
    out_df = pd.DataFrame(
        columns=[
            'model_key',
            'dim_key',
            'q_gate',
            'sev_sum_gate',
            'require_rule_match',
            'status',
            'recall',
            'acc',
            'delta_recall_vs_nollm',
            'delta_acc_vs_nollm',
            'pass_acc_guard',
            'cache_variant_meta',
            'result_csv',
        ]
    )
    out_df.to_csv(out_csv, index=False)
    lines = [
        '# pre-ARFF Grid (v1)',
        '',
        f'total_rows=0',
        f'total_records={total_records}',
        f'degenerate_count={degenerate_count}',
        f'effective_combo_count={effective_combo_count}',
        f'effective_ratio={effective_ratio:.4f}',
        '',
        'No valid result csv rows produced in this run.',
    ]
    out_md.write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {out_csv} rows=0')
    print(f'wrote {out_md}')
    raise SystemExit(0)

out_df = pd.DataFrame(rows)
out_df = out_df.sort_values(['model_key', 'pass_acc_guard', 'delta_recall_vs_nollm', 'delta_acc_vs_nollm'], ascending=[True, False, False, False])
out_df.to_csv(out_csv, index=False)

num_models = int(out_df["model_key"].nunique())
lines = [
    f'# pre-ARFF Grid ({num_models} models, v1)',
    '',
    f'total_rows={len(out_df)}',
    f'total_records={total_records}',
    f'degenerate_count={degenerate_count}',
    f'effective_combo_count={effective_combo_count}',
    f'effective_ratio={effective_ratio:.4f}',
    '',
]
for model in sorted(out_df['model_key'].unique()):
    md = out_df[out_df['model_key'] == model].copy()
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

echo "[phase3] done"
