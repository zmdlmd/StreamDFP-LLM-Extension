# v3 FS vs ZS 对比

| model_key | zs_status | fs_status | zs_recall | fs_recall | fs-zs recall | zs_acc | fs_acc | fs-zs acc | recommended |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| st3000dm001 | PASS | PASS | 63.7434 | 63.7259 | -0.0175 | 98.0812 | 98.1343 | 0.0530 | zs |
| hms5c4040ble640 | FALLBACK | FALLBACK | 13.3333 | 13.3333 | 0.0000 | 99.9445 | 99.9445 | 0.0000 | fallback |
| hi7 | PASS | FALLBACK | 70.9524 | 66.6667 | -4.2857 | 99.4360 | 99.8361 | 0.4001 | zs |
| hds723030ala640 | PASS | PASS | 100.0000 | 100.0000 | 0.0000 | 100.0000 | 98.9924 | -1.0076 | zs |
| st31500541as | PASS | FALLBACK | 68.3333 | 55.1389 | -13.1944 | 99.7957 | 99.7479 | -0.0478 | zs |

## 建议

- st3000dm001: 推荐 `zs`（ZS=PASS, FS=PASS）。
- hms5c4040ble640: 推荐 `fallback`（ZS=FALLBACK, FS=FALLBACK；dense-window no-LLM recall saturated, LLM redundant）。
- hi7: 推荐 `zs`（ZS=PASS, FS=FALLBACK）。
- hds723030ala640: 推荐 `zs`（ZS=PASS, FS=PASS）。
- st31500541as: 推荐 `zs`（ZS=PASS, FS=FALLBACK）。

证据：`docs/framework_v1_quality_hms5c4040ble640/hms_hd_nollm_baseline_summary.md`
