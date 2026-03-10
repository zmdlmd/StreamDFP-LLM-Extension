# Framework v1 Metric Contract

## Scope

- Time window: `2014-09-01 ~ 2014-11-09`
- Primary metric source: `parse.py` output CSV (`Local mean`)
- Comparison mode: per model (`LLM vs no-LLM`)

## Hard acceptance guard

For each evaluable model (`llm_valid=true` and `nollm_valid=true`):

1. `Recall_c1(LLM) >= Recall_c1(noLLM)`
2. `ACC(LLM) >= ACC(noLLM) - 1.0pp`

If either fails:
- mark `status=FALLBACK`
- `action=nollm`

If metrics are invalid (NaN / no positives):
- mark `status=N/A`
- `action=llm_invalid:*`

## Secondary quality constraints (extract stage)

- JSON parse success rate >= 98%
- `mapped_event_ratio >= 0.90`
- Report `unknown_ratio / rule_match_ratio / event_density / q_score quantiles`

## Reporting outputs

- Baseline lock: `docs/framework_v1_baseline_lock.csv`
- Trial report: `docs/llm_robust_eval_report_v3.csv`, `docs/llm_robust_eval_report_v3.md`
- Policy registry: `docs/cross_model_policy_registry_v1.md`
