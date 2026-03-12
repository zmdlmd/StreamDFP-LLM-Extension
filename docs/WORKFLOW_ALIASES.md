# Workflow Aliases

The repository contains many historical shell launchers created across different experiment rounds. They are useful for reproducibility, but they are not a good primary interface.

To make the project easier to operate, the repository now has a normalized alias layer under `workflows/`.

## Goal

- keep legacy script paths stable
- give users a clean, predictable command surface
- let the Web UI and CLI use the same naming model

## Naming Rules

### UI workflow IDs

The UI uses dot-separated identifiers:

- `classic.preprocess.hi7`
- `llm.framework.phase2`
- `llm.pilot20k.phase3-all12`
- `maintenance.workbench-registry-check`

These IDs are stable labels for people and tooling.

### CLI alias paths

The CLI alias layer uses:

```text
workflows/<group>/<task>.sh
```

Examples:

- `workflows/classic/hi7-preprocess.sh`
- `workflows/llm/framework-phase2.sh`
- `workflows/llm/pilot20k-phase2-all12.sh`
- `workflows/monitoring/pilot20k-phase2-monitor.sh`

## Mapping Model

Each alias wrapper does three things:

1. resolves the repository root robustly
2. optionally loads `configs/public_repro.env`
3. delegates to the legacy script

This means the alias layer is the canonical entrypoint, while the original script remains the execution backend.

## Migration Policy

- New user-facing entrypoints should be added under `workflows/`
- The UI registry in `ui/workflows.json` should point to `workflows/...`
- Legacy script names should stay visible as metadata until they can be retired safely
- Direct renaming of historical scripts should be done only when references, docs, and old experiment notes are updated together

## Recommended Usage

For daily operation:

- use `./run_workbench.sh`
- or call `workflows/...` wrappers directly

For historical debugging:

- inspect the original `run_*.sh` and `scripts/*.sh` files
