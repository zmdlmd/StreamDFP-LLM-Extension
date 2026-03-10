# FALLBACK Freeze Review v1 - 2026-03-05

Scope: one-time low-cost closure for current fallback models (no new large rerun).

| model_key | delta_recall | delta_acc | action | freeze_reason | evidence_csv |
|---|---:|---:|---|---|---|
| hds5c3030ala630 | -30.0000 | +9.7701 | nollm | guard_fail_after_existing_phase3 | `docs/llm_robust_eval_report_v4_merged_all12.csv` |
| hms5c4040ble640 | -23.3333 | -0.0208 | nollm | phase3_grid_fail_guard | `docs/llm_robust_eval_report_v4_merged_all12.csv` |
| st4000dm000 | -3.8043 | +0.0342 | nollm | guard_fail_after_existing_phase3 | `docs/llm_robust_eval_report_v4_merged_all12.csv` |
| wdcwd10eads | -90.0000 | -0.1899 | nollm | guard_fail_after_existing_phase3 | `docs/llm_robust_eval_report_v4_merged_all12.csv` |

Decision:
- Freeze these models as `fallback=nollm` for v1 rollout.
- Do not start new extraction cycles unless guard definition changes.
