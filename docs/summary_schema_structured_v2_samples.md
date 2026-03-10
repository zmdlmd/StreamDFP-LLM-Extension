# structured_v2 Sample

```text
WINDOW: 2014-10-10~2014-11-09 (30d) disk=AAANAAAAAA
DATA_QUALITY: valid_days=30 missing_ratio=0.03 active_features=5/34 known_features=18
RULE_SCORE: media=0.912 interface=0.231 temperature=0.044 power=0.102 workload=0.019
RULE_TOP2: media=0.912 interface=0.231 margin=0.681
ALLOWED_EVENT_FEATURES: SMART_5 SMART_197 SMART_198 SMART_199
ANOMALY_TABLE:
- feat=SMART_5|src=raw|mode=level|dir=high_bad|baseline=2.00|current=12.00|delta_pct=+500.0|abnormal_ratio=0.73|persistence=0.80|slope3=+0.211|slope14=+0.094|burst_ratio=1.10|severity=0.95|group=media
- feat=SMART_197|src=raw|mode=level|dir=high_bad|baseline=0.00|current=7.00|delta_pct=+700.0|abnormal_ratio=0.63|persistence=0.70|slope3=+0.140|slope14=+0.081|burst_ratio=1.05|severity=0.87|group=media
CAUSE_EVIDENCE: media=+SMART_5(0.95),+SMART_197(0.87),-SMART_9(0.03) interface=+SMART_199(0.22) temperature=none power=none workload=none
RULE_PRED: media
```

LLM 期望输出（短 JSON）：

```json
{
  "root_cause": "media",
  "risk_hint": 0.91,
  "hardness": 0.74,
  "confidence": 0.88,
  "events": [
    {"feature": "SMART_5", "type": "monotonic_increase", "severity": 0.95},
    {"feature": "SMART_197", "type": "monotonic_increase", "severity": 0.87}
  ]
}
```
