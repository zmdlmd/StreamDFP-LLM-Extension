# Qwen3-4B-Instruct-2507 vs Qwen3.5-4B vs Qwen3.5-Plus 对照表（2026-03-15）

## 口径

- `Qwen3-4B-Instruct-2507`：来源于历史 merged summary。
- `Qwen3.5-4B`：来源于 `pilot20k_qwen35` 的 HDD phase3 汇总。
- `Qwen3.5-Plus`：来源于 `pilot20k_qwen35plus_api` 的 HDD phase3 汇总。
- HDD 盘型按“盘型级最佳组合”对比；`mc1_pilot20k` 单独说明。

## HDD 盘型级对照

| model_key | Qwen3-Instruct action | ΔRecall | Qwen3.5-4B action | ΔRecall | Qwen3.5-Plus action | ΔRecall | Plus vs 4B | Plus vs Instruct |
|---|---|---:|---|---:|---|---:|---:|---:|
| hds5c3030ala630 | nollm | -30.0000 | nollm | -30.0000 | nollm | -30.0000 | 0.0000 | 0.0000 |
| hds723030ala640 | llm_enabled | 70.0000 | llm_enabled | 70.0000 | llm_enabled | 70.0000 | 0.0000 | 0.0000 |
| hgsthms5c4040ale640 | llm_enabled | 0.6548 | llm_enabled | 0.6548 | llm_enabled | 0.6548 | 0.0000 | -0.0000 |
| hi7 | llm_enabled | 2.8571 | llm_enabled | 2.8571 | llm_enabled | 6.1905 | 3.3333 | 3.3334 |
| hitachihds5c4040ale630 | llm_enabled | 0.0000 | llm_enabled | 0.0000 | llm_enabled | 0.0000 | 0.0000 | 0.0000 |
| hms5c4040ble640 | nollm | -23.3333 | nollm | -23.3333 | nollm | -23.3333 | 0.0000 | -0.0000 |
| st3000dm001 | llm_enabled | 28.0157 | llm_enabled | 29.2784 | llm_enabled | 26.3619 | -2.9165 | -1.6538 |
| st31500341as | llm_enabled | 1.6667 | llm_enabled | 1.6667 | llm_enabled | 7.8571 | 6.1905 | 6.1904 |
| st31500541as | llm_enabled | 11.5278 | nollm | -7.3611 | nollm | -7.3611 | 0.0000 | -18.8889 |
| st4000dm000 | nollm | -3.8043 | nollm | -3.8043 | nollm | -3.8043 | 0.0000 | -0.0000 |
| wdcwd10eads | nollm | -90.0000 | nollm | -90.0000 | nollm | -90.0000 | 0.0000 | 0.0000 |
| wdcwd30efrx | llm_enabled | 30.0000 | llm_enabled | 30.0000 | llm_enabled | 30.0000 | 0.0000 | 0.0000 |

## MC1 补充说明

| model_key | Qwen3-Instruct | Qwen3.5-4B | Qwen3.5-Plus |
|---|---|---|---|
| mc1_pilot20k_stratified_v2 | action=llm_enabled, ΔRecall=+2.2296, params=compact14, q=0.00, sev=0.0, rule=0 | action=llm_enabled, ΔRecall=+2.2296, params=compact14, q=0.00, sev=0.0, rule=0 | action=llm_enabled, ΔRecall=+2.2296, params=compact14, q=0.00, sev=0.0, rule=0 |

说明：`mc1` 在旧版错误 `pilot20k` 输入上确实存在 `kept=0` 和 legacy 才能复现的问题；但在修正后的 `pilot20k_stratified_v2` 输入上，三模型都已经能在当前严格 `phase3` 口径下得到相同的正增益结果。

## 简要结论

- HDD 启用盘型数：`Qwen3-Instruct = 8`，`Qwen3.5-4B = 7`，`Qwen3.5-Plus = 7`。
- HDD 通过盘型平均 `ΔRecall`：`Qwen3-Instruct = 18.0903`，`Qwen3.5-4B = 19.2081`，`Qwen3.5-Plus = 20.1520`。
- `Qwen3.5-Plus` 相比 `Qwen3.5-4B` 的主要增益盘型是 `hi7` 和 `st31500341as`；相比 `Qwen3-Instruct` 仍然没有修复 `st31500541as` 这类 hard case。
- `Qwen3.5-Plus` 没有扩大 HDD 的启用盘型覆盖面，只是在已有可启用盘型上做了小幅增强。
- `mc1` 需要单独看：旧错误输入下的结论已经被废弃，修正后的 `mc1_stratified_v2` 显示三模型都能复现 `+2.2296`，差异主要体现在 `phase2` 抽取质量和工程可用性，而不是 best-case `phase3` 指标。
