# Workbench UI

This repository contains many historical shell launchers. They are still kept for reproducibility, but they are not a good primary user interface.

The local Workbench UI solves two problems:

1. It gives a single, stable entrypoint instead of requiring users to remember many script filenames.
2. It separates normalized workflow names from legacy script names, so the UI can be clean without breaking existing documentation.

## Entry Point

Start the local UI from the repository root:

```bash
./run_workbench.sh
```

Default URL:

```text
http://127.0.0.1:8765
```

## Naming Strategy

The UI uses a workflow registry in `ui/workflows.json`.

Each workflow has:

- `id`: stable machine-readable identifier, e.g. `llm.pilot20k.phase2-all12`
- `display_name`: normalized human-readable label shown in the UI
- `category`: high-level grouping such as `Classic Pipeline` or `LLM Framework`
- `canonical_entry`: normalized wrapper path under `workflows/`
- `legacy_entry`: original script path kept for backward compatibility

This means legacy scripts do not need to be renamed immediately. The UI becomes the canonical user-facing layer, while `workflows/` becomes the canonical CLI layer.

## Scope

The first version of the UI is intentionally curated. It does not expose every historical experiment script. Instead, it focuses on:

- classic baseline entrypoints
- main `framework_v1` phases
- the pilot20k all12 Phase2/Phase3 launchers
- the disk-model-driven onboarding branch for previously unseen HDD models
- the single-model `pilot20k` calibration branch for registered disk models
- normalized `workflows/...` wrappers for the most common tasks
- a small set of safe diagnostics and maintenance checks

High-risk or highly specialized scripts can stay as legacy/manual tools until they are worth promoting into the registry.

## Runtime Model

- The UI is a lightweight local web server implemented with the Python standard library.
- It can start registered workflows and write their logs to `logs/ui_runs/`.
- Jobs can be inspected and stopped from the UI.
- No external UI framework is required.

## Recommended Usage

Use the Workbench UI as the main entrypoint for day-to-day operation.

Keep legacy scripts for:

- reproducibility of older runs
- paper or note references
- low-level debugging
- scripts that still need cleanup before they are safe enough for the UI
