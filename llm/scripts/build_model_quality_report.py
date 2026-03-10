#!/usr/bin/env python
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple


RULE_CAUSES = ["media", "interface", "temperature", "power", "workload"]


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        out = float(value)
        if out != out:
            return float(default)
        return out
    except Exception:
        return float(default)


def clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def normalize_root_cause(value) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"media", "interface", "temperature", "power", "workload", "unknown"} else "unknown"


def infer_model_key_from_path(path: str, prefix: str) -> str:
    name = os.path.basename(path)
    stem, _ = os.path.splitext(name)
    stem = stem.lower()
    if stem.startswith(prefix):
        stem = stem[len(prefix):]
    cut_markers = [
        "_fs_",
        "_zs_",
        "_phase",
        "_compare",
        "_gate",
        "_map",
        "_raw",
        "_loader",
        "_201",
        "_202",
    ]
    cut = len(stem)
    for marker in cut_markers:
        idx = stem.find(marker)
        if idx > 0:
            cut = min(cut, idx)
    model_key = re.sub(r"[^a-z0-9]+", "", stem[:cut])
    if not model_key:
        model_key = re.sub(r"[^a-z0-9]+", "", stem)
    return model_key


def parse_rule_top_cause(summary: str) -> str:
    if not summary:
        return "unknown"
    line = ""
    for raw in str(summary).splitlines():
        if raw.strip().startswith("RULE_SCORE:"):
            line = raw
            break
    if not line:
        return "unknown"
    scores = {cause: 0.0 for cause in RULE_CAUSES}
    for cause in RULE_CAUSES:
        match = re.search(rf"{cause}\s*=\s*([0-9]+(?:\.[0-9]+)?)", line)
        if match:
            scores[cause] = safe_float(match.group(1), 0.0)
    return max(scores, key=lambda key: scores[key]) if scores else "unknown"


def iter_jsonl(path: str, progress_every: int = 0, progress_label: str = "") -> Iterable[Dict]:
    start_ts = time.time()
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if progress_every > 0 and (line_no == 1 or line_no % progress_every == 0):
                elapsed = max(time.time() - start_ts, 1e-6)
                rate = line_no / elapsed
                label = progress_label or os.path.basename(path)
                print(
                    f"[build_model_quality_report] {label} lines={line_no} rate={rate:.1f} lines/s",
                    file=sys.stderr,
                    flush=True,
                )
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def quantiles(values: List[float], ps: Tuple[float, ...] = (0.1, 0.5, 0.9)) -> Dict[str, float]:
    if not values:
        return {f"q{int(p * 100)}": 0.0 for p in ps}
    vals = sorted(values)
    out: Dict[str, float] = {}
    n = len(vals)
    for p in ps:
        idx = min(max(int(round((n - 1) * p)), 0), n - 1)
        out[f"q{int(p * 100)}"] = float(vals[idx])
    return out


def load_window_top_map(
    paths: List[str],
    progress_every_rows: int = 0,
    show_progress: bool = False,
) -> Tuple[Dict[str, Dict[Tuple[str, str], str]], Dict[str, int]]:
    top_maps: Dict[str, Dict[Tuple[str, str], str]] = {}
    totals: Dict[str, int] = {}
    for path in paths:
        model_key = infer_model_key_from_path(path, "window_text_")
        key_map: Dict[Tuple[str, str], str] = {}
        count = 0
        for row in iter_jsonl(
            path,
            progress_every=(progress_every_rows if show_progress else 0),
            progress_label=f"window_text:{os.path.basename(path)}",
        ):
            disk_id = str(row.get("disk_id", ""))
            day = str(row.get("window_end_time", ""))
            if not disk_id or not day:
                continue
            summary = str(row.get("summary_text", ""))
            key_map[(disk_id, day)] = parse_rule_top_cause(summary)
            count += 1
        if key_map:
            top_maps[model_key] = key_map
            totals[model_key] = count
    return top_maps, totals


def parse_log_counts(log_paths: List[str], model_key: str) -> Dict[str, int]:
    counts = {"repair_logs": 0, "default_logs": 0}
    if not log_paths:
        return counts
    matcher = model_key.lower()
    for path in log_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    low = line.lower()
                    if matcher and matcher not in low:
                        continue
                    if "repaired invalid json" in low:
                        counts["repair_logs"] += 1
                    elif "failed to parse json" in low:
                        counts["default_logs"] += 1
        except Exception:
            continue
    return counts


