#!/usr/bin/env bash

WORKFLOW_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$WORKFLOW_LIB_DIR/../.." && pwd)}"

load_public_env() {
  local env_path="$ROOT/configs/public_repro.env"
  if [[ -f "$env_path" ]]; then
    # shellcheck disable=SC1090
    source "$env_path"
  fi
}

cd_root() {
  cd "$ROOT"
}
