# StreamDFP

This repository is based on the open-source StreamDFP project and extends it with an LLM-enhanced workflow for root-cause extraction, rule fusion, and model-level policy evaluation in disk failure prediction.

The current codebase keeps both the upstream Python + Java prediction pipeline and the extension work added on top of it. It is organized for research reproduction rather than as a minimal library package. Source code, experiment scripts, and result notes are kept together; large datasets, logs, generated caches, and local demo bundles are ignored by default so the repository can be uploaded to GitHub without dragging in runtime artifacts.

If you publish this repository separately on GitHub, prefer a name such as `StreamDFP-LLM-Extension` instead of the bare `StreamDFP`, so the upstream relationship stays clear.

## Upstream Attribution

This project builds on the open-source StreamDFP framework:

- Upstream repository: `https://github.com/shujiehan/StreamDFP`

The work in this repository focuses on extending StreamDFP with an LLM-enhanced pipeline for semantic root-cause extraction, rule blending, fallback control, and model-level policy evaluation.

## Highlights

- Upstream StreamDFP pipeline for HDD/SSD failure prediction with preprocessing in Python and training/simulation in Java.
- StreamDFP-based LLM-enhanced framework (`framework_v1`) for Phase1 window summarization, Phase2 root-cause extraction, and Phase3 policy grid evaluation.
- Extension modules for model-level policy registry, rule blending, fallback control, and multi-disk experiment summaries.

## Repository Layout

```text
StreamDFP/
├── pyloader/          # Python preprocessing, feature extraction, labeling, sample generation
├── simulate/          # Java simulation and prediction entry points
├── moa/               # MOA dependency source tree used by the Java pipeline
├── llm/               # LLM prompts, extraction logic, event mappings, contracts, tests
├── scripts/           # Phase2/Phase3 orchestration, watchers, probes, reproducibility helpers
├── docs/              # Experiment notes, summaries, comparison tables, metric reports
├── parse.py           # Parse simulation outputs into metric tables
└── run_*.sh           # Legacy example launchers for baseline experiments
```

Detailed directory notes are in [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md).
Documentation entry points are indexed in [docs/README.md](docs/README.md).

## Main Workflows

### 1. Classic StreamDFP Pipeline

1. Generate train/test samples with [pyloader/run.py](pyloader/run.py) or the `pyloader/run_*_loader.sh` helpers.
2. Train and simulate with the Java entrypoint in [simulate/](simulate/) using `simulate.Simulate`.
3. Parse metrics with [parse.py](parse.py).

Relevant files:

- [pyloader/run.py](pyloader/run.py)
- [run_hi7.sh](run_hi7.sh)
- [run_mc1_mlp.sh](run_mc1_mlp.sh)
- [parse.py](parse.py)

### 2. LLM-Enhanced Framework (`framework_v1`)

1. Convert sliding windows into textual summaries with [llm/window_to_text.py](llm/window_to_text.py).
2. Run offline LLM extraction with [llm/llm_offline_extract.py](llm/llm_offline_extract.py).
3. Build cache variants and evaluate them through the Phase3 grid scripts.
4. Merge per-model results into model-level policy decisions (`llm_enabled` vs `fallback`).

Relevant files:

- [scripts/run_cross_model_llm_framework_v1.sh](scripts/run_cross_model_llm_framework_v1.sh)
- [scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh](scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh)
- [scripts/run_framework_v1_phase3_grid.sh](scripts/run_framework_v1_phase3_grid.sh)
- [scripts/run_framework_v1_phase3_grid_batch7.sh](scripts/run_framework_v1_phase3_grid_batch7.sh)
- [llm/scripts/build_cache_variant.py](llm/scripts/build_cache_variant.py)

## Environment

Minimum runtime dependencies:

- Python 3
- `numpy`, `pandas`
- Java JDK 8

Optional LLM runtime:

- `vllm` for GPU-backed Phase2 extraction
- Qwen-family model weights downloaded locally from HuggingFace or ModelScope

Public repo environment files:

- [requirements-public.txt](requirements-public.txt)
- [requirements-llm-public.txt](requirements-llm-public.txt)
- [environment-public.yml](environment-public.yml)
- [configs/public_repro.env.example](configs/public_repro.env.example)

The public reproducibility walkthrough is in [docs/PUBLIC_REPRODUCIBILITY.md](docs/PUBLIC_REPRODUCIBILITY.md).

## Data and Models

This repository does not require committing raw datasets or downloaded model weights.

- Public HDD data typically comes from Backblaze SMART records.
- Public SSD experiments can use Alibaba SSD SMART datasets.
- Local datasets under `data/` are ignored by `.gitignore`.
- Local model directories outside the repo are recommended for Qwen checkpoints.

## Recommended Reading Order

If you are new to this repository, start here:

1. [docs/README.md](docs/README.md)
2. [docs/cross_model_llm_framework_v1_final.md](docs/cross_model_llm_framework_v1_final.md)
3. [docs/llm_recent_experiments_master_summary_20260305.md](docs/llm_recent_experiments_master_summary_20260305.md)
4. [docs/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md](docs/llm_recent_experiments_qwen35_pilot20k_summary_20260310.md)

## GitHub Upload Notes

This repository is now prepared for GitHub-style uploading with source code and experiment docs kept visible, while the following classes of files are ignored:

- raw datasets and local backups
- logs, generated caches, and temporary JSONL files
- training/test output folders under `pyloader/`
- local demo bundles and compressed share packages
- Java build outputs and notebook checkpoints

Before pushing, check `git status` and only stage the code/docs you really want to publish.

## Contact

Original project contact from the upstream README:

- Shujie Han (`shujiehan@pku.edu.cn`)
