# Tables

This directory keeps the retained public CSV tables referenced by the main summaries. One-off grid outputs, calibration sweeps, and intermediate experimental tables have been moved to `../archive/experiments/`.

## Included

- [framework_v1_baseline_lock.csv](framework_v1_baseline_lock.csv): baseline lock reference used by policy selection
- [llm_robust_eval_report_v4_merged_all12.csv](llm_robust_eval_report_v4_merged_all12.csv): retained merged guard report in CSV form
- [llm_vs_nollm_metrics_all12_summary.csv](llm_vs_nollm_metrics_all12_summary.csv): retained model-level metric summary in CSV form
- [qwen3_instruct_vs_qwen35_4b_vs_qwen35_plus_comparison_20260315.csv](qwen3_instruct_vs_qwen35_4b_vs_qwen35_plus_comparison_20260315.csv): HDD cross-model comparison table
- [mc1_phase2_quality_comparison_stratified_v2_20260319.csv](mc1_phase2_quality_comparison_stratified_v2_20260319.csv): repaired `mc1` Phase 2 quality table
- [mc1_phase3_comparison_stratified_v2_20260323.csv](mc1_phase3_comparison_stratified_v2_20260323.csv): repaired `mc1` Phase 3 comparison table

## Notes

- The matching narrative summaries live under `../reports/`.
- Historical per-run grids and ad hoc calibration tables were intentionally moved out of the public docs surface.
