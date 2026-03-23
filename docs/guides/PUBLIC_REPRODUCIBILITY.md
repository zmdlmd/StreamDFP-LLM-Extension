# Public Reproducibility Guide

This guide is for turning the repository into a public, rerunnable research repo. The repository is based on the open-source StreamDFP project and adds an LLM-enhanced extension layer on top of the original pipeline.

## Reproducibility Scope

This repository supports two practical reproduction targets:

1. The upstream StreamDFP preprocessing + Java simulation pipeline for HDD/SSD baselines.
2. The `framework_v1` extension workflow for LLM-based summary generation, root-cause extraction, and Phase3 policy evaluation.

The repo does not ship raw datasets or downloaded model weights. Reproduction means rebuilding generated artifacts from public data plus local model checkpoints.

## 1. Environment

### Option A: conda

```bash
conda env create -f environment-public.yml
conda activate streamdfp-public
```

### Option B: pip

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-public.txt
python -m pip install -r requirements-llm-public.txt
```

Notes:

- The versions above match the environment used for the recent public cleanup.
- LLM Phase2 requires a CUDA-capable GPU plus a `vllm`-compatible runtime.
- Java build requires JDK 8 and Maven.

## 2. Build Java Artifacts

```bash
mvn -q -DskipTests package
```

Expected outputs:

- `simulate/target/simulate-2019.01.0-SNAPSHOT.jar`
- `moa/target/moa-2019.01.0-SNAPSHOT.jar`

## 3. Prepare Data

Current scripts expect the HDD dataset under:

```text
data/data_2014/2014/
```

The public reproducibility path assumes Backblaze-style daily SMART CSV files are placed there. Feature lists and event mappings are already in the repository:

- `pyloader/features_erg/hi7_all.txt`
- `llm/event_mapping_hi7.yaml`
- `llm/event_mappings/models_7_20140901_20141109/`
- `llm/event_mappings/batch7_20140901_20141109/`

## 4. Download a Qwen Model

Recommended local base model: `Qwen3-4B-Instruct-2507`.

Example with ModelScope:

```python
from modelscope import snapshot_download
snapshot_download(
    "Qwen/Qwen3-4B-Instruct-2507",
    local_dir="/absolute/path/to/models/Qwen/Qwen3-4B-Instruct-2507"
)
```

You can then point `MODEL_PATH` to that local directory.

## 5. Load Public Config Defaults

Copy the example config and edit the absolute paths:

```bash
cp configs/public_repro.env.example configs/public_repro.env
```

Then load it:

```bash
source configs/public_repro.env
```

The example file centralizes:

- repository root
- HDD data root
- feature list path
- model checkpoint path
- pilot window count
- Phase2/Phase3 run tags

Main public workflow scripts now infer `ROOT` from their own location by default. If you place model checkpoints in a sibling directory such as `../models/Qwen/...`, the default `MODEL_PATH` resolution also matches that layout.

## 6. Reproduce the Classic Pipeline

### Preprocess

```bash
cd pyloader
python run.py -h
```

Or use the existing example launchers:

```bash
bash run_hi7_loader.sh
```

### Train + Simulate

```bash
cd ..
bash run_hi7.sh
python parse.py hi7_example/example.txt
```

The same pattern applies to `run_hi7_reg.sh`, `run_hi640_transfer.sh`, and `run_mc1_mlp.sh`.

## 7. Reproduce the LLM-Enhanced Pipeline

### Path A: core `framework_v1` stages

```bash
source configs/public_repro.env
PHASE=0 bash scripts/run_cross_model_llm_framework_v1.sh
PHASE=1 bash scripts/run_cross_model_llm_framework_v1.sh
PHASE=2 bash scripts/run_cross_model_llm_framework_v1.sh
```

This script uses:

- `ROOT`
- `MODEL_PATH`
- `DATA_ROOT_HDD`
- `FEATURES_HDD`
- `REF_START`, `REF_END`
- `OUT_START`, `OUT_END`
- `RUN_TAG`

### Path B: 12-model `pilot20k` Phase2 + Phase3

Phase2:

```bash
source configs/public_repro.env
AUTO_SHUTDOWN=0 RUN_TAG="$RUN_TAG" bash scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh
```

Phase3:

```bash
source configs/public_repro.env
PHASE3_RUN_TAG="$RUN_TAG" \
PHASE3_TAG_SUFFIX="$PHASE3_TAG_SUFFIX" \
bash scripts/run_phase3_all_pilot20k_qwen35.sh
```

Key generated outputs:

- Phase1 inputs:
  - `llm/framework_v1/window_text_*.jsonl`
  - `llm/framework_v1/reference_*.json`
- Phase2 caches:
  - `llm/framework_v1/cache_*.jsonl`
  - `logs/framework_v1/phase2_*.log`
- Phase3 summaries:
  - `docs/prearff_grid_*.csv`
  - `docs/prearff_grid_*.md`

These files are intentionally ignored by Git because they are meant to be regenerated.

### Path C: new-model `pilot20k` calibration branch

Use this branch when a disk model is not yet part of the retained policy registry.

Recommended order:

1. Provide the raw `DISK_MODEL` name as it appears in the HDD CSV data.
2. Let the onboarding workflow derive the normalized `model_key`, build the feature contract, generate the event mapping, and run the classic no-LLM baseline automatically.
3. Use the same workflow to generate `pilot20k` Phase1 inputs, then run Phase2 extraction and Phase3 grid search for that model.
4. Compare the best LLM result against the no-LLM baseline with the same acceptance guards used by the retained registry.
5. Only after passing the guard, review the generated policy suggestion and promote it into the retained policy registry if desired.

In other words, the public workflow treats `pilot20k` as the admission-test branch for a new disk model, not as an optional afterthought.

There is now a dedicated wrapper for this path:

```bash
DISK_MODEL="Seagate ST4000DX000" \
bash workflows/llm/new-model-onboarding-calibration.sh
```

This wrapper derives the normalized `model_key`, builds the feature contract, generates an event mapping, runs a no-LLM baseline, performs Phase2 extraction, runs Phase3 calibration, and writes a suggested policy file under `llm/calibration/generated/`.

## 8. Minimal Smoke Checks

Python smoke test:

```bash
python -m unittest llm.tests.test_profile_and_fewshot
```

Schema validation example:

```bash
python llm/scripts/validate_summary_schema.py \
  --window_text_path llm/framework_v1/window_text_hi7_schema32.jsonl \
  --max_rows 32
```

## 9. Public Repo Recommendations

- Keep source, scripts, and `docs/` in Git.
- Keep `data/`, `logs/`, `share_demo/`, generated caches, and generated result folders out of Git.
- Use release assets or external storage if you need to publish a ready-made demo package.
- Prefer documenting exact `RUN_TAG`, model version, and date window in every experiment note.

## 10. Known Constraints

- The Java side depends on Maven and JDK 8.
- The LLM side depends on GPU availability and `vllm` compatibility.
- Some scripts default to absolute local paths, but all public-facing paths in the main workflow can be overridden through environment variables.
