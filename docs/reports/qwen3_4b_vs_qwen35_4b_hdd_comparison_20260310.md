# Qwen3-4B vs Qwen3.5-4B 盘型级对照（2026-03-10）

## 对照口径

- 旧模型：`Qwen3-4B-Instruct-2507`，结果来源于 [llm_recent_experiments_master_summary_20260305.md](/root/autodl-tmp/StreamDFP/docs/reports/llm_recent_experiments_master_summary_20260305.md)
- 新模型：`Qwen3.5-4B`，结果来源于 [llm_recent_experiments_qwen35_pilot20k_summary_20260310.md](/root/autodl-tmp/StreamDFP/docs/reports/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md)
- 范围：`12` 个 HDD 盘型，不含 `mc1_pilot20k`
- 口径：按盘型级“最佳组合”结果对比，重点看 `action / Recall / ΔRecall / ACC`

## 总结

- 旧模型：`llm_enabled = 8`，`fallback = 4`
- 新模型：`llm_enabled = 7`，`fallback = 5`
- `11/12` 个盘型启停结论一致，唯一发生策略变化的是 `st31500541as`
- 新模型相对更明显的正向变化在 `hi7` 和 `st3000dm001`
- 新模型的核心退化盘型是 `st31500541as`

## 盘型级对照表

| model_key | 旧 action | 旧 Recall | 旧 ΔRecall | 新 action | 新 Recall | 新 ΔRecall | ΔRecall 变化 | 旧 ACC | 新 ACC | 备注 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| hds5c3030ala630 | nollm | 65.0000 | -30.0000 | nollm | 65.0000 | -30.0000 | +0.0000 | 99.8824 | 99.8824 | 结论不变 |
| hds723030ala640 | llm_enabled | 100.0000 | +70.0000 | llm_enabled | 100.0000 | +70.0000 | +0.0000 | 100.0000 | 98.9532 | Recall 持平，ACC 边际下降 |
| hgsthms5c4040ale640 | llm_enabled | 75.8929 | +0.6548 | llm_enabled | 75.8929 | +0.6548 | +0.0000 | 99.4447 | 99.4447 | 基本一致 |
| hi7 | llm_enabled | 70.9524 | +2.8571 | llm_enabled | 70.9524 | +2.8571 | +0.0000 | 99.4360 | 99.7914 | Recall 持平，ACC 明显改善 |
| hitachihds5c4040ale630 | llm_enabled | 0.0000 | +0.0000 | llm_enabled | 0.0000 | +0.0000 | +0.0000 | 99.9213 | 99.9213 | 基本一致 |
| hms5c4040ble640 | nollm | 13.3333 | -23.3333 | nollm | 13.3333 | -23.3333 | +0.0000 | 99.9445 | 99.9445 | 结论不变 |
| st3000dm001 | llm_enabled | 63.7434 | +28.0157 | llm_enabled | 65.0061 | +29.2784 | +1.2627 | 98.0812 | 98.1415 | 新模型小幅更优 |
| st31500341as | llm_enabled | 70.2381 | +1.6667 | llm_enabled | 70.2381 | +1.6667 | +0.0000 | 99.4381 | 99.4381 | 基本一致 |
| st31500541as | llm_enabled | 68.3333 | +11.5278 | nollm | 49.4444 | -7.3611 | -18.8889 | 99.7957 | 99.7061 | 唯一策略变化，旧正增益变为新负增益 |
| st4000dm000 | nollm | 54.1005 | -3.8043 | nollm | 54.1005 | -3.8043 | +0.0000 | 99.9137 | 99.9137 | 结论不变 |
| wdcwd10eads | nollm | 0.0000 | -90.0000 | nollm | 0.0000 | -90.0000 | +0.0000 | 99.7890 | 99.7890 | 结论不变 |
| wdcwd30efrx | llm_enabled | 30.0000 | +30.0000 | llm_enabled | 30.0000 | +30.0000 | +0.0000 | 99.9003 | 99.9003 | 基本一致 |

## 结论

- `Qwen3.5-4B` 没有在 `12` 个 HDD 盘型上全面超过 `Qwen3-4B-Instruct-2507`
- 新模型在多数盘型上与旧模型接近，但提升主要集中在 `ACC` 边际或个别盘型的小幅 `Recall` 增益
- 真正阻止新模型直接替代旧模型的关键盘型是 `st31500541as`
- 对 `st31500541as`，同子集 A/B 已确认更像模型或抽取链路退化，而不是子集波动，详见 [st31500541as_ab_same_subset_20260310.md](/root/autodl-tmp/StreamDFP/docs/diagnostics/st31500541as_ab_same_subset_20260310.md)
