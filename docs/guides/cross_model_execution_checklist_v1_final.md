# Cross-model Execution Checklist v1 (Final)

Lock date: 2026-03-05
Default strategy: `ZS + per-model fallback` (policy source: `docs/reports/cross_model_policy_registry_v1_all12.md`)

## 0) Preflight

```bash
cd /root/autodl-tmp/StreamDFP
nvidia-smi
df -h /root/autodl-tmp
```

Stop if:
- GPU unavailable (Phase2),
- free disk < 20G.

## 1) One-pass execution order

1. Phase2 ZS extraction (**GPU**)
2. Phase3 grid/eval (**CPU**)
3. Merge report + policy lock (**CPU**)
4. Optional FS spot-check on 2 models (`hi7`, `st31500541as`) (**GPU+CPU**)
5. Final sync (`v4 merged report` + `policy registry`)

### Full-data mode (not pilot20k)

Use a non-pilot run tag and disable max-window truncation:

```bash
cd /root/autodl-tmp/StreamDFP

# Phase2 full extraction (ZS default)
PHASE=2 PHASE2_MODELS=all PHASE2_EXTRACT_COMBOS=zs_structured_v2 RUN_TAG=full MAX_WINDOWS=0 \
  bash scripts/run_cross_model_llm_framework_v1.sh

# Phase3 full grid (M1/M2)
PHASE3_RUN_TAG=full PHASE3_EXTRACT_MODE=zs PHASE3_PROMPT_PROFILE=structured_v2 PHASE3_MODELS=m2 \
  bash scripts/run_framework_v1_phase3_grid.sh

# Optional batch7 full grid
PHASE3_RUN_TAG=full PHASE3_EXTRACT_MODE=zs PHASE3_PROMPT_PROFILE=structured_v2 \
  bash scripts/run_framework_v1_phase3_grid_batch7.sh
```

## 2) Phase dependencies

- **GPU required**
  - `window_to_text.py` (if rebuilding Phase2 inputs)
  - `llm_offline_extract.py` (vLLM extraction)
- **CPU required**
  - `build_cache_variant.py`
  - `pyloader/run.py`
  - `simulate` / `parse.py`
  - report merge/summary scripts

## 3) Resume-safe execution

- Use `screen` for long jobs:
  ```bash
  screen -S framework_v1
  ```
- Run scripts with checkpointed outputs (`existing` rows skipped automatically).
- Phase3 now supports `degenerate_skip`:
  - if cache-variant meta shows `kept=0`, combo is recorded as `degenerate_skip`;
  - loader/simulate is skipped to save CPU time.

## 4) Acceptance and lock

Per-model guard:
- `Recall(LLM) >= Recall(noLLM)`
- `ACC(LLM) >= ACC(noLLM) - 1.0pp`

Lock rule:
- PASS -> `llm_enabled`
- FALLBACK -> `nollm`

Final evidence files:
- `docs/llm_robust_eval_report_v4_merged_all12.csv`
- `docs/reports/llm_robust_eval_report_v4_merged_all12.md`
- `docs/reports/cross_model_policy_registry_v1_all12.md`
