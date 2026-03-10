# FS Spot-check (2 Models) - 2026-03-05

Scope: reuse existing FS/ZS evidence for `hi7` and `st31500541as` to validate ZS-default policy without full FS rerun.

| model_key | zs_status | zs_delta_recall | zs_delta_acc | fs_status | fs_delta_recall | fs_delta_acc | decision |
|---|---|---:|---:|---|---:|---:|---|
| hi7 | PASS | +2.8571 | -0.0490 | FALLBACK | -1.4286 | +0.3512 | keep_zs_default |
| st31500541as | PASS | +11.5278 | +0.1030 | FALLBACK | -1.6667 | +0.0552 | keep_zs_default |

Conclusion:
- Keep `zs` as default profile for rollout.
- No per-model FS exception is needed for these two spot-check models.

Evidence: `docs/llm_robust_eval_report_v3_fs_vs_zs.csv`.
