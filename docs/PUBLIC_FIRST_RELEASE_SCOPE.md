# Public First Release Scope

This note defines a pragmatic first public release boundary for the repository. The goal is to publish enough code and documentation for others to understand and reproduce the main workflow, without pushing large generated artifacts or every internal iteration note.

## Recommended `docs/` Scope

### Keep in the first public release

- [README.md](README.md)
- [REPOSITORY_LAYOUT.md](REPOSITORY_LAYOUT.md)
- [GITHUB_UPLOAD_CHECKLIST.md](GITHUB_UPLOAD_CHECKLIST.md)
- [PUBLIC_REPRODUCIBILITY.md](PUBLIC_REPRODUCIBILITY.md)
- [cross_model_llm_framework_v1_final.md](cross_model_llm_framework_v1_final.md)
- [cross_model_execution_checklist_v1_final.md](cross_model_execution_checklist_v1_final.md)
- [framework_v1_metric_contract.md](framework_v1_metric_contract.md)
- [llm_integration.md](llm_integration.md)
- [llm_recent_experiments_master_summary_20260305.md](llm_recent_experiments_master_summary_20260305.md)
- [llm_recent_experiments_qwen35_pilot20k_summary_20260310.md](llm_recent_experiments_qwen35_pilot20k_summary_20260310.md)
- [qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md](qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md)
- [summary_schema_structured_v2.md](summary_schema_structured_v2.md)
- [summary_schema_structured_v2_samples.md](summary_schema_structured_v2_samples.md)

### Keep if you want stronger experiment traceability

- `prearff_grid_*.csv|md`
- `llm_robust_eval_report*.csv|md`
- `llm_vs_nollm_metrics_*.csv|md`
- `framework_v1_baseline_lock.csv`
- `cross_model_policy_registry_v1.md`
- `cross_model_policy_registry_v1_all12.md`

### Hold back from the first public release

- round-by-round HMS tuning logs
- one-off management notes
- raw probe JSONL files
- internal path-heavy debug runbooks that still encode machine-local layout

Examples:

- `hms_microgrid_round*.md`
- `hms_policy_grid_round*.md`
- `st31500541as_raw_probe_*.jsonl`
- `fallback_freeze_review_v1_20260305.md`

## Recommended `llm/` Scope

### Keep in the first public release

Core code:

- `parse.py`
- `parse_reg.py`
- `pyloader/run.py`
- `pyloader/run_hi7_loader.sh`
- `pyloader/run_hi7_reg_loader.sh`
- `pyloader/run_mc1_loader.sh`
- `run_hi7.sh`
- `run_hi7_reg.sh`
- `run_hi640_transfer.sh`
- `run_hi7_rnn.sh`
- `run_mc1_mlp.sh`
- `pom.xml`
- `simulate/src/`
- `simulate/pom.xml`
- `moa/src/`
- `moa/pom.xml`
- `llm/__init__.py`
- `llm/window_to_text.py`
- `llm/llm_offline_extract.py`
- `llm/feature_mapping.py`
- `llm/eval_alignment.py`
- `llm/tests/`
- `llm/scripts/`

Core config:

- `llm/event_mapping_hi7.yaml`
- `llm/event_mapping_mc1.yaml`
- `llm/event_mappings/models_7_20140901_20141109/`
- `llm/event_mappings/batch7_20140901_20141109/`
- `llm/rules/default.yaml`
- `llm/rules/mc1.yaml`
- `llm/rules/profiles/`
- `llm/calibration/model_policy.yaml`
- `llm/requirements_vllm.txt`

### Optional to keep

- `llm/contracts/feature_contract_*.json`

These are generated summaries, not core source. They can help readers inspect the feature-contract outcome, but they are not required for rerunning the pipeline because the repository already contains the contract-building scripts.

### Do not include in the first public release

- `llm/framework_v1/`
- `llm/framework_v1_mc1/`
- `llm/window_text_*.jsonl`
- `llm/reference_examples_*.json`
- `llm/reference_quality_*.json`
- `llm/*eval_report*.json`
- temporary probes and startup checks

These are generated runtime artifacts and are already ignored by the root `.gitignore`.

## Suggested First Public `git add`

```bash
git add \
  README.md .gitignore LICENSE \
  environment-public.yml requirements-public.txt requirements-llm-public.txt \
  pom.xml parse.py parse_reg.py run_hi7.sh run_hi7_reg.sh run_hi640_transfer.sh run_hi7_rnn.sh run_mc1_mlp.sh \
  configs/public_repro.env.example \
  docs/README.md docs/REPOSITORY_LAYOUT.md docs/GITHUB_UPLOAD_CHECKLIST.md \
  docs/PUBLIC_REPRODUCIBILITY.md docs/PUBLIC_FIRST_RELEASE_SCOPE.md \
  docs/cross_model_llm_framework_v1_final.md docs/cross_model_execution_checklist_v1_final.md \
  docs/framework_v1_metric_contract.md docs/llm_integration.md \
  docs/llm_recent_experiments_master_summary_20260305.md \
  docs/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md \
  docs/qwen3_4b_vs_qwen35_4b_hdd_comparison_20260310.md \
  docs/summary_schema_structured_v2.md docs/summary_schema_structured_v2_samples.md \
  simulate/src simulate/pom.xml moa/src moa/pom.xml \
  pyloader/run.py pyloader/run_hi7_loader.sh pyloader/run_hi7_reg_loader.sh pyloader/run_mc1_loader.sh \
  llm/__init__.py llm/window_to_text.py llm/llm_offline_extract.py llm/feature_mapping.py llm/eval_alignment.py \
  llm/tests llm/scripts llm/calibration/model_policy.yaml \
  llm/event_mapping_hi7.yaml llm/event_mapping_mc1.yaml llm/event_mappings llm/rules \
  llm/requirements_vllm.txt
```

Adjust upward only after checking `git status --short`.

## Helper Script

You can preview the current first-release scope directly with:

```bash
bash scripts/check_public_first_release.sh
```

Other modes:

- `bash scripts/check_public_first_release.sh paths`
- `bash scripts/check_public_first_release.sh status`
