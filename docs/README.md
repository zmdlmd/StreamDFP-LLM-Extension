# Docs Index

This directory mixes framework notes, experiment summaries, policy tables, and one-off debugging records. If you only need the main storyline, use the following reading order.

## Start Here

- [../README.md](../README.md): repository overview and main entry points
- [REPOSITORY_LAYOUT.md](REPOSITORY_LAYOUT.md): what each top-level directory is for
- [GITHUB_UPLOAD_CHECKLIST.md](GITHUB_UPLOAD_CHECKLIST.md): what to stage and what to keep local before pushing
- [GITHUB_METADATA.md](GITHUB_METADATA.md): GitHub `About`, topics, and release text aligned with upstream attribution
- [PUBLIC_REPRODUCIBILITY.md](PUBLIC_REPRODUCIBILITY.md): environment setup and end-to-end reproduction steps
- [PUBLIC_FIRST_RELEASE_SCOPE.md](PUBLIC_FIRST_RELEASE_SCOPE.md): recommended `docs/` and `llm/` scope for the first public release
- [cross_model_llm_framework_v1_final.md](cross_model_llm_framework_v1_final.md): main write-up for the LLM-enhanced `framework_v1`
- [cross_model_execution_checklist_v1_final.md](cross_model_execution_checklist_v1_final.md): execution checklist for the cross-model pipeline
- [cross_model_policy_registry_v1.md](cross_model_policy_registry_v1.md): frozen 5-model policy after the first FS/ZS comparison
- [cross_model_policy_registry_v1_all12.md](cross_model_policy_registry_v1_all12.md): merged model-level policy table covering 12 HDD models plus MC1 pilot
- [cross_model_llm_framework_v1_batch7_zs_final.md](cross_model_llm_framework_v1_batch7_zs_final.md): final write-up for the batch7 ZS expansion

## Recent Experiment Summaries

- [llm_recent_experiments_master_summary_20260305.md](llm_recent_experiments_master_summary_20260305.md): baseline lock and merged model-level conclusions before the Qwen3.5 refresh
- [llm_recent_experiments_qwen35_pilot20k_summary_20260310.md](llm_recent_experiments_qwen35_pilot20k_summary_20260310.md): Qwen3.5-4B `pilot20k` results across 12 HDD models
- [qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md](qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md): side-by-side comparison between `Qwen3-4B-Instruct-2507` and `Qwen3.5-4B`
- [llm_robust_eval_report_v4_merged_all12.md](llm_robust_eval_report_v4_merged_all12.md): merged policy guard table across all 12 HDD models plus MC1 pilot

## Model-Specific Diagnosis

- [st31500541as_ab_same_subset_20260310.md](st31500541as_ab_same_subset_20260310.md): same-subset A/B comparison for `st31500541as`
- [st31500541as_regression_windows_20260310.md](st31500541as_regression_windows_20260310.md): regression window tracing for the `st31500541as` degradation case
- [st31500541as_media_gate_validation_20260310.md](st31500541as_media_gate_validation_20260310.md): validation of `three_stage` soft-gate behavior on `media -> unknown`

## Result Tables

- [prearff_grid_2models_pilot20k_qwen35_v1.md](prearff_grid_2models_pilot20k_qwen35_v1.md): Qwen3.5-4B pilot20k Phase3 summary for the core 5 HDD models
- [prearff_grid_batch7_zs_pilot20k_qwen35_v1.md](prearff_grid_batch7_zs_pilot20k_qwen35_v1.md): Qwen3.5-4B pilot20k Phase3 summary for the batch7 HDD models
- [prearff_grid_2models_pilot20k_qwen35_st315_sg050_v1.md](prearff_grid_2models_pilot20k_qwen35_st315_sg050_v1.md): `st31500541as` soft-gate calibration result
- [prearff_grid_2models_pilot20k_qwen35_9b_st315_v1.md](prearff_grid_2models_pilot20k_qwen35_9b_st315_v1.md): `st31500541as` `Qwen3.5-9B` validation result
- [llm_robust_eval_report_v4_merged_all12.md](llm_robust_eval_report_v4_merged_all12.md): merged evaluation report used by the all12 policy registry
- [llm_vs_nollm_metrics_all12_summary.md](llm_vs_nollm_metrics_all12_summary.md): model-level metric comparison with NA explanations handled separately
- [framework_v1_baseline_lock.csv](framework_v1_baseline_lock.csv): baseline lock reference used by policy selection

## Directory Conventions

- `framework_v1_quality_*`: quality analysis outputs for specific model groups
- `model_quality*`: cache quality summaries across tuning rounds
- `*.md`: narrative summaries and decisions
- `*.csv`: metric tables for plotting or spreadsheet review
- `*.json|*.jsonl`: raw probes, audit snapshots, or intermediate reports

## Upload Note

The repository root `.gitignore` is configured to keep runtime outputs out of Git, but the `docs/` directory is intentionally left trackable because it holds the experiment narrative and final summary tables.
