# LLM Robust Eval Report v4 (All Models + MC1 Pilot, ZS)

- Source A (legacy 5-model ZS): `docs/llm_robust_eval_report_v3.csv`
- Source B (new batch7 ZS): `docs/llm_robust_eval_report_v4_batch7_zs.csv`
- Source C (MC1 phase3 retry): `docs/prearff_grid_mc1_v1.csv`
- Acceptance: `Recall(LLM)>=Recall(noLLM)` and `ACC(LLM)>=ACC(noLLM)-1.0pp`
- Summary: PASS `9`, FALLBACK `4`, N/A `0` (total `13`)

| model | status | action | recall_llm | recall_nollm | delta_recall | acc_llm | acc_nollm | delta_acc | best_recall_params |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| hds5c3030ala630 | FALLBACK | nollm | 65.0000 | 95.0000 | -30.0000 | 99.8824 | 90.1123 | +9.7701 | full70, q=0.00, sev=0.0, rule=0 |
| hds723030ala640 | PASS | llm_enabled | 100.0000 | 30.0000 | +70.0000 | 100.0000 | 99.9022 | +0.0978 | full70, q=0.00, sev=0.0, rule=0 |
| hgsthms5c4040ale640 | PASS | llm_enabled | 75.8929 | 75.2381 | +0.6548 | 99.4447 | 99.3963 | +0.0483 | full70, q=0.00, sev=0.0, rule=0 |
| hi7 | PASS | llm_enabled | 70.9524 | 68.0952 | +2.8571 | 99.4360 | 99.4850 | -0.0490 | compact14, q=0.00, sev=0.8, rule=0 |
| hitachihds5c4040ale630 | PASS | llm_enabled | 0.0000 | 0.0000 | +0.0000 | 99.9213 | 99.9213 | +0.0000 | compact9, q=0.00, sev=0.0, rule=0 |
| hms5c4040ble640 | FALLBACK | nollm | 13.3333 | 36.6667 | -23.3333 | 99.9445 | 99.9653 | -0.0208 | compact14, q=0.00, sev=0.0, rule=0 |
| mc1_pilot20k | PASS | llm_enabled | 100.0000 | 97.7704 | +2.2296 | 99.5489 | 99.4956 | +0.0532 | compact14, q=0.00, sev=0.0, rule=0 |
| st3000dm001 | PASS | llm_enabled | 63.7434 | 35.7277 | +28.0157 | 98.0812 | 97.4178 | +0.6634 | compact9, q=0.55, sev=0.8, rule=1 |
| st31500341as | PASS | llm_enabled | 70.2381 | 68.5714 | +1.6667 | 99.4381 | 99.3534 | +0.0847 | compact9, q=0.00, sev=0.8, rule=0 |
| st31500541as | PASS | llm_enabled | 68.3333 | 56.8056 | +11.5278 | 99.7957 | 99.6927 | +0.1030 | full70, q=0.00, sev=0.0, rule=0 |
| st4000dm000 | FALLBACK | nollm | 54.1005 | 57.9049 | -3.8043 | 99.9137 | 99.8795 | +0.0342 | compact14, q=0.00, sev=0.0, rule=0 |
| wdcwd10eads | FALLBACK | nollm | 0.0000 | 90.0000 | -90.0000 | 99.7890 | 99.9789 | -0.1899 | compact9, q=0.00, sev=0.0, rule=0 |
| wdcwd30efrx | PASS | llm_enabled | 30.0000 | 0.0000 | +30.0000 | 99.9003 | 99.8580 | +0.0423 | compact14, q=0.00, sev=0.0, rule=0 |

## Notes
- Status meaning:
  - `PASS`: satisfies guard (`Recall(LLM)>=Recall(noLLM)` and `ACC(LLM)>=ACC(noLLM)-1.0pp`), action=`llm_enabled`.
  - `FALLBACK`: fails guard, action=`nollm`.
  - `N/A`: not evaluable (none in current table).
- `best_recall_params` records the best-recall phase3 config used for that model.
- `mc1_pilot20k` 是 SSD 数据集试点（20k 样本），口径与 HDD 报告不同，不直接用于跨介质绝对比较。
- 该行主要用于跟踪“同数据同口径”下 LLM 增益方向。
- MC1 phase3 网格已补齐完成（`compact9` 12/12 + `compact14` 12/12），汇总见 `docs/prearff_grid_mc1_v1.csv` 与 `docs/prearff_grid_mc1_v1.md`。
- FS spot-check（2 models）见 `docs/fs_spotcheck_2models_v1_20260305.md`。
- FALLBACK 冻结复核见 `docs/fallback_freeze_review_v1_20260305.md`。
