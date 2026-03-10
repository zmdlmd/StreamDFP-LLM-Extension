# GitHub Metadata

This note provides GitHub-facing text for the public repository page. The wording is aligned with the fact that this project is an extension built on top of the open-source StreamDFP repository.

## Repository Positioning

Do not describe this repository as the original StreamDFP project.
Use wording such as:

- based on the open-source StreamDFP project
- StreamDFP-based extension
- extension repository for LLM-enhanced disk failure prediction

## Suggested Repository Names

Prefer a name that makes the upstream relationship explicit and avoids colliding with the original project name.

Recommended:

- `StreamDFP-LLM-Extension`
- `StreamDFP-LLM`
- `StreamDFP-RootCause-Extension`

Avoid:

- `StreamDFP`
- `StreamDFP-public`

## GitHub About

Recommended:

`A reproducible extension of the open-source StreamDFP framework, adding an LLM-enhanced root-cause extraction and policy evaluation pipeline for disk failure prediction.`

Shorter version:

`A StreamDFP-based extension for reproducible disk failure prediction with LLM-enhanced root-cause extraction and policy evaluation.`

## Suggested Topics

Recommended full set:

- `disk-failure-prediction`
- `predictive-maintenance`
- `stream-learning`
- `concept-drift`
- `smart-data`
- `time-series`
- `llm`
- `vllm`
- `backblaze`
- `python`
- `java`
- `moa`

Compact set:

- `disk-failure-prediction`
- `predictive-maintenance`
- `stream-learning`
- `concept-drift`
- `smart-data`
- `llm`
- `python`
- `java`

## Release Title

Recommended:

- `v1.0.0-streamdfp-extension-public`
- `v1.0.0-llm-extension-public`

More attribution-explicit version:

- `v1.0.0-streamdfp-based-reproducible-release`

## Release Description

```md
## Public Reproducible Release of the StreamDFP-Based Extension

This release provides the first public reproducible release of our extension project built on top of the open-source StreamDFP framework.

### Included
- Upstream StreamDFP preprocessing and simulation pipeline
- LLM-enhanced `framework_v1` extension workflow
- Public environment files and reproducibility guide
- Core experiment documentation and model comparison summaries
- GitHub-ready repository structure and ignore rules

### Upstream Attribution
This repository is based on the open-source StreamDFP project:
https://github.com/shujiehan/StreamDFP

### Reproducibility
Please start from:
- `README.md`
- `docs/PUBLIC_REPRODUCIBILITY.md`
- `docs/PUBLIC_FIRST_RELEASE_SCOPE.md`

### Notes
- Raw datasets and generated runtime artifacts are not included
- Local model checkpoints should be downloaded separately
- Java build requires JDK 8 and Maven
- LLM Phase2 requires a CUDA-capable GPU with `vllm`
```

## One-Line Chinese Description

`一个基于开源 StreamDFP 框架的可复现实验扩展项目，增加了面向磁盘故障预测的大模型根因抽取与策略评估流程。`
