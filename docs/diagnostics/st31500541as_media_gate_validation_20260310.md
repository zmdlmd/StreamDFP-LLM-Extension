## st31500541as media gate validation (2026-03-10)

Scope:
- Model: `Qwen3.5-4B`
- Task slice: `st31500541as`
- Source set: all `18` windows where historical old cache was `media` and `pilot20k_qwen35` cache became `unknown`
- Probe file: `docs/st31500541as_raw_probe_qwen35_media_unknown_all18_20260310.jsonl`

Raw-output result:
- `13 / 18` raw outputs are `media`
- `4 / 18` raw outputs are `unknown`
- `1 / 18` raw output is `workload`

This means the `media -> unknown` regression is only partially caused by model abstention. A larger part is caused by Phase2 normalization / gating.

Replayed normalization with the same settings used by Phase2:
- `rule_blend_mode = three_stage`
- `rule_score_gate = 0.80`
- `event_type_policy = strict`
- `enforce_event_feature_whitelist = true`

Soft-gate sweep:

| rule_score_soft_gate | media | unknown |
|---|---:|---:|
| 0.55 | 0 | 18 |
| 0.52 | 2 | 16 |
| 0.50 | 6 | 12 |
| 0.48 | 6 | 12 |
| 0.45 | 11 | 7 |
| 0.40 | 13 | 5 |

Interpretation:
- With the current `soft_gate = 0.55`, all `18` sampled windows stay `unknown`.
- Lowering to `0.50` already recovers `6` windows to `media`.
- Lowering to `0.45` recovers `11` windows.
- Lowering to `0.40` recovers all `13` windows whose raw model output is already `media`; the remaining `5` windows stay `unknown`, matching the `4` raw-unknown and `1` raw-workload cases.

Representative recovered windows at `soft_gate = 0.50`:
- `5XW03BSD / 2014-10-21` (`top_score = 0.514`)
- `5XW03BSD / 2014-10-22` (`top_score = 0.512`)
- `6XW07HKR / 2014-10-17` (`top_score = 0.547`)
- `9XW032GZ / 2014-09-20` (`top_score = 0.512`)
- `9XW032GZ / 2014-09-22` (`top_score = 0.505`)
- `9XW04MBA / 2014-10-04` (`top_score = 0.528`)

Conclusion:
- The earlier diagnosis is validated.
- For `st31500541as`, the `media -> unknown` regression is materially driven by the current `three_stage` soft gate being too strict for the Qwen3.5 output distribution.
- But this is not the whole story: some windows are still raw `unknown` or even `workload`, so gate relaxation can only recover part of the total regression.
