# Cross-model LLM Framework v1 Final Report (ZS Default)

## 1) Scope

- Models: `st3000dm001`, `hms5c4040ble640`, `hi7`, `hds723030ala640`, `st31500541as`
- Date range: `2014-09-01 ~ 2014-11-09`
- LLM backend: `Qwen3-4B-Instruct-2507 + vLLM`
- Prompt profile: `structured_v2`
- Public references:
  - `docs/cross_model_policy_registry_v1_all12.md`
  - `docs/llm_robust_eval_report_v4_merged_all12.csv`
  - `docs/llm_robust_eval_report_v4_merged_all12.md`

## 2) Acceptance rule

- Recall guard: `Recall_c1(LLM) >= Recall_c1(noLLM)`
- ACC guard: `ACC(LLM) >= ACC(noLLM) - 1.0pp`

## 3) Final per-model decision

| model_key | final_profile | final_status | fallback | rationale |
|---|---|---|---|---|
| st3000dm001 | zs | PASS | nollm | FS and ZS both pass; ZS has slightly higher recall |
| hms5c4040ble640 | zs | FALLBACK | nollm | FS and ZS both fail recall guard; dense-window no-LLM recall is saturated (LLM judged redundant) |
| hi7 | zs | PASS | nollm | ZS passes; FS falls back |
| hds723030ala640 | zs | PASS | nollm | FS and ZS both pass; FS has worse ACC margin |
| st31500541as | zs | PASS | nollm | ZS passes; FS falls back |

## 4) Locked default policy

- Default extraction profile: `ZS`
- Default runtime action: enable LLM only for PASS models
- Forced fallback model: `hms5c4040ble640`
- Registry source of truth: `docs/cross_model_policy_registry_v1_all12.md`
- HMS dense-window evidence: `docs/framework_v1_quality_hms5c4040ble640/hms_hd_nollm_baseline_summary.md`

## 5) Implementation notes

1. Training interface is unchanged (`run.py/simulate` command contracts remain the same).
2. Adaptation is handled before ARFF by cache gating/compaction strategy.
3. For reproducibility, FS remains an offline validation track, not the production default.
4. Historical intermediate FS/ZS comparison tables are intentionally not kept in the public repo; the merged all12 registry is the retained public summary.

## 6) Batch7 ZS extension (merged on 2026-03-01)

- Extended models: `hgsthms5c4040ale640`, `st31500341as`, `hitachihds5c4040ale630`, `wdcwd30efrx`, `wdcwd10eads`, `st4000dm000`, `hds5c3030ala630`
- Pilot setting: `20000` windows/model, `structured_v2`, ZS only
- Result: PASS `4/7`, FALLBACK `3/7`
- Merged all-model report (12 models): `docs/llm_robust_eval_report_v4_merged_all12.csv`
- Merged all-model policy registry: `docs/cross_model_policy_registry_v1_all12.md`
