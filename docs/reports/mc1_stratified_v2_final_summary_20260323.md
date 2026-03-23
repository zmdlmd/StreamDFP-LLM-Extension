# MC1 Stratified V2 最终结果总结（2026-03-23）

## 1. 结论摘要

`mc1` 之前跑不出来，根因主要是旧版 `pilot20k` 输入采用了错误的 `sequential` 顺序采样，导致 `Phase1` 生成的窗口几乎没有有效事件证据。  
本轮切换到新的 `pilot20k_stratified_v2` 输入后，三种模型在当前严格 `phase3` 口径下都已经可以稳定得到有效结果，并且最优组合完全一致：

- 最优组合：`compact14, q=0.00, sev=0.0, rule=0`
- `Recall = 100.0000`
- `ACC = 99.5489`
- 相对 no-LLM baseline：
  - `ΔRecall = +2.2296`
  - `ΔACC = +0.0532`

也就是说，修正输入后，`mc1` 不再是“当前严格口径不可用”的条目，而是已经恢复为可启用 LLM 的条目。

## 2. 输入修复

本轮使用的新输入为：

- [window_text_mc1_pilot20k_stratified_v2.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/window_text_mc1_pilot20k_stratified_v2.jsonl)
- [reference_mc1_pilot20k_stratified_v2.json](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/reference_mc1_pilot20k_stratified_v2.json)
- [reference_mc1_pilot20k_stratified_v2_quality.json](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/reference_mc1_pilot20k_stratified_v2_quality.json)

修复要点：

- `sample_mode` 从旧版 `sequential` 改为 `stratified_day_disk`
- `window_end_time` 覆盖 `2018-02-01 ~ 2018-03-13`
- 避开最早一批缺少历史上下文的窗口
- 同时重建 `reference_pool`

旧版失败原因详见：

- [mc1_抽取失败原因与修复进展_20260320.md](/root/autodl-tmp/StreamDFP/docs/reports/mc1_抽取失败原因与修复进展_20260320.md)

## 3. Phase2 质量对比

`Phase2` 质量对比见：

- [mc1_phase2_quality_comparison_stratified_v2_20260319.md](/root/autodl-tmp/StreamDFP/docs/reports/mc1_phase2_quality_comparison_stratified_v2_20260319.md)
- [mc1_phase2_quality_comparison_stratified_v2_20260319.csv](/root/autodl-tmp/StreamDFP/docs/tables/mc1_phase2_quality_comparison_stratified_v2_20260319.csv)

关键指标如下：

| 模型 | `unknown`占比 | 非`unknown`占比 | `mapped_event_ratio` | Avg `confidence` | Avg `risk_hint` | Avg `llm_q_score` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Qwen3.5-4B (tp2+eager)` | `92.4450%` | `7.5550%` | `77.4600%` | `0.2247` | `0.2105` | `0.2470` |
| `Qwen3.5-Plus` | `92.3250%` | `7.6750%` | `90.1950%` | `0.3727` | `0.2779` | `0.2974` |
| `Qwen3-4B-Instruct-2507` | `91.5550%` | `8.4450%` | `90.7750%` | `0.8547` | `0.7133` | `0.4503` |

结论：

- `Qwen3-4B-Instruct-2507` 的 `Phase2` 抽取质量最好
- `Qwen3.5-Plus` 次之
- `Qwen3.5-4B` 最弱，而且需要双卡 `TP=2 + eager` 才能稳定跑完

## 4. Phase3 最终对比

baseline：

- 文件：[example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv](/root/autodl-tmp/StreamDFP/mc1_mlp/example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv)
- `Recall = 97.7704`
- `ACC = 99.4956`

三模型最优结果：

| 模型 | 最优配置 | Recall | ACC | `ΔRecall` | `ΔACC` |
| --- | --- | ---: | ---: | ---: | ---: |
| `Qwen3.5-4B (tp2+eager)` | `compact14, q=0.00, sev=0.0, rule=0` | `100.0000` | `99.5489` | `+2.2296` | `+0.0532` |
| `Qwen3.5-Plus` | `compact14, q=0.00, sev=0.0, rule=0` | `100.0000` | `99.5489` | `+2.2296` | `+0.0532` |
| `Qwen3-4B-Instruct-2507` | `compact14, q=0.00, sev=0.0, rule=0` | `100.0000` | `99.5489` | `+2.2296` | `+0.0532` |

对应结果文件：

- `Qwen3.5-4B`：
  [phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen35tp2eager_i10.csv](/root/autodl-tmp/StreamDFP/mc1_mlp/phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen35tp2eager_i10.csv)
- `Qwen3.5-Plus`：
  [phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen35plusapi_i10.csv](/root/autodl-tmp/StreamDFP/mc1_mlp/phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen35plusapi_i10.csv)
- `Qwen3-Instruct`：
  [phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen3instruct2507_i10.csv](/root/autodl-tmp/StreamDFP/mc1_mlp/phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_stratified_v2_qwen3instruct2507_i10.csv)

## 5. 三模型比较

有两个层面的结论：

### 5.1 如果看最终最佳指标

三者没有区别。  
在新的 `mc1 stratified_v2` 输入上，三模型都能达到完全相同的最优点。

### 5.2 如果看工程稳定性和抽取质量

三者差异仍然明显：

- `Qwen3-4B-Instruct-2507`
  - `Phase2` 最强
  - 本地运行稳定
  - 当前是最强本地基线
- `Qwen3.5-Plus`
  - `Phase2` 次强
  - `Phase3` 24 组全部正常 `ok`
  - 是最稳的 API 方案
- `Qwen3.5-4B`
  - `Phase2` 最弱
  - 需要双 `5090`、`TP=2 + eager`
  - 虽然最终最好结果能追平，但工程成本最高

## 6. 和 legacy 结论的关系

历史上 `mc1` 有一条 `+2.2296` 的记录。  
这次新结果的重要意义在于：

- 以前只能通过 legacy 旧口径解释这条结果
- 现在在修正后的 `stratified_v2` 输入上，三模型已经能在当前严格 `phase3` 口径下复现同样的 `+2.2296`

所以现在应当把 `mc1` 的结论从：

- “legacy 才能复现”

更新为：

- “旧输入有问题；修正输入后，当前严格口径也能稳定得到正增益”

legacy 诊断文档仍保留，主要用于解释旧失败链路：

- [mc1_legacy_repro_20260314.md](/root/autodl-tmp/StreamDFP/docs/diagnostics/mc1_legacy_repro_20260314.md)

## 7. 最终建议

- 后续 `mc1` 实验应统一使用 `pilot20k_stratified_v2`
- 不再复用旧版 `window_text_mc1_pilot20k.jsonl`
- 如果优先看研究结论：
  - 三模型都可视为 `mc1` 上有效
- 如果优先看工程可用性：
  1. `Qwen3.5-Plus`
  2. `Qwen3-4B-Instruct-2507`
  3. `Qwen3.5-4B`

更具体地说：

- `Qwen3.5-Plus` 是最稳的上线候选
- `Qwen3-Instruct` 是最强的本地模型基线
- `Qwen3.5-4B` 不建议作为首选正式方案
