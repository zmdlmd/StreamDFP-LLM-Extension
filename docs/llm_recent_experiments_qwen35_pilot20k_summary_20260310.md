# Qwen3.5-4B / pilot20k 实验总结（2026-03-10）

## 1. 本轮目标与范围
- 目标：在 `vLLM` 升级完成后，重新验证 `Qwen3.5-4B` 在 `pilot20k` 子集上的 Phase2 抽取与 Phase3 网格结果，判断其是否可以替代当前锁定策略。
- 范围：`12` 个 HDD 盘型，统一采用 `ZS + structured_v2`，运行标签为 `pilot20k_qwen35`。
- 完整性：
  - Phase2：`12/12` 盘型抽取完成，形成 `cache_*_pilot20k_qwen35.jsonl`
  - Phase3：`432/432` 组组合全部完成，产出 `432` 份结果 CSV
  - 汇总产物已生成：`docs/prearff_grid_2models_pilot20k_qwen35_v1.*` 与 `docs/prearff_grid_batch7_zs_pilot20k_qwen35_v1.*`

## 2. 当前结论
- 当前盘型级结论：`llm_enabled = 7`，`fallback = 5`
- 通过盘型的平均 `ΔRecall = +19.2081pp`
- 本轮 Top3 增益盘型：
  - `hds723030ala640`: `+70.0000pp`
  - `wdcwd30efrx`: `+30.0000pp`
  - `st3000dm001`: `+29.2784pp`
- 持续小幅正增益盘型：
  - `hi7`: `+2.8571pp`
  - `st31500341as`: `+1.6667pp`
  - `hgsthms5c4040ale640`: `+0.6548pp`
- 明确应回退盘型：
  - `wdcwd10eads`: `-90.0000pp`
  - `hds5c3030ala630`: `-30.0000pp`
  - `hms5c4040ble640`: `-23.3333pp`
  - `st31500541as`: `-7.3611pp`
  - `st4000dm000`: `-3.8043pp`
- 本轮所有“最佳组合”都满足 `ACC guard`；是否启用 LLM 的主要判断依据退化为 `Recall` 是否不低于 `no-LLM`。

## 3. 盘型级最佳结果（本轮）
| model_key | action | recall | delta_recall | acc | delta_acc | best_recall_params |
|---|---|---:|---:|---:|---:|---|
| hds5c3030ala630 | nollm | 65.0000 | -30.0000 | 99.8824 | +9.7701 | full70, q=0.00, sev=0.0, rule=0 |
| hds723030ala640 | llm_enabled | 100.0000 | +70.0000 | 98.9532 | -0.9489 | compact9, q=0.00, sev=0.0, rule=0 |
| hgsthms5c4040ale640 | llm_enabled | 75.8929 | +0.6548 | 99.4447 | +0.0483 | full70, q=0.00, sev=0.0, rule=0 |
| hi7 | llm_enabled | 70.9524 | +2.8571 | 99.7914 | +0.3065 | compact14, q=0.55, sev=0.0, rule=0 |
| hitachihds5c4040ale630 | llm_enabled | 0.0000 | +0.0000 | 99.9213 | +0.0000 | compact9, q=0.00, sev=0.0, rule=0 |
| hms5c4040ble640 | nollm | 13.3333 | -23.3333 | 99.9445 | -0.0208 | compact14, q=0.00, sev=0.0, rule=0 |
| st3000dm001 | llm_enabled | 65.0061 | +29.2784 | 98.1415 | +0.7237 | compact9, q=0.55, sev=0.8, rule=0 |
| st31500341as | llm_enabled | 70.2381 | +1.6667 | 99.4381 | +0.0847 | compact9, q=0.00, sev=0.8, rule=0 |
| st31500541as | nollm | 49.4444 | -7.3611 | 99.7061 | +0.0133 | compact9, q=0.00, sev=0.0, rule=0 |
| st4000dm000 | nollm | 54.1005 | -3.8043 | 99.9137 | +0.0342 | compact14, q=0.00, sev=0.0, rule=0 |
| wdcwd10eads | nollm | 0.0000 | -90.0000 | 99.7890 | -0.1899 | compact9, q=0.00, sev=0.0, rule=0 |
| wdcwd30efrx | llm_enabled | 30.0000 | +30.0000 | 99.9003 | +0.0423 | compact14, q=0.00, sev=0.0, rule=0 |

