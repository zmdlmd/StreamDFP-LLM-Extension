#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

load_public_env
cd_root
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-0}" bash scripts/run_phase2_pilot20k_all12_qwen35_then_shutdown.sh
