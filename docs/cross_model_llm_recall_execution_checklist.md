# 跨盘型 LLM 增强 Recall 执行清单（已同步 v1 最终版）

同步日期：2026-02-28
默认策略：`ZS + 按盘型回退`（`hms5c4040ble640 -> no-LLM`）

本文件已与以下最终文档保持一致：
- `docs/cross_model_policy_registry_v1.md`
- `docs/cross_model_llm_framework_v1_final.md`
- `docs/cross_model_execution_checklist_v1_final.md`

## 0) 预检

```bash
cd <repo_root>
nvidia-smi
df -h .
```

停止条件：
- Phase2 需要 GPU，不可用则暂停；
- 磁盘可用空间 `< 20G` 先清理。

## 1) Phase2（GPU）：LLM 抽取

目标：生成/刷新各盘型 `llm_cache_*.jsonl`。
默认抽取档：`ZS`（`FS` 仅用于离线对比验证）。

## 2) Phase3（CPU）：pre-ARFF 网格 + 训练评估

目标：在不改训练接口前提下，选择每盘型最优 gate/compact 配置。
验收硬约束（逐盘型）：
- `Recall_c1(LLM) >= Recall_c1(noLLM)`
- `ACC(LLM) >= ACC(noLLM) - 1.0pp`

关键产物：
- `docs/prearff_grid_*.csv/.md`
- `docs/llm_robust_eval_report_v3.csv`
- `docs/llm_robust_eval_report_v3_fs.csv`
- `docs/llm_robust_eval_report_v3_fs_vs_zs.csv`

## 3) 策略落盘

根据通过/回退结果更新：
- `docs/cross_model_policy_registry_v1.md`
- `docs/cross_model_llm_framework_v1_final.md`

规则：
- PASS：启用该盘型 LLM（当前默认用 ZS）
- FAIL：该盘型 fallback 到 no-LLM

## 4) 推荐执行顺序

1. Phase2 ZS 抽取（GPU）
2. Phase3 评估（CPU）
3. 可选：Phase2/3 FS 验证
4. FS vs ZS 对比
5. 更新最终策略与总报告
