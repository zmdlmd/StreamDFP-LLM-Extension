# MC1 Legacy Reproduction Note (2026-03-14)

## Summary

This note records a legacy-path reproduction for `mc1_pilot20k`, targeting the historical result:

- best params: `compact14, q=0.00, sev=0.0, rule=0`
- `Recall = 100.0`
- baseline `Recall = 97.7704`
- `Delta Recall = +2.2296`

The goal was to verify whether the historical `mc1` uplift could still be reproduced with the current repository state.

## Key Finding

The historical `mc1` result **can be reproduced**, but only under the **legacy phase3 interpretation** where:

- `build_cache_variant.py` writes the full variant cache even when `kept=0`
- downstream `loader/simulate` still runs
- the run is **not** short-circuited by the current `degenerate_skip` guard

Under the current strict phase3 script behavior, the same `mc1` cache is skipped because all combinations are treated as degenerate.

## Input Cache Status

The currently available `mc1` caches all show the same pattern:

- `root_cause_pred = unknown` for all `20000` rows
- `llm_q_score = 0`
- `confidence = 0`
- `risk_hint = 0`
- `llm_rule_top_cause = media`
- `llm_rule_match = False`

Checked files:

- [cache_mc1_zs_structured_v2_pilot20k.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k.jsonl)
- [cache_mc1_zs_structured_v2_pilot20k_qwen35.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_qwen35.jsonl)
- [cache_mc1_zs_structured_v2_pilot20k_qwen35plus_api.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/cache_mc1_zs_structured_v2_pilot20k_qwen35plus_api.jsonl)

So the historical uplift is **not evidence that current `mc1` phase2 contains effective semantic labels**.

## Why Historical Phase3 Still Produced Results

The critical behavior is in [build_cache_variant.py](/root/autodl-tmp/StreamDFP/llm/scripts/build_cache_variant.py):

- rows with `keep=False` are still written to the output cache
- `z_llm_*` fields are zeroed
- the variant cache remains structurally valid for downstream loader/simulate

Current `mc1` phase3 script behavior adds a later guard:

- if `kept=0`, mark `degenerate_skip`
- do not continue to loader/simulate

That is why:

- historical `mc1` CSVs exist
- current strict `phase3` for `mc1` produces only `degenerate_skip`

## Legacy Reproduction Run

Variant cache built from the historical pilot20k cache:

- [mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro.jsonl](/root/autodl-tmp/StreamDFP/llm/framework_v1_mc1/phase3_variants/mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro.jsonl)
- [mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro_cache_variant.json](/root/autodl-tmp/StreamDFP/logs/framework_v1_phase3_mc1/mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro_cache_variant.json)

The metadata still shows:

- `kept = 0`
- `dropped_unknown = 20000`

But the wrapper was forced to continue in the legacy style.

Full reproduction outputs:

- result CSV: [phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2_i10.csv](/root/autodl-tmp/StreamDFP/mc1_mlp/phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2_i10.csv)
- loader time: [time_loader_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2.txt](/root/autodl-tmp/StreamDFP/logs/framework_v1_phase3_mc1/time_loader_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2.txt)
- simulate time: [time_phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2_i10.txt](/root/autodl-tmp/StreamDFP/mc1_mlp/time_phase3_mc1_compact14_q00_s00_r0_zs_structured_v2_pilot20k_legacyrepro2_i10.txt)

## Reproduced Metrics

From the reproduced CSV:

- `Recall = 100.0`
- `ACC = 99.548854005`

These match the historical merged report entry for `mc1_pilot20k`.

## Conclusion

The historical `mc1 +2.2296` line is reproducible, but only as a **legacy pipeline result**.

It should be interpreted carefully:

- it reflects a historical evaluation path where `kept=0` variants still flowed into downstream training/simulation
- it does **not** demonstrate that current `mc1` phase2 extraction is producing useful non-unknown semantic labels
- therefore, the historical `mc1_pilot20k = llm_enabled` status should be treated as a **legacy-compatible result**, not as evidence that current strict phase3 logic is wrong

