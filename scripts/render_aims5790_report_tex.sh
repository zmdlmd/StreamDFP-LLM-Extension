#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_MD="${1:-$REPO_ROOT/docs/reports/aims5790_term1_latex_ready_20260410.md}"
OUTPUT_TEX="${2:-$REPO_ROOT/docs/reports/aims5790_term1_latex_submission_20260410.tex}"

pandoc "$SOURCE_MD" \
  --resource-path="$REPO_ROOT/docs/reports" \
  -s \
  --toc \
  -V documentclass=article \
  -V classoption=a4paper \
  -V fontsize=11pt \
  -V geometry:margin=1in \
  -V linestretch=1.0 \
  -o "$OUTPUT_TEX"

python "$REPO_ROOT/scripts/postprocess_report_tex.py" "$OUTPUT_TEX" >/dev/null

printf '%s\n' "$OUTPUT_TEX"
