# GitHub Upload Checklist

Use this checklist before pushing the repository.

## Keep in Git

- source code under `pyloader/`, `simulate/src/`, `moa/src/`, `llm/`, `scripts/`
- root launcher scripts such as `run_hi7.sh`
- documentation under `docs/`
- repository metadata such as `README.md` and `.gitignore`

## Keep Out of Git

- `data/`
- `logs/`
- `backups/`
- `share_demo/`
- generated result folders such as `hi7_example/`
- generated cache/input files under `llm/framework_v1/`
- generated train/test folders under `pyloader/`

## Quick Check

```bash
git status --short
```

You should mainly see source files and docs you intentionally want to publish.

## Typical First Commit Scope

```bash
git add README.md .gitignore docs pyloader simulate/src moa/src llm scripts parse.py run_*.sh
```

Adjust that command if you want to keep only part of the experiment history in Git.
