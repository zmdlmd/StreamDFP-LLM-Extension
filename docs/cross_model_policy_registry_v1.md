# Cross-model Policy Registry v1 (Locked)

Lock date: 2026-02-28

This is the frozen default policy for framework v1 after FS/ZS comparison.
Default runtime profile is `ZS`, with per-model fallback to `no-LLM`.

| model_key | default_profile | enabled | cache_variant | q_gate | sev_sum_gate | require_rule_match | fallback | fs_vs_zs_decision |
|---|---|---:|---|---:|---:|---:|---|---|
| st3000dm001 | zs | true | compact9 | 0.55 | 0.8 | true | nollm | keep `zs` (FS pass but no recall gain) |
| hms5c4040ble640 | zs | false | compact14 | 0.00 | 0.0 | false | nollm | fallback (FS/ZS both fail; dense-window no-LLM recall saturated, LLM redundant) |
| hi7 | zs | true | compact14 | 0.00 | 0.8 | false | nollm | keep `zs` (FS falls back) |
| hds723030ala640 | zs | true | full70 | 0.00 | 0.0 | false | nollm | keep `zs` (FS no gain, ACC worse) |
| st31500541as | zs | true | full70 | 0.00 | 0.0 | false | nollm | keep `zs` (FS falls back) |

Evidence:
- `docs/llm_robust_eval_report_v3.csv`
- `docs/llm_robust_eval_report_v3_fs.csv`
- `docs/llm_robust_eval_report_v3_fs_vs_zs.csv`
- `docs/framework_v1_quality_hms5c4040ble640/hms_hd_nollm_baseline_summary.md`

Compatibility note:
- Runtime gate fields consumed by `run.py` remain unchanged:
  `min_q_score`, `min_rule_match`, `min_mapped_event_ratio`, `keep_dims`, `llm_scale_alpha`.
