# Workflow Aliases

This directory provides stable, normalized entrypoints for the most important workflows in the repository.

The goal is to avoid breaking historical script paths while still giving users a clean operational surface.

Rules:

- `workflows/classic/`: classic upstream StreamDFP preprocessing and training entrypoints
- `workflows/llm/`: LLM-enhanced `framework_v1`, pilot20k, batch7, and MC1 flows
- `workflows/monitoring/`: read-only monitors and progress helpers
- `workflows/maintenance/`: repository checks and low-risk maintenance helpers

Each wrapper keeps the original script as the execution backend and only normalizes naming, defaults, and repository-root resolution.
