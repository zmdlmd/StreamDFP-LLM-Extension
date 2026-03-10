import argparse
import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple

from feature_mapping import ROOT_CAUSES
from window_to_text import iter_window_records, load_features


def read_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def get_root_cause_from_row(row: Dict) -> str:
    direct = str(row.get("root_cause_pred") or row.get("root_cause") or "").strip().lower()
    if direct in ROOT_CAUSES:
        return direct

    score_vec = [float(row.get(f"z_llm_{i}", 0.0)) for i in range(len(ROOT_CAUSES))]
    best_idx = max(range(len(ROOT_CAUSES)), key=lambda i: score_vec[i])
    return ROOT_CAUSES[best_idx]


def parse_failed_keys_from_log(log_path: str, key_set: set, run_id: Optional[str]) -> List[Tuple[str, str]]:
    if not log_path or not os.path.exists(log_path):
        return []
    pattern = re.compile(r"Failed to parse JSON for key=([^,]+),(\d{4}-\d{2}-\d{2})")
    out = set()
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if run_id and f"[run_id={run_id}]" not in line:
                continue
            m = pattern.search(line)
            if not m:
                continue
            key = (m.group(1), m.group(2))
            if key in key_set:
                out.add(key)
    return sorted(out)


def build_rule_map(
    key_set: set,
    data_root: str,
    features_path: str,
    window_days: int,
    date_format: str,
    disk_model: Optional[str],
    max_scan_windows: Optional[int],
) -> Dict[Tuple[str, str], str]:
    features = load_features(features_path, data_root)
    rule_map: Dict[Tuple[str, str], str] = {}
    for disk_id, window_end_time, _summary, _stats, target, _n_rows in iter_window_records(
        data_root,
        features,
        window_days,
        date_format,
        disk_model,
        max_scan_windows,
    ):
        key = (str(disk_id), str(window_end_time))
        if key not in key_set:
            continue
        rule_map[key] = str(target.get("root_cause", "unknown"))
        if len(rule_map) >= len(key_set):
            break
    return rule_map


def evaluate(args):
    window_rows = read_jsonl(args.window_text_path)
    cache_rows = read_jsonl(args.cache_path)

    window_keys = [(str(r["disk_id"]), str(r["window_end_time"])) for r in window_rows]
    cache_keys = [(str(r["disk_id"]), str(r["window_end_time"])) for r in cache_rows]

    key_window_set = set(window_keys)
    key_cache_set = set(cache_keys)
    overlap_keys = sorted(key_window_set & key_cache_set)
    overlap_set = set(overlap_keys)

    missing_z = []
    invalid_meta = []
    llm_root: Dict[Tuple[str, str], str] = {}
    for row in cache_rows:
        key = (str(row["disk_id"]), str(row["window_end_time"]))
        if key not in overlap_set:
            continue

        if not all(f"z_llm_{i}" in row for i in range(64)):
            missing_z.append(key)

        for field in ("risk_hint", "hardness", "confidence"):
            value = row.get(field)
            ok_number = isinstance(value, (int, float)) and math.isfinite(float(value))
            in_range = ok_number and 0.0 <= float(value) <= 1.0
            if not in_range:
                invalid_meta.append((key, field, value))
                break

        llm_root[key] = get_root_cause_from_row(row)

    rule_map = build_rule_map(
        overlap_set,
        args.data_root,
        args.features_path,
        args.window_days,
        args.date_format,
        args.disk_model,
        args.max_scan_windows,
    )

    parse_fail_keys = []
    if overlap_set:
        parse_fail_keys = parse_failed_keys_from_log(args.log_path, overlap_set, args.run_id)

    common_keys = sorted(overlap_set & set(rule_map.keys()))
    confusion = {truth: {pred: 0 for pred in ROOT_CAUSES} for truth in ROOT_CAUSES}
    mismatch = []
    match_total = 0
    non_unknown_total = 0
    non_unknown_match = 0
    llm_unknown_count = 0
    rule_unknown_count = 0

    for key in common_keys:
        truth = rule_map[key]
        pred = llm_root.get(key, "unknown")
        if truth not in confusion:
            continue
        if pred not in confusion[truth]:
            pred = "unknown"
        confusion[truth][pred] += 1
        if pred == truth:
            match_total += 1
        else:
            mismatch.append({"disk_id": key[0], "window_end_time": key[1], "truth": truth, "pred": pred})
        if truth != "unknown":
            non_unknown_total += 1
            if pred == truth:
                non_unknown_match += 1
        if pred == "unknown":
            llm_unknown_count += 1
        if truth == "unknown":
            rule_unknown_count += 1

    n_common = len(common_keys)
    parse_fail_count = len(parse_fail_keys)
    parse_success_rate = (n_common - parse_fail_count) / n_common if n_common else None

    report = {
        "window_rows": len(window_rows),
        "cache_rows": len(cache_rows),
        "overlap_rows": n_common,
        "parse_fail_count": parse_fail_count,
        "parse_success_rate": parse_success_rate,
        "missing_z_count": len(missing_z),
        "meta_invalid_count": len(invalid_meta),
        "meta_valid_rate": (n_common - len(invalid_meta)) / n_common if n_common else None,
        "llm_unknown_ratio": llm_unknown_count / n_common if n_common else None,
        "rule_unknown_ratio": rule_unknown_count / n_common if n_common else None,
        "unknown_overshoot": ((llm_unknown_count - rule_unknown_count) / n_common) if n_common else None,
        "overall_match_rate": match_total / n_common if n_common else None,
        "non_unknown_total": non_unknown_total,
        "non_unknown_match_rate": (non_unknown_match / non_unknown_total) if non_unknown_total else None,
        "confusion_matrix": confusion,
        "failure_samples_top5": [],
    }

    top_failures = []
    for key in parse_fail_keys[:5]:
        top_failures.append(
            {"disk_id": key[0], "window_end_time": key[1], "reason": "failed_to_parse_json"}
        )
    remaining = 5 - len(top_failures)
    if remaining > 0:
        for row in mismatch[:remaining]:
            top_failures.append(
                {
                    "disk_id": row["disk_id"],
                    "window_end_time": row["window_end_time"],
                    "reason": f"root_cause_mismatch (truth={row['truth']}, pred={row['pred']})",
                }
            )
    report["failure_samples_top5"] = top_failures

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window_text_path", required=True)
    parser.add_argument("--cache_path", required=True)
    parser.add_argument("--data_root", required=True)
    parser.add_argument("--features_path", required=True)
    parser.add_argument("--window_days", type=int, default=30)
    parser.add_argument("--date_format", default="%Y-%m-%d")
    parser.add_argument("--disk_model", default=None)
    parser.add_argument("--max_scan_windows", type=int, default=None)
    parser.add_argument("--log_path", default=None)
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()
