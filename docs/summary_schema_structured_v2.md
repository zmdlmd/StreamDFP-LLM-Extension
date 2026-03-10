# Summary Schema `structured_v2`

`window_to_text.py --summary_schema structured_v2` 输出固定块，顺序不可变：

1. `WINDOW: <start>~<end> (<n>d) disk=<masked_id>`
2. `DATA_QUALITY: valid_days=<int> missing_ratio=<0~1> active_features=<a>/<b> known_features=<int>`
3. `RULE_SCORE: media=... interface=... temperature=... power=... workload=...`
4. `RULE_TOP2: <cause1>=... <cause2>=... margin=...`
5. `ALLOWED_EVENT_FEATURES: SMART_x ...` 或 `none`
6. `ANOMALY_TABLE:`
   - `- feat=...|src=...|mode=...|dir=...|baseline=...|current=...|delta_pct=...|abnormal_ratio=...|persistence=...|slope3=...|slope14=...|burst_ratio=...|severity=...|group=...`
   - 无异常时：`- none`
7. `CAUSE_EVIDENCE: ...`
8. `RULE_PRED: <root_cause>`

## CLI

```bash
python llm/window_to_text.py \
  ... \
  --summary_schema structured_v2 \
  --summary_anomaly_top_k 8 \
  --summary_emit_legacy_text
```

- `summary_emit_legacy_text=false`（默认）：仅输出 v2 固定块
- `summary_emit_legacy_text=true`：追加旧版辅助行（兼容/调试）

## Validator

```bash
python llm/scripts/validate_summary_schema.py \
  --window_text_path llm/window_text_xxx.jsonl \
  --max_rows 32
```
