#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_MD="${1:-$REPO_ROOT/docs/reports/aims5790_term1_pandoc_ready_20260409.md}"
REFERENCE_DOC="${2:-$REPO_ROOT/docs/reports/aims5790_pandoc_reference_template_20260409.docx}"
OUTPUT_DOCX="${3:-$REPO_ROOT/docs/reports/aims5790_term1_styled_20260409.docx}"

if [[ ! -f "$REFERENCE_DOC" ]]; then
  python "$REPO_ROOT/scripts/make_pandoc_reference_doc.py" "$REFERENCE_DOC"
fi

pandoc "$SOURCE_MD" \
  --resource-path="$REPO_ROOT/docs/reports" \
  --reference-doc="$REFERENCE_DOC" \
  -o "$OUTPUT_DOCX"

python "$REPO_ROOT/scripts/postprocess_report_docx.py" "$OUTPUT_DOCX" >/dev/null

printf '%s\n' "$OUTPUT_DOCX"
