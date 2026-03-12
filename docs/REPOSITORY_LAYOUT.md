# Repository Layout

This note explains which parts of the repository are source code, which parts are research records, and which parts are local runtime artifacts that should usually stay out of Git.

## Top-Level Directories

| Path | Purpose | Upload Suggestion |
| --- | --- | --- |
| `pyloader/` | Python preprocessing, feature extraction, sample generation, dataset conversion | Keep source files; ignore generated train/test folders |
| `simulate/` | Java simulation logic and prediction runtime | Keep source; ignore `target/` build output |
| `moa/` | MOA dependency source tree used by Java pipeline | Keep source; ignore `target/` |
| `llm/` | LLM extraction code, prompts, event mappings, contracts, utilities, tests | Keep source/config; ignore generated caches and temporary data |
| `ui/` | Local workbench UI server, workflow registry, and static frontend assets | Keep |
| `workflows/` | Canonical wrapper entrypoints with normalized names for CLI/UI use | Keep |
| `scripts/` | Batch launchers, watchers, probes, pipeline orchestration scripts | Keep |
| `docs/` | Experiment documentation, summaries, comparison tables, audit notes | Keep |
| `data/` | Local datasets for HDD/SSD experiments | Ignore |
| `logs/` | Runtime logs and monitor output | Ignore |
| `backups/` | Local backups and frozen snapshots | Ignore |
| `share_demo/` | Local share packages and compressed demo bundles | Ignore |
| `hi7_example/` | Generated result CSV/TXT outputs from baseline and Phase3 runs | Ignore |

## Important Standalone Files

| Path | Purpose |
| --- | --- |
| `README.md` | GitHub-facing repository overview |
| `parse.py` | Parse raw simulation output into metric tables |
| `run_hi7.sh` | Example launcher for classic HDD baseline |
| `run_mc1_mlp.sh` | Example launcher for SSD/MLP baseline |
| `run_workbench.sh` | Stable launcher for the local workbench UI |
| `workflows/README.md` | Naming model and wrapper policy for canonical workflow aliases |
| `run_cross_model_llm_recall_controller.sh` | Historical orchestration entry for LLM-related experiments |

## LLM Workflow Files

### Phase1

- `llm/window_to_text.py`
- `llm/framework_v1/window_text_*.jsonl` (generated, ignore)
- `llm/framework_v1/reference_*.json` (generated, ignore)

### Phase2

- `llm/llm_offline_extract.py`
- `scripts/run_cross_model_llm_framework_v1.sh`
- `scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh`
- `llm/framework_v1/cache_*.jsonl` (generated, ignore)
- `logs/framework_v1/` (generated, ignore)

### Phase3

- `llm/scripts/build_cache_variant.py`
- `scripts/run_framework_v1_phase3_grid.sh`
- `scripts/run_framework_v1_phase3_grid_batch7.sh`
- `llm/framework_v1/phase3_variants/` (generated, ignore)
- `logs/framework_v1_phase3*/` (generated, ignore)
- `hi7_example/phase3_*.csv` (generated, ignore)

## What Should Usually Be Committed

- source code under `pyloader/`, `simulate/src/`, `moa/src/`, `llm/`, `scripts/`
- root-level launcher scripts that document how experiments were run
- experiment notes and final tables under `docs/`
- lightweight config files such as `.gitignore`

## What Should Usually Stay Local

- raw datasets
- downloaded model weights
- log directories
- temporary probes
- generated cache JSONL files
- train/test output folders
- demo archives, zips, and backup snapshots

## Recommended Upload Strategy

1. Keep code, configs, and documentation in Git.
2. Exclude local datasets, logs, and generated artifacts through `.gitignore`.
3. If you need to share a full runnable example, put it in `share_demo/` locally or publish it as a release asset, not as normal repository history.
