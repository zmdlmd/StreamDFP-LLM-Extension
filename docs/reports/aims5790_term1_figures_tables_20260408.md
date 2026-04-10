# AIMS5790 Term 1 Figures and Tables

This file provides ready-to-use figure captions, table captions, suggested placement, and short in-text lead-in sentences for the first-term report.

## Figures

### Figure 1

**Suggested placement**

- Section `3.1 Overall architecture`

**Caption**

`Figure 1. Overall architecture of the StreamDFP-LLM extension. The system consists of three layers: the classic StreamDFP baseline, the LLM enhancement pipeline with Phase1/Phase2/Phase3, and the orchestration layer for workflows, monitoring, and local workbench operation.`

**In-text lead-in**

`As shown in Fig. 1, the proposed system preserves the original StreamDFP prediction backbone and adds an LLM-based semantic enhancement layer above it rather than replacing the underlying predictor.`

### Figure 2

**Suggested placement**

- Section `3.3 LLM-enhanced framework: Phase1, Phase2, and Phase3`

**Caption**

`Figure 2. Dataflow of the Phase1-Phase2-Phase3 pipeline. Windowed SMART records are first converted into structured summaries, then transformed into offline extraction caches, and finally compacted into variant feature sets that are reinjected into the original prediction chain for evaluation.`

**In-text lead-in**

`Fig. 2 illustrates the core dataflow of the semantic enhancement pipeline and clarifies how structured LLM outputs are converted into features usable by the original prediction framework.`

### Figure 3

**Suggested placement**

- Section `4.4 HDD cross-model comparison`

**Caption**

`Figure 3. HDD cross-model comparison under the retained evaluation protocol. The figure compares the number of enabled HDD disk models and the average Delta Recall over accepted models for Qwen3-4B-Instruct-2507, Qwen3.5-4B, and Qwen3.5-Plus.`

**In-text lead-in**

`Fig. 3 summarizes the main trade-off in the HDD experiments: wider disk-model coverage favors the local Qwen3-4B-Instruct-2507 baseline, whereas higher average gain on accepted models favors Qwen3.5-Plus.`

### Figure 4

**Suggested placement**

- Section `4.5 The mc1 case study: from failure diagnosis to repaired gain`

**Caption**

`Figure 4. Repair of the mc1 evaluation pipeline. The original sequential sampling strategy produced poor temporal coverage and degenerate extraction behavior, whereas the repaired stratified_day_disk pipeline restored valid contextual windows and enabled consistent positive gains across all three compared models.`

**In-text lead-in**

`The mc1 repair process is summarized in Fig. 4, which shows that the original failure pattern was caused primarily by input construction rather than by the model family itself.`

## Tables

### Table 1

**Suggested placement**

- Section `3.1 Overall architecture`

**Caption**

`Table 1. Major modules of the repository and their responsibilities.`

**In-text lead-in**

`Table 1 summarizes the main modules of the repository and clarifies the functional boundary of each layer.`

### Table 2

**Suggested placement**

- Section `3.4 Phase contract and intermediate artifacts`

**Caption**

`Table 2. Phase contract of the StreamDFP-LLM pipeline, including the main input, main output, typical artifact, and functional role of each stage.`

**In-text lead-in**

`To make the pipeline diagnosable and reproducible, Table 2 formalizes the input-output contract of each stage.`

### Table 3

**Suggested placement**

- Section `4.3 HDD policy snapshot under the locked local baseline`

**Caption**

`Table 3. HDD disk-model policy snapshot under the retained Qwen3-4B-Instruct-2507 + vLLM + ZS baseline, showing which models are marked as llm_enabled and which remain in fallback mode.`

**In-text lead-in**

`Table 3 shows that the final outcome of the HDD branch is a per-model policy rather than a single global decision.`

### Table 4

**Suggested placement**

- Section `4.4 HDD cross-model comparison`

**Caption**

`Table 4. Cross-model HDD comparison by the number of enabled disk models and average Delta Recall over accepted models.`

**In-text lead-in**

`The aggregate HDD comparison is reported in Table 4, which highlights the trade-off between policy coverage and average recall improvement.`

### Table 5

**Suggested placement**

- Section `4.5 The mc1 case study: from failure diagnosis to repaired gain`

**Caption**

`Table 5. Phase3 best-case result on repaired mc1, comparing the no-LLM baseline against the best retained LLM-enhanced configuration.`

**In-text lead-in**

`Table 5 reports the repaired mc1 result and shows that the LLM-enhanced path recovers a measurable improvement over the aligned no-LLM baseline.`

### Table 6

**Suggested placement**

- Section `4.6 Phase2 quality comparison on repaired mc1`

**Caption**

`Table 6. Phase2 extraction-quality comparison on repaired mc1 across Qwen3.5-4B, Qwen3.5-Plus, and Qwen3-4B-Instruct-2507.`

**In-text lead-in**

`To avoid over-interpreting the identical best-case Phase3 results, Table 6 compares the extraction quality of the three candidate models at the Phase2 stage.`

### Table 7

**Suggested placement**

- Section `1.5 Tasks performed by the student`

**Caption**

`Table 7. Summary of the tasks completed by the author in the first term of the individual project.`

**In-text lead-in**

`Because this is an individual project, Table 7 summarizes the major categories of work completed during the first term.`

## Optional Appendix Items

If you want a slightly stronger appendix without adding too much overhead, use the following two items first:

1. Full HDD per-disk-model comparison table.
2. Screenshot of the workbench UI with a short note on workflow orchestration and result summary.

## Compression Advice

If the final report becomes too long, keep:

- Figure 1
- Figure 3
- Figure 4
- Table 2
- Table 4
- Table 5

If space permits, then keep:

- Figure 2
- Table 3
- Table 6
- Table 7
