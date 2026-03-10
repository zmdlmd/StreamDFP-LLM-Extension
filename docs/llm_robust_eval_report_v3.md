# LLM Robust Eval Report v3 (M1 + M2 phase3)

## Scope

- Models: `st3000dm001`, `hms5c4040ble640`, `hi7`, `hds723030ala640`, `st31500541as`
- Date range: `2014-09-01 ~ 2014-11-09`
- LLM extraction profile: `zs + structured_v2` pilot cache (`20k`)
- Pre-ARFF grid per model: `3 dims x 3 q_gate x 2 sev_sum x 2 rule_match = 36`
- Result sources:
  - `docs/prearff_grid_2models_v1.csv` (M1)
  - `docs/prearff_grid_3models_m2_v1.csv` (M2)
  - `docs/prearff_grid_st315_v1.csv` (ST315 contractfix refresh)
  - `docs/llm_robust_eval_report_v3.csv`

## Acceptance rule

- Recall guard: `Recall_c1(LLM) >= Recall_c1(noLLM)`
- ACC guard: `ACC(LLM) >= ACC(noLLM) - 1.0pp`

## Final decision

| model_key | status | action | llm_recall | nollm_recall | delta_recall | llm_acc | nollm_acc | delta_acc | selected_combo |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| st3000dm001 | PASS | llm_enabled | 63.7434 | 35.7277 | 28.0157 | 98.0812 | 97.4178 | 0.6634 | compact9_q0.55_sev0.8_rule1 |
| hms5c4040ble640 | FALLBACK | nollm | 13.3333 | 36.6667 | -23.3333 | 99.9445 | 99.9653 | -0.0208 | from_phase3_grid |
| hi7 | PASS | llm_enabled | 70.9524 | 68.0952 | 2.8571 | 99.4360 | 99.4850 | -0.0490 | compact14_q0.00_sev0.8_rule0 |
| hds723030ala640 | PASS | llm_enabled | 100.0000 | 30.0000 | 70.0000 | 100.0000 | 99.9022 | 0.0978 | full70_q0.00_sev0.0_rule0 |
| st31500541as | PASS | llm_enabled | 68.3333 | 56.8056 | 11.5278 | 99.7957 | 99.6927 | 0.1030 | full70_q0.00_sev0.0_rule0 |

## Extract quality snapshot (zs + structured_v2 pilot20k)

| model_key | unknown_ratio | mapped_event_ratio | event_density | q50 | q90 | parse_repair_rate | parse_default_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| st3000dm001 | 0.6896 | 0.9910 | 2.7191 | 0.4880 | 0.7133 | 0.0000 | 0.0000 |
| hms5c4040ble640 | 0.5945 | 0.9648 | 2.3866 | 0.5605 | 0.8059 | 0.0000 | 0.0000 |
| hi7 | 0.7147 | 0.8698 | 1.6866 | 0.3825 | 0.7172 | 0.0000 | 0.0000 |
| hds723030ala640 | 0.6816 | 0.8550 | 1.6620 | 0.3825 | 0.7198 | 0.0000 | 0.0000 |
| st31500541as | 0.7693 | 0.9473 | 2.5263 | 0.3965 | 0.6793 | 0.0000 | 0.0000 |

## Key findings

1. PASS models: `st3000dm001, hi7, hds723030ala640, st31500541as`.
2. FALLBACK models: `hms5c4040ble640`.
3. N/A models: `none`.
4. ST315 baseline is switched to contractfix and now participates in guard evaluation.

## HMS redundancy note (dense-window check)

- Additional CPU-only density scan selected HMS high-failure window `2014-03-08 ~ 2014-05-17`.
- no-LLM baseline on this window remains saturated on recall (`Local mean l_Recall_c1 = 100`), confirming strong native SMART separability.
- Decision for HMS remains `fallback=nollm`; LLM signal is treated as redundant for current framework.
- Evidence: `docs/framework_v1_quality_hms5c4040ble640/hms_hd_nollm_baseline_summary.md`.

## Next action

- Keep PASS models enabled with selected combo.
- Keep FALLBACK models on no-LLM while iterating extraction quality/policy.
