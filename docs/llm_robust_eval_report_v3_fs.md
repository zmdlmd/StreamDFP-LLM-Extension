# LLM Robust Eval Report v3-FS (M1 + M2 phase3)

## Scope

- Models: `st3000dm001`, `hms5c4040ble640`, `hi7`, `hds723030ala640`, `st31500541as`
- Date range: `2014-09-01 ~ 2014-11-09`
- LLM extraction profile: `fs + structured_v2` pilot cache (`20k`)
- Pre-ARFF grid source: `docs/prearff_grid_5models_fs_v1.csv`

## Acceptance rule

- Recall guard: `Recall_c1(LLM) >= Recall_c1(noLLM)`
- ACC guard: `ACC(LLM) >= ACC(noLLM) - 1.0pp`

## Final decision

| model_key | status | action | llm_recall | nollm_recall | delta_recall | llm_acc | nollm_acc | delta_acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| st3000dm001 | PASS | llm_enabled | 63.7259 | 35.7277 | 27.9982 | 98.1343 | 97.4178 | 0.7165 |
| hms5c4040ble640 | FALLBACK | nollm | 13.3333 | 36.6667 | -23.3333 | 99.9445 | 99.9653 | -0.0208 |
| hi7 | FALLBACK | nollm | 66.6667 | 68.0952 | -1.4286 | 99.8361 | 99.4850 | 0.3512 |
| hds723030ala640 | PASS | llm_enabled | 100.0000 | 30.0000 | 70.0000 | 98.9924 | 99.9022 | -0.9098 |
| st31500541as | FALLBACK | nollm | 55.1389 | 56.8056 | -1.6667 | 99.7479 | 99.6927 | 0.0552 |

## Extract quality snapshot (fs + structured_v2 pilot20k)

| model_key | unknown_ratio | mapped_event_ratio | event_density | q50 | q90 | parse_repair_rate | parse_default_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| st3000dm001 | 0.7464 | 0.9729 | 1.9554 | 0.2530 | 0.3655 | 0.0000 | 0.0000 |
| hms5c4040ble640 | 0.6470 | 0.7864 | 2.0292 | 0.3012 | 0.4601 | 0.0000 | 0.0000 |
| hi7 | 0.7338 | 0.7154 | 0.9747 | 0.1872 | 0.4160 | 0.0001 | 0.0000 |
| hds723030ala640 | 0.6997 | 0.6964 | 0.8769 | 0.1985 | 0.4434 | 0.0000 | 0.0000 |
| st31500541as | 0.7823 | 0.8736 | 1.4914 | 0.2105 | 0.3205 | 0.0000 | 0.0000 |

## HMS redundancy note (dense-window check)

- For `hms5c4040ble640`, additional dense-window validation (`2014-03-08 ~ 2014-05-17`) shows no-LLM `l_Recall_c1=100`.
- Decision stays `fallback=nollm`; current LLM signal is treated as redundant on HMS.
- Evidence: `docs/framework_v1_quality_hms5c4040ble640/hms_hd_nollm_baseline_summary.md`.
