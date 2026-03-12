# Cross-model Policy Registry v1 (All 13 Models)

Lock date: 2026-03-05

Default extraction profile is `zs`; per-model action is decided by v4 merged guard results.

| model_key | action | best_recall_params | chosen_variant | chosen_extract_profile | evidence_csv | evidence_md |
|---|---|---|---|---|---|---|
| hds5c3030ala630 | nollm | full70, q=0.00, sev=0.0, rule=0 | full70 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| hds723030ala640 | llm_enabled | full70, q=0.00, sev=0.0, rule=0 | full70 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| hgsthms5c4040ale640 | llm_enabled | full70, q=0.00, sev=0.0, rule=0 | full70 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| hi7 | llm_enabled | compact14, q=0.00, sev=0.8, rule=0 | compact14 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| hitachihds5c4040ale630 | llm_enabled | compact9, q=0.00, sev=0.0, rule=0 | compact9 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| hms5c4040ble640 | nollm | compact14, q=0.00, sev=0.0, rule=0 | compact14 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| mc1_pilot20k | llm_enabled | compact14, q=0.00, sev=0.0, rule=0 | compact14 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| st3000dm001 | llm_enabled | compact9, q=0.55, sev=0.8, rule=1 | compact9 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| st31500341as | llm_enabled | compact9, q=0.00, sev=0.8, rule=0 | compact9 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| st31500541as | llm_enabled | full70, q=0.00, sev=0.0, rule=0 | full70 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| st4000dm000 | nollm | compact14, q=0.00, sev=0.0, rule=0 | compact14 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| wdcwd10eads | nollm | compact9, q=0.00, sev=0.0, rule=0 | compact9 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |
| wdcwd30efrx | llm_enabled | compact14, q=0.00, sev=0.0, rule=0 | compact14 | zs | `docs/llm_robust_eval_report_v4_merged_all12.csv` | `docs/reports/llm_robust_eval_report_v4_merged_all12.md` |

Decision rule:
- `action=llm_enabled`: model passes guard, enable LLM path with listed params.
- `action=nollm`: model fails guard, keep fallback to no-LLM.

Primary evidence source: `docs/llm_robust_eval_report_v4_merged_all12.csv`.
