# Cross-model LLM Framework v1 Batch7 Final Report (ZS)

- Models: `hgsthms5c4040ale640`, `st31500341as`, `hitachihds5c4040ale630`, `wdcwd30efrx`, `wdcwd10eads`, `st4000dm000`, `hds5c3030ala630`
- Date range: `2014-09-01 ~ 2014-11-09`
- Pilot windows per model: `20000`
- Acceptance: `Recall(LLM)>=Recall(noLLM)` and `ACC(LLM)>=ACC(noLLM)-1.0pp`

- Result: PASS `4/7`, FALLBACK `3/7`

| model | status | action | selected_config | recall_llm | recall_nollm | delta_recall | acc_llm | acc_nollm | delta_acc |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| hds5c3030ala630 | FALLBACK | nollm | full70,q=0.00,sev=0.0,rule=0 | 65.0000 | 95.0000 | -30.0000 | 99.8824 | 90.1123 | +9.7701 |
| hgsthms5c4040ale640 | PASS | llm_enabled | full70,q=0.00,sev=0.0,rule=0 | 75.8929 | 75.2381 | +0.6548 | 99.4447 | 99.3963 | +0.0483 |
| hitachihds5c4040ale630 | PASS | llm_enabled | compact9,q=0.00,sev=0.0,rule=0 | 0.0000 | 0.0000 | +0.0000 | 99.9213 | 99.9213 | +0.0000 |
| st31500341as | PASS | llm_enabled | compact9,q=0.00,sev=0.8,rule=0 | 70.2381 | 68.5714 | +1.6667 | 99.4381 | 99.3534 | +0.0847 |
| st4000dm000 | FALLBACK | nollm | compact14,q=0.00,sev=0.0,rule=0 | 54.1005 | 57.9049 | -3.8043 | 99.9137 | 99.8795 | +0.0342 |
| wdcwd10eads | FALLBACK | nollm | compact9,q=0.00,sev=0.0,rule=0 | 0.0000 | 90.0000 | -90.0000 | 99.7890 | 99.9789 | -0.1899 |
| wdcwd30efrx | PASS | llm_enabled | compact14,q=0.00,sev=0.0,rule=0 | 30.0000 | 0.0000 | +30.0000 | 99.9003 | 99.8580 | +0.0423 |

## Artifacts
- Public merged report: `docs/llm_robust_eval_report_v4_merged_all12.csv` / `docs/llm_robust_eval_report_v4_merged_all12.md`
- Public merged registry: `docs/cross_model_policy_registry_v1_all12.md`
- Historical batch7 intermediate tables are intentionally not retained in the public repo.