## 4. 与 2026-03-05 锁定策略对照
- 总体上，`11/12` 个盘型的启停结论与 `2026-03-05` 锁定策略一致。
- 唯一发生变化的盘型是 `st31500541as`：
  - 旧结论：`llm_enabled`，`ΔRecall=+11.5278`
  - 本轮结果：`nollm`，`ΔRecall=-7.3611`
  - 结论：当前 `pilot20k_qwen35` 结果不能直接替换该盘型的既有锁定策略
- `hi7`：
  - `ΔRecall` 保持 `+2.8571`
  - `ΔACC` 从 `-0.0490` 改善到 `+0.3065`
  - 最佳参数从 `compact14, q=0.00, sev=0.8, rule=0` 变为 `compact14, q=0.55, sev=0.0, rule=0`
- `st3000dm001`：
  - `ΔRecall` 从 `+28.0157` 提升到 `+29.2784`
  - `ΔACC` 从 `+0.6634` 提升到 `+0.7237`
  - 最佳参数从 `rule=1` 切换为 `rule=0`
- `hds723030ala640`：
  - `ΔRecall` 保持 `+70.0000`
  - 但最佳组合从历史 `full70` 切到当前 `compact9`
  - `ΔACC` 从 `+0.0978` 变为 `-0.9489`，虽然仍在 guard 内，但安全边际明显变小
- 其余盘型基本保持稳定：
  - 持续 `llm_enabled`：`hgsthms5c4040ale640`、`hitachihds5c4040ale630`、`st31500341as`、`wdcwd30efrx`
  - 持续 `fallback`：`hds5c3030ala630`、`hms5c4040ble640`、`st4000dm000`、`wdcwd10eads`

## 5. 解释与判断
- 这轮实验的核心价值是：完成了 `Qwen3.5-4B` 在 `pilot20k` 子集上的全链路兼容性验证，证明升级后的 `vLLM + Qwen3.5-4B` 可以稳定跑通 `12` 盘型的 Phase2/Phase3。
- 从结果看，`Qwen3.5-4B` 并没有整体推翻原有锁定策略，更多是“局部改善 + 个别回退”：
  - 明显增益：`hds723030ala640`、`st3000dm001`、`wdcwd30efrx`
  - 明显风险：`st31500541as`
- 因为本轮仅使用 `pilot20k` 子集，不建议仅凭这轮结果直接覆盖 `2026-03-05` 的全局策略锁定。

## 6. 建议
1. 继续保留 `docs/cross_model_policy_registry_v1_all12.md` 作为当前默认锁定策略，不用本轮 `pilot20k_qwen35` 直接覆盖。
2. 若后续准备推广 `Qwen3.5-4B` 为默认模型，优先补做两类复核：
   - `st31500541as`：确认当前负增益是否为子集波动还是模型退化
   - `hds723030ala640`：确认 `compact9` 虽然 Recall 持平，但 ACC 边际变差是否可接受
3. 若只在 `pilot20k` 范围内做快速试验，可以优先参考本轮对 `hi7` 与 `st3000dm001` 的新参数。

## 7. 相关产物
- Phase2 汇总：`logs/framework_v1/phase2_all12_pilot20k_qwen35_20260308_101314.tsv`
- Phase3 主批次：`docs/prearff_grid_2models_pilot20k_qwen35_v1.csv` / `docs/prearff_grid_2models_pilot20k_qwen35_v1.md`
- Phase3 batch7：`docs/prearff_grid_batch7_zs_pilot20k_qwen35_v1.csv` / `docs/prearff_grid_batch7_zs_pilot20k_qwen35_v1.md`
- 历史锁定参考：`docs/llm_recent_experiments_master_summary_20260305.md`
