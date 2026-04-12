# AIMS5790 Term 1 Report Plan

## 1. Scope and constraints

This report should follow the course requirement in `docs/write_report/requirements.txt`.

- Main body within 20 pages.
- Required sections:
  - Cover Sheet
  - Abstract
  - Introduction
  - Overview of Related Works
  - Detailed Descriptions of the Methodology and Results
  - Conclusion, Discussion and Future Work
  - References
  - Appendix (optional)
- Because this is the first report for a two-term project, add one page at the end for the plan of the second term.
- If this is a team project, the introduction must include:
  - tasks performed by the student
  - contribution percentages for the major tasks

## 2. Recommended title options

Choose one and keep it consistent with the cover sheet.

1. `LLM-Enhanced Disk Failure Prediction on Top of StreamDFP: System Design, Evaluation, and First-Term Progress`
2. `A Hybrid Stream Learning and LLM-Augmented Framework for Disk Failure Prediction`
3. `Extending StreamDFP with Structured LLM Signals for Disk Failure Prediction`

## 3. Recommended structure

This version should stay close to the course template instead of expanding into a thesis-style ten-chapter report.

1. Cover Sheet
2. Abstract
3. Introduction
4. Overview of Related Works
5. Methodology and System Design
6. Experimental Setup and Results
7. Conclusion, Discussion and Future Work
8. References
9. Appendix (optional)
10. Plan for the Second Term

## 4. Page budget

Recommended allocation for a 20-page main body:

| Section | Suggested length |
| --- | ---: |
| Abstract | 0.5 page |
| Introduction | 2.0 to 2.5 pages |
| Related Works | 1.5 to 2.0 pages |
| Methodology and System Design | 5.5 to 6.5 pages |
| Experimental Setup and Results | 6.0 to 7.0 pages |
| Conclusion, Discussion and Future Work | 1.5 to 2.0 pages |
| Total main body | about 17 to 20 pages |

The final "Plan for the Second Term" page is outside the main narrative and should be appended after the references or appendix according to the programme instruction.

## 5. Writing strategy for the first-term submission

This first report should emphasize three things:

1. The project already has a complete and coherent system architecture.
2. The current term already produced concrete comparative results, including HDD policy evaluation and the repaired `mc1` case.
3. The second term will focus on consolidation, expansion, and stronger validation rather than restarting the problem definition.

In other words, this report should read as:

- a credible research progress report
- a technically grounded system paper draft
- a staged project update with a clear next-term plan

## 6. Section-by-section source mapping

| Report section | Main source files |
| --- | --- |
| Abstract | `docs/reports/project_modules/00_学术报告总纲与写作路线.md`, `07_评估协议_核心结果与写作建议.md` |
| Introduction | `docs/reports/project_modules/01_研究背景与问题定义.md` |
| Related Works | `docs/reports/project_modules/01_研究背景与问题定义.md`, `03_经典StreamDFP主链.md`, `04_LLM增强框架_framework_v1.md` |
| Methodology and System Design | `docs/reports/project_modules/02_系统总体架构与模块边界.md`, `03_经典StreamDFP主链.md`, `04_LLM增强框架_framework_v1.md`, `06_实验编排_资源管理与Workbench_UI.md`, `README.md` |
| Experimental Setup and Results | `docs/reports/project_modules/05_MC1专项修复与对照实验.md`, `07_评估协议_核心结果与写作建议.md`, `docs/reports/qwen3_instruct_vs_qwen35_4b_vs_qwen35_plus_comparison_20260315.md` |
| Conclusion and Future Work | `docs/reports/project_modules/08_局限性_风险与未来工作.md` |
| Second-term plan | derive from `08_局限性_风险与未来工作.md` plus actual project milestones |

## 7. Required figures and tables

Prioritize the minimum set below. These are enough for a solid first-term submission.

### Figures

1. Overall architecture:
   classic StreamDFP pipeline + LLM Phase1/2/3 + new-model onboarding branch.
2. Dataflow of `Phase1 -> Phase2 -> Phase3`:
   show `summary_text`, cache, variant, and final simulation outputs.
3. HDD comparison chart:
   enabled disk-model count and average `Delta Recall` for the three candidate models.
4. `mc1` repair chart:
   old faulty input vs `stratified_v2` repaired input, plus final best-case results.

### Tables

1. Module responsibility table.
2. Three-phase input/output table.
3. HDD cross-model comparison table.
4. `mc1` Phase2 quality comparison table.
5. `mc1` Phase3 final result table.
6. Personal task/contribution table.

## 8. Concrete drafting order

Use this order to avoid blocking on missing details.

1. Finish the result section first.
2. Write the methodology section around the already-fixed architecture.
3. Write the introduction after the contributions and results are stable.
4. Write the abstract last.
5. Add the second-term plan as the final page.
6. Convert the markdown draft into the required Word or PDF format only after the content is stable.

## 9. User-specific blanks that still need confirmation

The current draft can be prepared without these details, but they must be filled before submission.

1. Student name and student ID.
2. Exact final report title.
3. Whether this is an individual or team project.
4. If team project:
   task list and contribution percentages.
5. Preferred reference style:
   numbered, APA, IEEE, or department-specific style.
6. Whether the final submitted language will be English only.

## 10. Deliverables prepared in this round

This plan is paired with:

- `docs/reports/aims5790_term1_report_draft_20260408.md`

That draft is a report skeleton with project-specific content already filled where the repository provides enough evidence.
