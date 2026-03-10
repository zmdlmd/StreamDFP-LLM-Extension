#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

MODE="${1:-preview}" # preview|paths|status

ROOT_FILES=(
  "README.md"
  ".gitignore"
  "LICENSE"
  "environment-public.yml"
  "requirements-public.txt"
  "requirements-llm-public.txt"
  "pom.xml"
  "parse.py"
  "parse_reg.py"
  "run_hi7.sh"
  "run_hi7_reg.sh"
  "run_hi640_transfer.sh"
  "run_hi7_rnn.sh"
  "run_mc1_mlp.sh"
  "run_llm_feature_flow_qwen3_4b_2507.sh"
  "run_llm_feature_flow_mc1_qwen3_4b_2507.sh"
)

CONFIG_FILES=(
  "configs/public_repro.env.example"
)

DOC_FILES=(
  "docs/README.md"
  "docs/REPOSITORY_LAYOUT.md"
  "docs/GITHUB_UPLOAD_CHECKLIST.md"
  "docs/PUBLIC_REPRODUCIBILITY.md"
  "docs/PUBLIC_FIRST_RELEASE_SCOPE.md"
  "docs/cross_model_llm_framework_v1_final.md"
  "docs/cross_model_execution_checklist_v1_final.md"
  "docs/framework_v1_metric_contract.md"
  "docs/llm_integration.md"
  "docs/llm_recent_experiments_master_summary_20260305.md"
  "docs/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md"
  "docs/qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md"
  "docs/summary_schema_structured_v2.md"
  "docs/summary_schema_structured_v2_samples.md"
)

CODE_DIRS=(
  "simulate/src"
  "moa/src"
  "llm/tests"
  "llm/scripts"
  "llm/event_mappings"
  "llm/rules"
)

CODE_FILES=(
  "simulate/pom.xml"
  "moa/pom.xml"
  "pyloader/run.py"
  "pyloader/run_mc1_loader.sh"
  "llm/__init__.py"
  "llm/window_to_text.py"
  "llm/llm_offline_extract.py"
  "llm/feature_mapping.py"
  "llm/eval_alignment.py"
  "llm/event_mapping_hi7.yaml"
  "llm/event_mapping_mc1.yaml"
  "llm/calibration/model_policy.yaml"
  "llm/requirements_vllm.txt"
  "pyloader/run_hi7_loader.sh"
  "pyloader/run_hi7_reg_loader.sh"
  "scripts/run_cross_model_llm_framework_v1.sh"
  "scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh"
  "scripts/run_phase3_all_pilot20k_qwen35.sh"
  "scripts/run_framework_v1_phase3_grid.sh"
  "scripts/run_framework_v1_phase3_grid_batch7.sh"
  "scripts/run_framework_v1_phase2_mc1.sh"
  "scripts/run_framework_v1_phase3_grid_mc1.sh"
  "scripts/run_batch7_phase2_zs.sh"
  "scripts/run_batch7_phase2_zs_continue.sh"
  "scripts/run_batch7_phase2_zs_reliable.sh"
  "scripts/run_batch7_phase2_zs_resume.sh"
  "scripts/monitor_phase2_all12_qwen35.sh"
  "scripts/watch_phase2_single_then_phase3.sh"
  "scripts/watch_phase3_all_qwen35_then_shutdown.sh"
  "scripts/watch_mc1_compact14_until_done_shutdown.sh"
  "scripts/watch_mc1_phase3_full70_listener.sh"
  "scripts/run_mc1_phase3_full70_rounds.sh"
  "scripts/auto_resume_hms_robustv6.sh"
  "scripts/auto_resume_phase3_batch7_zs.sh"
  "scripts/auto_resume_phase3_fs.sh"
  "scripts/auto_shutdown_after_hms_robustv5.sh"
  "scripts/hms_robustv6_follow_and_eval.sh"
  "scripts/hms_round10_seed_check.sh"
  "scripts/hms_round10_trainside_grid.sh"
  "scripts/hms_round11_trainside_utilization_zs.sh"
  "scripts/run_batch5_cpu_phase0_phase1.sh"
  "scripts/run_hms_rerun_v7_zs.sh"
  "scripts/controller_hooks/microgrid_hms5c4040ble640.sh"
  "scripts/controller_hooks/policy_grid_hms5c4040ble640.sh"
  "scripts/controller_hooks/rerun_extract_hms5c4040ble640.sh"
  "run_robust_eval_report_v2.sh"
  "run_stage2_7models_fs_20140901_20141109.sh"
  "run_stage2_remaining5_fs_zs_then_shutdown.sh"
  "run_stage2_remaining5_resume_safe_then_shutdown.sh"
  "run_stage3_5_for_completed_map70_models.sh"
  "run_cross_model_llm_recall_controller.sh"
  "stop_after_model_fs_zs.sh"
)

REPRESENTATIVE_IGNORED=(
  "data"
  "logs"
  "share_demo"
  "hi7_example"
  "llm/framework_v1/cache_st31500541as_zs_structured_v2_pilot20k_qwen35.jsonl"
  "llm/window_text_smoke64.jsonl"
  "llm/reference_examples_hi7_trainonly.json"
  "pyloader/hi7_train_st31500541as_nollm_contractfix_20140901_20141109"
)

ALL_PATHS=(
  "${ROOT_FILES[@]}"
  "${CONFIG_FILES[@]}"
  "${DOC_FILES[@]}"
  "${CODE_DIRS[@]}"
  "${CODE_FILES[@]}"
)

print_paths() {
  local p
  for p in "${ALL_PATHS[@]}"; do
    printf "%s\n" "$p"
  done
}

check_missing() {
  local missing=0
  local p
  for p in "${ALL_PATHS[@]}"; do
    if [[ ! -e "$p" ]]; then
      echo "[missing] $p"
      missing=1
    fi
  done
  return "$missing"
}

print_add_command() {
  echo "git add \\"
  local i
  for ((i = 0; i < ${#ALL_PATHS[@]}; i++)); do
    local suffix=" \\"
    if (( i == ${#ALL_PATHS[@]} - 1 )); then
      suffix=""
    fi
    printf "  %s%s\n" "${ALL_PATHS[$i]}" "$suffix"
  done
}

print_ignore_preview() {
  local p
  echo
  echo "Ignored artifact check:"
  for p in "${REPRESENTATIVE_IGNORED[@]}"; do
    if git check-ignore -q "$p"; then
      echo "  [ignored] $p"
    else
      echo "  [NOT_IGNORED] $p"
    fi
  done
}

case "$MODE" in
  paths)
    print_paths
    ;;
  status)
    check_missing || true
    echo
    git status --short -- "${ALL_PATHS[@]}"
    print_ignore_preview
    ;;
  preview)
    echo "Public first-release path count: ${#ALL_PATHS[@]}"
    echo
    check_missing || true
    echo
    echo "Suggested git add command:"
    print_add_command
    echo
    echo "Current git status for suggested paths:"
    git status --short -- "${ALL_PATHS[@]}"
    print_ignore_preview
    ;;
  *)
    echo "Usage: $0 [preview|paths|status]" >&2
    exit 2
    ;;
esac
