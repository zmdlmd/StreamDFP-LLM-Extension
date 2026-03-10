#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_PARENT="$(cd "$DEFAULT_ROOT/.." && pwd)"
ROOT="${1:-$DEFAULT_ROOT}"
RUN_POST="${RUN_POST:-1}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"
RETRY_SLEEP="${RETRY_SLEEP:-30}"
MAX_RESTARTS="${MAX_RESTARTS:-0}"   # 0 means unlimited
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-0}"
SHUTDOWN_DELAY_MIN="${SHUTDOWN_DELAY_MIN:-1}"

WINDOW_PATH="llm/window_text_hms5c4040ble640_20140901_20141109_v2.jsonl"
REFERENCE_PATH="llm/reference_examples_hms5c4040ble640_train_0101_0831_v2.json"
OUT_PATH="llm_cache_hms5c4040ble640_fs_robustv6_recall_20140901_20141109.jsonl"
MAPPING_PATH="llm/event_mappings/models_7_20140901_20141109/event_mapping_hgst_hms5c4040ble640.yaml"
MODEL_PATH="${MODEL_PATH:-$REPO_PARENT/models/Qwen/Qwen3.5-4B}"

count_rows() {
  local path="$1"
  if [[ -f "$path" ]]; then
    wc -l < "$path" | tr -d ' '
  else
    echo 0
  fi
}

gpu_ready() {
  nvidia-smi >/dev/null 2>&1 || return 1
  python - <<'PY' >/dev/null 2>&1
import torch
raise SystemExit(0 if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 1)
PY
}

extract_pid() {
  ps -eo pid=,args= | awk -v out="$OUT_PATH" '
    index($0, "llm/llm_offline_extract.py") > 0 && index($0, "--out " out) > 0 {
      print $1
      exit
    }'
}

launch_extract_once() {
  local attempt="$1"
  local stamp="$2"
  local log_path="logs/hms5c4040ble640_rerun_extract_robustv6_recall_auto_attempt${attempt}_${stamp}.log"

  echo "[auto-resume] launch attempt=${attempt} log=${log_path}"
  set +e
  python llm/llm_offline_extract.py \
    --window_text_path "$WINDOW_PATH" \
    --reference_examples "$REFERENCE_PATH" \
    --out "$OUT_PATH" \
    --model "$MODEL_PATH" \
    --backend vllm \
    --batch_size 32 \
    --vllm_max_model_len 12288 \
    --vllm_gpu_memory_utilization 0.92 \
    --vllm_max_num_batched_tokens 24576 \
    --max_new_tokens 220 \
    --temperature 0 \
    --top_p 0.9 \
    --fewshot_mode force \
    --reference_max_examples 12 \
    --rule_score_gate 0.32 \
    --rule_score_soft_gate 0.12 \
    --event_quality_gate 0.0 \
    --event_min_count 0 \
    --enforce_event_feature_whitelist \
    --emit_quality_meta \
    --event_mapping_config "$MAPPING_PATH" \
    --flush_every 2048 \
    --log_every_batches 50 \
    --write_root_cause_pred > "$log_path" 2>&1
  local rc=$?
  set -e
  echo "[auto-resume] attempt=${attempt} exit_code=${rc}"
  return "$rc"
}

run_post_pipeline() {
  echo "[auto-resume] running post pipeline"
  python llm/scripts/build_model_quality_report.py \
    --cache_paths "$OUT_PATH" \
    --window_text_paths "$WINDOW_PATH" \
    --log_paths logs/llm_offline_extract.log \
    --out_dir docs/model_quality_hms_robustv6_recall \
    --summary_csv docs/model_quality_summary_hms_robustv6_recall.csv

  bash scripts/controller_hooks/policy_grid_hms5c4040ble640.sh hms5c4040ble640 9 "$ROOT"
  bash scripts/controller_hooks/microgrid_hms5c4040ble640.sh hms5c4040ble640 9 "$ROOT"
  bash run_robust_eval_report_v2.sh
}

cd "$ROOT"
mkdir -p logs

for p in "$WINDOW_PATH" "$REFERENCE_PATH" "$MAPPING_PATH"; do
  if [[ ! -f "$p" ]]; then
    echo "[auto-resume] missing required file: $p" >&2
    exit 2
  fi
done

restarts=0

while true; do
  total_rows="$(count_rows "$WINDOW_PATH")"
  cache_rows="$(count_rows "$OUT_PATH")"

  if (( cache_rows >= total_rows )); then
    echo "[auto-resume] extraction complete rows=${cache_rows}/${total_rows}"
    break
  fi

  pid="$(extract_pid)"
  if [[ -n "$pid" ]]; then
    echo "[auto-resume] extractor running pid=${pid} rows=${cache_rows}/${total_rows}"
    sleep "$CHECK_INTERVAL"
    continue
  fi

  if ! gpu_ready; then
    echo "[auto-resume] GPU unavailable; retry in ${RETRY_SLEEP}s"
    sleep "$RETRY_SLEEP"
    continue
  fi

  restarts=$((restarts + 1))
  if (( MAX_RESTARTS > 0 && restarts > MAX_RESTARTS )); then
    echo "[auto-resume] reached MAX_RESTARTS=${MAX_RESTARTS}; abort"
    exit 3
  fi

  stamp="$(date +%Y%m%d_%H%M%S)"
  if launch_extract_once "$restarts" "$stamp"; then
    :
  else
    echo "[auto-resume] extract run failed; will retry in ${RETRY_SLEEP}s"
    sleep "$RETRY_SLEEP"
  fi
done

if [[ "$RUN_POST" == "1" ]]; then
  run_post_pipeline
fi

if [[ "$AUTO_SHUTDOWN" == "1" ]]; then
  echo "[auto-resume] scheduling shutdown in ${SHUTDOWN_DELAY_MIN} minute(s)"
  shutdown -h +"$SHUTDOWN_DELAY_MIN"
fi

echo "[auto-resume] done"
