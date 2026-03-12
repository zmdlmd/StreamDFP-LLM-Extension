# st31500541as 退化样本定位

日期：2026-03-10

关联结论文档：

- [st31500541as_ab_same_subset_20260310.md](st31500541as_ab_same_subset_20260310.md)

## 分析口径

对比两份同子集 `pilot20k` cache：

- 旧快照：
  `llm/framework_v1/cache_st31500541as_zs_structured_v2_pilot20k_pre_contractfix_backup.jsonl`
- Qwen3.5：
  `llm/framework_v1/cache_st31500541as_zs_structured_v2_pilot20k_qwen35.jsonl`

匹配键：

- `disk_id`
- `window_end_time`

共匹配 `20000` 个窗口。

## 核心现象

两份 cache 之间共有 `3433` 个窗口的 `root_cause_pred` 发生变化，其中主导模式不是“换成别的根因”，而是大规模塌回 `unknown`。

主要转移如下：

- `temperature -> unknown`: `3212`
- `media -> unknown`: `18`
- `temperature -> media`: `87`

## 关键判断

### 1. 不是 parser 失败

在三类主要转移里，`parse_source` 全部都是 `direct`。

这说明：

- 当前退化不是由输出解析失败直接造成
- 而是模型本身就生成了更弱的根因判断

### 2. 不是规则证据消失

对 `temperature -> unknown` 的 `3212` 个窗口：

- 旧快照 `llm_rule_top_cause = temperature`：`3212/3212`
- Qwen3.5 `llm_rule_top_cause = temperature`：`3156/3212`
- 旧快照 `llm_rule_match = True`：`3212/3212`
- Qwen3.5 `llm_rule_match = False`：`3212/3212`

对 `media -> unknown` 的 `18` 个窗口：

- 旧快照 `llm_rule_top_cause = media`：`18/18`
- Qwen3.5 `llm_rule_top_cause = media`：`14/18`
- 旧快照 `llm_rule_match = True`：`18/18`
- Qwen3.5 `llm_rule_match = False`：`18/18`

这说明很多窗口里，规则侧证据仍然在，但 `Qwen3.5` 没有把它转成一致的根因标签。

### 3. 置信度和风险提示明显塌缩

`temperature -> unknown`：

- 旧快照平均 `confidence = 0.9625`
- Qwen3.5 平均 `confidence = 0.0353`
- 旧快照平均 `risk_hint = 0.9301`
- Qwen3.5 平均 `risk_hint = 0.0574`

`media -> unknown`：

- 旧快照平均 `confidence = 0.9267`
- Qwen3.5 平均 `confidence = 0.3594`
- 旧快照平均 `risk_hint = 0.8172`
- Qwen3.5 平均 `risk_hint = 0.3383`

这与 Phase3 中有效 LLM 窗口数大幅下降是一致的。

## 代表样本

### 样本 1：温度证据很强，但 Qwen3.5 直接回到 unknown

窗口：

- `disk_id = 9XW01YFW`
- `window_end_time = 2014-10-09`

窗口摘要来自：

- `llm/framework_v1/window_text_st31500541as_pilot20k.jsonl`

规则证据：

- `RULE_TOP2: temperature=0.135 media=0.000`
- `SMART_194 severity = 0.86`
- `CAUSE_EVIDENCE: temperature=+SMART_194(0.86)`

旧快照：

- `root_cause_pred = temperature`
- `confidence = 1.0`
- `risk_hint = 1.0`
- `llm_rule_match = True`

Qwen3.5：

- `root_cause_pred = unknown`
- `confidence = 0.0`
- `risk_hint = 0.0`
- `llm_rule_match = False`

### 样本 2：同类温度窗口重复出现同样塌缩

窗口：

- `disk_id = 9XW01T3V`
- `window_end_time = 2014-10-16`

规则证据：

- `RULE_TOP2: temperature=0.135 media=0.000`
- `SMART_194 severity = 0.86`
- `CAUSE_EVIDENCE: temperature=+SMART_194(0.86)`

旧快照：

- `root_cause_pred = temperature`
- `confidence = 1.0`
- `risk_hint = 1.0`

Qwen3.5：

- `root_cause_pred = unknown`
- `confidence = 0.0`
- `risk_hint = 0.0`

这不是单点异常，而是大批温度型窗口的重复模式。

### 样本 3：媒体证据明确，但 Qwen3.5 仍打成 unknown

窗口：

- `disk_id = 5XW03BSD`
- `window_end_time = 2014-10-21`

规则证据：

- `RULE_TOP2: media=0.514 temperature=0.035`
- `SMART_5 severity = 0.64`
- `CAUSE_EVIDENCE: media=+SMART_5(0.64)`
- `RULE_PRED: media`

旧快照：

- `root_cause_pred = media`
- `confidence = 0.9`
- `risk_hint = 0.7`
- `label_noise_risk = 0.1`
- `llm_rule_match = True`

Qwen3.5：

- `root_cause_pred = unknown`
- `confidence = 0.51`
- `risk_hint = 0.51`
- `label_noise_risk = 0.4`
- `llm_rule_match = False`

### 样本 4：有混合证据时，Qwen3.5 更容易改判为 media

窗口：

- `disk_id = 5XW004Q0`
- `window_end_time = 2014-10-21`

规则证据：

- `RULE_TOP2: media=0.804 temperature=0.105`
- `SMART_5 severity = 1.00`
- `SMART_194 severity = 0.67`

旧快照：

- `root_cause_pred = temperature`
- `confidence = 0.95`
- `risk_hint = 0.92`
- `llm_rule_top_cause = temperature`

Qwen3.5：

- `root_cause_pred = media`
- `confidence = 0.8`
- `risk_hint = 0.8`
- `llm_rule_top_cause = media`

这一类不是完全塌到 `unknown`，而是在混合证据窗口里更倾向 `media`。

## 结论

`st31500541as` 的退化模式很明确：

1. 主损失来自大量 `temperature` 窗口被 Qwen3.5 打回 `unknown`
2. 少量 `media` 窗口也出现同样问题
3. 不是 parser 崩溃，而是模型输出本身变弱
4. 规则侧证据在大多数退化窗口中依然存在，因此更像是模型对该盘型温度/媒体线索的服从性下降

## 后续建议

- 优先抽查 `temperature -> unknown` 的窗口原始 LLM 响应，确认是：
  - 明确输出了 `unknown`
  - 还是输出文本变保守、导致后续映射未命中
- 针对 `st31500541as` 单独测试：
  - 提示词中加强 `SMART_194` 温度证据解释
  - 对 `temperature` 根因做更强的规则辅助或映射兜底
