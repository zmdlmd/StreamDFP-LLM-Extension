# LLM 增强实验总总结（最近批次）

## 1. 本轮目标与范围
- 目标：在不破坏基线稳定性的前提下，评估 LLM 增强对磁盘故障预测 Recall/ACC 的增益。
- 范围：HDD 多盘型（HI7 体系 + batch7 ZS 扩展）与 SSD MC1（pilot20k）并行验证。
- 统一验收口径：`Recall(LLM) >= Recall(noLLM)` 且 `ACC(LLM) >= ACC(noLLM)-1.0pp`。

## 2. 本轮执行主线（按流程）
1. Phase2（LLM 抽取）：统一短 JSON + structured_v2 prompt，形成 cache。
2. Phase3（pre-ARFF 网格）：`q_gate × sev_sum_gate × require_rule_match × dim_key` 网格。
3. 训练评估：固定 simulate 参数口径，输出 CSV 指标并回写总报告。
4. 策略收敛：盘型级 PASS/FALLBACK 决策，失败盘型自动回退 no-LLM。

## 3. 总体结果（截至本次同步）
- 总盘型数：13
- PASS：9
- FALLBACK：4
- N/A：0

### 3.1 盘型级结果总表（v4 merged all12）
| model_key | status | action | llm_recall | nollm_recall | delta_recall | llm_acc | nollm_acc | delta_acc | best_recall_params |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
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
## 4. FS vs ZS 结论（已做对照盘型）
| model_key | zs_status | zs_delta_recall | zs_delta_acc | fs_status | fs_delta_recall | fs_delta_acc | 推荐 |
|---|---|---:|---:|---|---:|---:|---|
| hds723030ala640 | PASS | +70.0000 | +0.0978 | PASS | +70.0000 | -0.9098 | zs |
| hi7 | PASS | +2.8571 | -0.0490 | FALLBACK | -1.4286 | +0.3512 | zs |
| hms5c4040ble640 | FALLBACK | -23.3333 | -0.0208 | FALLBACK | -23.3333 | -0.0208 | fallback |
| st3000dm001 | PASS | +28.0157 | +0.6634 | PASS | +27.9982 | +0.7165 | zs |
| st31500541as | PASS | +11.5278 | +0.1030 | FALLBACK | -1.6667 | +0.0552 | zs |

- 当前已验证盘型中，ZS 在稳定性和综合收益上整体优于 FS；HMS 盘型 FS/ZS 都触发 fallback。

## 5. MC1（SSD）最新专项结果
- 网格完成状态：`compact9` 12/12 + `compact14` 12/12（已补齐）。
- compact14：Recall=100.0000，ACC=99.5489，ΔRecall=+2.2296，ΔACC=+0.0532
- compact9：Recall=97.3780，ACC=99.8322，ΔRecall=-0.3925，ΔACC=+0.3366
- 最优方案：`compact14` + q=0.0 + sev=0.0 + rule=0（按 Recall 优先且满足 ACC guard）。

## 6. 关键工程发现（这轮最重要）
1. full70 在 MC1 上成本高、收益低：大量组合出现 `kept=0`（注入全零），导致训练端高成本空跑。
2. compact14 在 MC1 上更优：Recall 提升且 ACC 不降，且整体更稳。
3. HMS 的核心瓶颈不在“是否抽取成功”，而在“注入信号可分性/可利用性不足”。
4. 进程托管必须脱离临时会话：采用 screen 后，长任务稳定性明显改善。

## 7. 当前可复现产物（主入口）
- 总报告（跨盘型）：`docs/llm_robust_eval_report_v4_merged_all12.csv` / `docs/reports/llm_robust_eval_report_v4_merged_all12.md`
- 策略注册表：`docs/reports/cross_model_policy_registry_v1_all12.md`
- 盘型级指标汇总：`docs/llm_vs_nollm_metrics_all12_summary.csv` / `docs/reports/llm_vs_nollm_metrics_all12_summary.md`

## 8. 下一步建议（按优先级）
1. 维持“盘型级策略 + fallback”上线原则：PASS 盘型启用，FALLBACK 盘型继续 no-LLM。
2. MC1 后续默认走 compact14，不再默认跑 full70。
3. 对 HMS 仅做低成本增益验证：优先前置信号契约优化，不优先增加训练侧复杂度。
4. 将 `kept=0` 组合在 phase3 直接标记 `degenerate_skip`，减少无效计算。

## 9. v1 收敛补充（2026-03-05）
- Policy lock 单一事实源：`docs/reports/cross_model_policy_registry_v1_all12.md`。
- 执行手册（GPU/CPU/断点续跑）：`docs/guides/cross_model_execution_checklist_v1_final.md`。
- 早期 5-model / batch7 / MC1 中间网格细表未作为公开仓库长期保留物。
