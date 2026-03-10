#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$ROOT"

DATE_TAG="20140901_20141109"
OUT_CSV="$ROOT/docs/llm_robust_eval_report_v2.csv"
OUT_MD="$ROOT/docs/llm_robust_eval_report_v2.md"

# Default LLM result files (per-model), aligned with framework v1 phase3 best combos.
LLM_HI7="hi7_example/phase3_hi7_compact14_q00_s08_r0_D10_H05000_i10.csv"
LLM_HDS723="hi7_example/phase3_hds723030ala640_full70_q00_s00_r0_D10_H05000_i10.csv"
LLM_HMS5C="hi7_example/phase3_hms5c4040ble640_compact14_q00_s00_r0_D10_H05000_i10.csv"
LLM_ST3000="hi7_example/phase3_st3000dm001_compact9_q55_s08_r1_D10_H05000_i10.csv"
LLM_ST315="hi7_example/phase3_st31500541as_full70_q00_s00_r0_D10_H05000_i10.csv"

# no-LLM baselines (fixed).
NOLLM_HI7="hi7_example/example_hi7_nollm_${DATE_TAG}_compare_aligned_i10.csv"
NOLLM_HDS723="hi7_example/example_hds723030ala640_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"
NOLLM_HMS5C="hi7_example/example_hms5c4040ble640_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"
NOLLM_ST3000="hi7_example/example_st3000dm001_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"
NOLLM_ST315="hi7_example/example_st31500541as_nollm_${DATE_TAG}_compare_map70_aligned_i10.csv"
NOLLM_ST315_CONTRACTFIX="hi7_example/example_st31500541as_nollm_contractfix_${DATE_TAG}_aligned_i10.csv"

if [[ -f "$NOLLM_ST315_CONTRACTFIX" ]]; then
  NOLLM_ST315="$NOLLM_ST315_CONTRACTFIX"
fi

echo "[robust-eval-v2] st3000 llm csv => $LLM_ST3000"

python llm/scripts/eval_llm_vs_nollm_by_model.py \
  --pair "hi7,$LLM_HI7,$NOLLM_HI7" \
  --pair "hds723030ala640,$LLM_HDS723,$NOLLM_HDS723" \
  --pair "hms5c4040ble640,$LLM_HMS5C,$NOLLM_HMS5C" \
  --pair "st3000dm001,$LLM_ST3000,$NOLLM_ST3000" \
  --pair "st31500541as,$LLM_ST315,$NOLLM_ST315" \
  --acc_drop_pp 1.0 \
  --out_csv "$OUT_CSV" \
  --out_md "$OUT_MD"

echo "[robust-eval-v2] wrote:"
echo "  - $OUT_CSV"
echo "  - $OUT_MD"