def build_quality_for_cache(
    cache_path: str,
    top_map: Optional[Dict[Tuple[str, str], str]],
    window_total: int,
    log_paths: List[str],
    show_progress: bool = False,
    progress_every_rows: int = 0,
) -> Dict:
    model_key = infer_model_key_from_path(cache_path, "llm_cache_")

    total = 0
    unknown = 0
    parse_counts = Counter()
    q_values: List[float] = []
    mapped_ratio_sum = 0.0
    event_density_sum = 0.0
    cache_keys = set()

    rule_match_hits = 0
    rule_match_total = 0

    for row in iter_jsonl(
        cache_path,
        progress_every=(progress_every_rows if show_progress else 0),
        progress_label=f"cache:{os.path.basename(cache_path)}",
    ):
        total += 1
        disk_id = str(row.get("disk_id", ""))
        day = str(row.get("window_end_time", ""))
        if disk_id and day:
            cache_keys.add((disk_id, day))

        root = normalize_root_cause(row.get("root_cause_pred", row.get("root_cause")))
        if root == "unknown":
            unknown += 1

        parse_source = str(row.get("parse_source", "direct")).strip().lower()
        if parse_source not in ("direct", "repair", "default"):
            parse_source = "direct"
        parse_counts[parse_source] += 1

        q_score = row.get("llm_q_score")
        if q_score is None:
            confidence = clip01(safe_float(row.get("confidence"), 0.0))
            risk_hint = clip01(safe_float(row.get("risk_hint"), 0.0))
            noise = clip01(safe_float(row.get("label_noise_risk"), 0.0))
            q_score = min(confidence, risk_hint) * (1.0 - noise)
        q_values.append(clip01(safe_float(q_score, 0.0)))

        mapped_ratio = row.get("llm_mapped_event_ratio")
        if mapped_ratio is None:
            mapped_count = safe_float(row.get("llm_mapped_event_count"), 0.0)
            event_count = safe_float(row.get("llm_event_count"), 0.0)
            mapped_ratio = mapped_count / event_count if event_count > 0 else 0.0
        mapped_ratio_sum += clip01(safe_float(mapped_ratio, 0.0))

        event_count = safe_float(row.get("llm_event_count"), 0.0)
        if event_count <= 0 and "z_llm_11" in row:
            event_count = min(10.0, max(0.0, safe_float(row.get("z_llm_11"), 0.0) * 10.0))
        event_density_sum += max(0.0, event_count)

        if top_map:
            key = (disk_id, day)
            top = top_map.get(key)
            if top:
                rule_match_total += 1
                if "llm_rule_match" in row:
                    val = str(row.get("llm_rule_match", "")).strip().lower()
                    is_match = val in ("1", "true", "yes", "y")
                else:
                    is_match = root == top
                if is_match:
                    rule_match_hits += 1

    q_stat = quantiles(q_values)
    log_counts = parse_log_counts(log_paths, model_key)

    coverage = None
    if window_total > 0:
        coverage = len(cache_keys) / float(window_total)

    return {
        "model_key": model_key,
        "cache_path": cache_path,
        "total_rows": total,
        "unknown_ratio": round((unknown / float(total)) if total else 0.0, 6),
        "rule_match_ratio": round((rule_match_hits / float(rule_match_total)) if rule_match_total else 0.0, 6),
        "mapped_event_ratio": round((mapped_ratio_sum / float(total)) if total else 0.0, 6),
        "event_density": round((event_density_sum / float(total)) if total else 0.0, 6),
        "q_score_q10": round(q_stat["q10"], 6),
        "q_score_q50": round(q_stat["q50"], 6),
        "q_score_q90": round(q_stat["q90"], 6),
        "parse_repair_rate": round((parse_counts["repair"] / float(total)) if total else 0.0, 6),
        "parse_default_rate": round((parse_counts["default"] / float(total)) if total else 0.0, 6),
        "parse_counts": dict(parse_counts),
        "cache_coverage": round(coverage, 6) if coverage is not None else None,
        "window_total": window_total,
        "log_repair_hits": log_counts["repair_logs"],
        "log_default_hits": log_counts["default_logs"],
    }


def write_json(path: str, payload: Dict):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_summary_csv(path: str, rows: List[Dict]):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fields = [
        "model_key",
        "total_rows",
        "unknown_ratio",
        "rule_match_ratio",
        "mapped_event_ratio",
        "event_density",
        "q_score_q10",
        "q_score_q50",
        "q_score_q90",
        "parse_repair_rate",
        "parse_default_rate",
        "cache_coverage",
        "window_total",
        "cache_path",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})


def main():
    parser = argparse.ArgumentParser(description="Build per-model LLM quality diagnostics from cache/window_text artifacts.")
    parser.add_argument("--cache_paths", nargs="+", required=True, help="One or more llm_cache*.jsonl paths")
    parser.add_argument("--window_text_paths", nargs="*", default=[], help="Optional window_text*.jsonl paths")
    parser.add_argument("--log_paths", nargs="*", default=[], help="Optional extractor log paths")
    parser.add_argument("--out_dir", default="docs", help="Directory for per-model json outputs")
    parser.add_argument("--summary_csv", default="docs/model_quality_summary.csv")
    parser.add_argument("--show_progress", dest="show_progress", action="store_true", default=True)
    parser.add_argument("--no_progress", dest="show_progress", action="store_false")
    parser.add_argument("--progress_every_rows", type=int, default=200000)
    args = parser.parse_args()

    top_maps, window_totals = load_window_top_map(
        args.window_text_paths,
        progress_every_rows=max(1, int(args.progress_every_rows)),
        show_progress=bool(args.show_progress),
    )

    rows: List[Dict] = []
    for cache_path in args.cache_paths:
        model_key = infer_model_key_from_path(cache_path, "llm_cache_")
        top_map = top_maps.get(model_key)
        window_total = int(window_totals.get(model_key, 0))
        quality = build_quality_for_cache(
            cache_path,
            top_map,
            window_total,
            args.log_paths,
            show_progress=bool(args.show_progress),
            progress_every_rows=max(1, int(args.progress_every_rows)),
        )
        rows.append(quality)
        out_json = os.path.join(args.out_dir, f"model_quality_{model_key}.json")
        write_json(out_json, quality)

    rows.sort(key=lambda r: r.get("model_key", ""))
    write_summary_csv(args.summary_csv, rows)


if __name__ == "__main__":
    main()
