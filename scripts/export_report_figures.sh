#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HTML_PATH="${1:-$REPO_ROOT/docs/reports/report_figures_frontend_20260409.html}"
OUTPUT_DIR="${2:-$REPO_ROOT/docs/reports/frontend_exports}"
SCALE="${3:-2.0}"

python "$REPO_ROOT/scripts/export_report_figures.py" \
  --html "$HTML_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --scale "$SCALE"
