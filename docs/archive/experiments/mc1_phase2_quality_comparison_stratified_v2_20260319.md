# MC1 Phase2 Quality Comparison (Stratified V2)

This note compares the `phase2` extraction quality of three models on the corrected `mc1` input set:

- [window_text_mc1_pilot20k_stratified_v2.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/window_text_mc1_pilot20k_stratified_v2.jsonl)
- [reference_mc1_pilot20k_stratified_v2.json](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/reference_mc1_pilot20k_stratified_v2.json)

The comparison table is also available as CSV:

- [mc1_phase2_quality_comparison_stratified_v2_20260319.csv](/root/autodl-tmp/StreamDFP/docs/tables/mc1_phase2_quality_comparison_stratified_v2_20260319.csv)

## Summary Table

| Model | Total | `unknown` | Non-`unknown` | `mapped_event_ratio` | `rule_match_ratio` | Avg `confidence` | Avg `risk_hint` | Avg `llm_q_score` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Qwen3.5-4B (tp2+eager)` | 20000 | `92.445%` | `7.555%` | `77.460%` | `7.550%` | `0.2247` | `0.2105` | `0.2470` |
| `Qwen3.5-Plus` | 20000 | `92.325%` | `7.675%` | `90.195%` | `7.675%` | `0.3727` | `0.2779` | `0.2974` |
| `Qwen3-4B-Instruct-2507` | 20000 | `91.555%` | `8.445%` | `90.775%` | `8.445%` | `0.8547` | `0.7133` | `0.4503` |

## Root Cause Distribution

- `Qwen3.5-4B (tp2+eager)`: `unknown=18489`, `temperature=1218`, `media=231`, `workload=47`, `power=13`, `interface=2`
- `Qwen3.5-Plus`: `unknown=18465`, `temperature=1238`, `media=234`, `workload=47`, `power=14`, `interface=2`
- `Qwen3-4B-Instruct-2507`: `unknown=18311`, `temperature=1315`, `media=270`, `workload=87`, `power=15`, `interface=2`

## Interpretation

- The corrected `mc1 stratified_v2` input is no longer degenerate. All three models now produce non-`unknown` outputs, unlike the earlier broken sequential sample.
- `Qwen3-4B-Instruct-2507` is the strongest `phase2` extractor on this input set.
  It has the lowest `unknown` ratio, the highest non-`unknown` ratio, and clearly stronger `confidence`, `risk_hint`, and `llm_q_score`.
- `Qwen3.5-Plus` is second-best. Its extraction coverage is close to `Qwen3-4B-Instruct-2507`, but its score calibration is materially weaker.
- `Qwen3.5-4B` can be forced to run with `TP=2 + eager`, but it is still the weakest of the three.
  The largest gap is `mapped_event_ratio` (`77.46%` vs `90%+` for the other two models).

## Sources

- `Qwen3.5-4B` cache: [cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35_tp2eager.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35_tp2eager.jsonl)
- `Qwen3.5-Plus` cache: [cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35plus_api.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen35plus_api.jsonl)
- `Qwen3-4B-Instruct-2507` cache: [cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen3instruct2507.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_stratified_v2_qwen3instruct2507.jsonl)
- Existing `Qwen3.5-Plus` quality CSV: [extract_quality_mc1_pilot20k_stratified_v2_qwen35plus_api_v1.csv](/root/autodl-tmp/StreamDFP/docs/extract_quality_mc1_pilot20k_stratified_v2_qwen35plus_api_v1.csv)
