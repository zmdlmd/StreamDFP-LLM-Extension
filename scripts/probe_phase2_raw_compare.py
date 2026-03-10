#!/usr/bin/env python3
import argparse
import gc
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "llm"))

from llm_offline_extract import build_backend, build_messages, extract_json  # noqa: E402


Key = Tuple[str, str]


def load_cache(path: Path) -> Dict[Key, Dict]:
    rows: Dict[Key, Dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row.get("disk_id", "")), str(row.get("window_end_time", "")))
            rows[key] = row
    return rows


def parse_transition(token: str) -> Tuple[str, str]:
    if ":" not in token:
        raise ValueError(f"invalid transition: {token}")
    left, right = token.split(":", 1)
    return left.strip().lower(), right.strip().lower()


def select_keys(
    old_rows: Dict[Key, Dict],
    new_rows: Dict[Key, Dict],
    transitions: List[Tuple[str, str]],
    per_transition: int,
) -> List[Dict]:
    selected: List[Dict] = []
    shared = sorted(set(old_rows) & set(new_rows))
    for old_label, new_label in transitions:
        count = 0
        for key in shared:
            old_row = old_rows[key]
            new_row = new_rows[key]
            old_pred = str(old_row.get("root_cause_pred", "")).strip().lower()
            new_pred = str(new_row.get("root_cause_pred", "")).strip().lower()
            if old_pred != old_label or new_pred != new_label:
                continue
            selected.append(
                {
                    "disk_id": key[0],
                    "window_end_time": key[1],
                    "transition": f"{old_label}->{new_label}",
                    "old_pred": old_pred,
                    "new_pred": new_pred,
                    "old_confidence": old_row.get("confidence"),
                    "new_confidence": new_row.get("confidence"),
                    "old_risk_hint": old_row.get("risk_hint"),
                    "new_risk_hint": new_row.get("risk_hint"),
                    "old_rule_top_cause": old_row.get("llm_rule_top_cause"),
                    "new_rule_top_cause": new_row.get("llm_rule_top_cause"),
                }
            )
            count += 1
            if count >= per_transition:
                break
    return selected


def load_window_lookup(path: Path, wanted: Iterable[Key]) -> Dict[Key, str]:
    target = set(wanted)
    lookup: Dict[Key, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row.get("disk_id", "")), str(row.get("window_end_time", "")))
            if key in target:
                lookup[key] = str(row.get("summary_text", ""))
    return lookup


def batched(seq: List[Dict], batch_size: int) -> Iterable[List[Dict]]:
    for idx in range(0, len(seq), batch_size):
        yield seq[idx : idx + batch_size]


def probe_model(args, samples: List[Dict], label: str, model_path: str) -> List[Dict]:
    backend = build_backend(
        args.backend,
        model_path,
        args.enable_thinking,
        args.max_new_tokens,
        args.temperature,
        args.top_p,
        args.vllm_tensor_parallel_size,
        args.vllm_gpu_memory_utilization,
        args.vllm_max_model_len,
        args.vllm_enforce_eager,
        args.vllm_max_num_batched_tokens,
    )

    outputs: List[Dict] = []
    for batch in batched(samples, args.batch_size):
        batch_messages = [build_messages(item["summary_text"], [], prompt_profile=args.prompt_profile) for item in batch]
        raw_outputs = backend.generate(batch_messages)
        for item, raw_text in zip(batch, raw_outputs):
            outputs.append(
                {
                    **{k: v for k, v in item.items() if k != "summary_text"},
                    "model_label": label,
                    "model_path": model_path,
                    "raw_text": raw_text,
                    "parsed_json": extract_json(raw_text),
                }
            )
    del backend
    gc.collect()
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old_cache", required=True)
    parser.add_argument("--new_cache", required=True)
    parser.add_argument("--window_text_path", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--old_model", required=True)
    parser.add_argument("--new_model", required=True)
    parser.add_argument("--model", default=None, help="Optional single-model path; when set, only this model is probed.")
    parser.add_argument("--model_label", default=None, help="Label used together with --model.")
    parser.add_argument(
        "--transition",
        action="append",
        default=[],
        help="Transition in old:new form, e.g. temperature:unknown. Can repeat.",
    )
    parser.add_argument("--per_transition", type=int, default=6)
    parser.add_argument("--prompt_profile", default="structured_v2", choices=["legacy", "structured_v2"])
    parser.add_argument("--backend", default="vllm", choices=["auto", "vllm", "transformers"])
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--max_new_tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--enable_thinking", action="store_true")
    parser.add_argument("--vllm_tensor_parallel_size", type=int, default=1)
    parser.add_argument("--vllm_gpu_memory_utilization", type=float, default=0.8)
    parser.add_argument("--vllm_max_model_len", type=int, default=4096)
    parser.add_argument("--vllm_enforce_eager", action="store_true")
    parser.add_argument("--vllm_max_num_batched_tokens", type=int, default=1024)
    args = parser.parse_args()

    transitions = [parse_transition(t) for t in (args.transition or ["temperature:unknown", "media:unknown", "temperature:media"])]
    old_rows = load_cache(Path(args.old_cache))
    new_rows = load_cache(Path(args.new_cache))
    samples = select_keys(old_rows, new_rows, transitions, args.per_transition)
    wanted = {(row["disk_id"], row["window_end_time"]) for row in samples}
    summaries = load_window_lookup(Path(args.window_text_path), wanted)

    for row in samples:
        row["summary_text"] = summaries[(row["disk_id"], row["window_end_time"])]

    results: List[Dict] = []
    if args.model:
        label = args.model_label or "single_model"
        results.extend(probe_model(args, samples, label, args.model))
    else:
        results.extend(probe_model(args, samples, "old_model", args.old_model))
        results.extend(probe_model(args, samples, "new_model", args.new_model))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"wrote {len(results)} rows to {out_path}")


if __name__ == "__main__":
    main()
