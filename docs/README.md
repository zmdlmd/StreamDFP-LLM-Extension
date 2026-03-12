# Docs Index

This directory holds the public-facing experiment narrative, policy summaries, result tables, and a small amount of retained diagnosis material.

## Start Here

- [../README.md](../README.md): repository overview and main entry points
- [guides/README.md](guides/README.md): reproducibility, UI usage, repository layout, and workflow guides
- [reports/README.md](reports/README.md): retained public summaries, policy notes, and merged reports
- [diagnostics/README.md](diagnostics/README.md): kept model-specific diagnosis records
- [tables/README.md](tables/README.md): generated result tables still kept at `docs/` root for script compatibility

## Key Documents

- [guides/PUBLIC_REPRODUCIBILITY.md](guides/PUBLIC_REPRODUCIBILITY.md): environment setup and end-to-end reproduction steps
- [guides/REPOSITORY_LAYOUT.md](guides/REPOSITORY_LAYOUT.md): what each top-level directory is for
- [guides/WORKBENCH_UI.md](guides/WORKBENCH_UI.md): local Web UI entrypoint, workflow registry model, and naming strategy
- [guides/WORKFLOW_ALIASES.md](guides/WORKFLOW_ALIASES.md): normalized `workflows/` CLI aliases and the naming convention they follow
- [reports/cross_model_llm_framework_v1_final.md](reports/cross_model_llm_framework_v1_final.md): main write-up for the LLM-enhanced `framework_v1`
- [guides/cross_model_execution_checklist_v1_final.md](guides/cross_model_execution_checklist_v1_final.md): execution checklist for the cross-model pipeline
- [reports/cross_model_policy_registry_v1_all12.md](reports/cross_model_policy_registry_v1_all12.md): merged model-level policy table covering 12 HDD models plus MC1 pilot
- [reports/cross_model_llm_framework_v1_batch7_zs_final.md](reports/cross_model_llm_framework_v1_batch7_zs_final.md): final write-up for the batch7 ZS expansion

## Summaries

- [reports/llm_recent_experiments_master_summary_20260305.md](reports/llm_recent_experiments_master_summary_20260305.md): baseline lock and merged model-level conclusions before the Qwen3.5 refresh
- [reports/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md](reports/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md): Qwen3.5-4B `pilot20k` results across 12 HDD models
- [reports/qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md](reports/qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md): side-by-side comparison between `Qwen3-4B-Instruct-2507` and `Qwen3.5-4B`
- [reports/llm_robust_eval_report_v4_merged_all12.md](reports/llm_robust_eval_report_v4_merged_all12.md): merged policy guard table across all 12 HDD models plus MC1 pilot

## Model-Specific Diagnosis

- [diagnostics/st31500541as_ab_same_subset_20260310.md](diagnostics/st31500541as_ab_same_subset_20260310.md): same-subset A/B comparison for `st31500541as`
- [diagnostics/st31500541as_regression_windows_20260310.md](diagnostics/st31500541as_regression_windows_20260310.md): regression window tracing for the `st31500541as` degradation case
- [diagnostics/st31500541as_media_gate_validation_20260310.md](diagnostics/st31500541as_media_gate_validation_20260310.md): validation of `three_stage` soft-gate behavior on `media -> unknown`

## Result Tables

- [prearff_grid_2models_pilot20k_qwen35_v1.md](prearff_grid_2models_pilot20k_qwen35_v1.md): Qwen3.5-4B pilot20k Phase3 summary for the core 5 HDD models
- [prearff_grid_batch7_zs_pilot20k_qwen35_v1.md](prearff_grid_batch7_zs_pilot20k_qwen35_v1.md): Qwen3.5-4B pilot20k Phase3 summary for the batch7 HDD models
- [prearff_grid_2models_pilot20k_qwen35_st315_sg050_v1.md](prearff_grid_2models_pilot20k_qwen35_st315_sg050_v1.md): `st31500541as` soft-gate calibration result
- [prearff_grid_2models_pilot20k_qwen35_9b_st315_v1.md](prearff_grid_2models_pilot20k_qwen35_9b_st315_v1.md): `st31500541as` `Qwen3.5-9B` validation result
- [llm_robust_eval_report_v4_merged_all12.md](llm_robust_eval_report_v4_merged_all12.md): merged evaluation report used by the all12 policy registry
- [llm_vs_nollm_metrics_all12_summary.md](llm_vs_nollm_metrics_all12_summary.md): model-level metric comparison with NA explanations handled separately
- [framework_v1_baseline_lock.csv](framework_v1_baseline_lock.csv): baseline lock reference used by policy selection

## Directory Conventions

- `guides/`: usage, reproducibility, schema, and workflow documentation
- `reports/`: retained public experiment write-ups and merged summaries
- `diagnostics/`: selected deep-dive diagnosis records
- `tables/`: index page for generated result tables that still live at `docs/` root
- `*.md`: narrative summaries and decisions
- `*.csv`: metric tables for plotting or spreadsheet review
- `*.json|*.jsonl`: raw probes, audit snapshots, or intermediate reports

## Versioning Note

The repository root `.gitignore` keeps runtime outputs out of normal version control, while `docs/` stays tracked because it holds the experiment narrative and final summary tables.
