#!/usr/bin/env python3
"""
Build dense temporal LLM features from an existing cache JSONL.

Goal:
- Keep upstream extraction unchanged.
- Convert sparse per-window signals into low-dimensional dense time features.
- Output remains cache-compatible (`z_llm_*` fields), so existing run.py/simulate flow works.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


RULE_CAUSES = ["media", "interface", "temperature", "power", "workload"]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isnan(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _infer_vector_dim(row: Dict) -> int:
    max_idx = -1
    for key in row.keys():
        if not key.startswith("z_llm_"):
            continue
        try:
            idx = int(key.split("_")[-1])
        except Exception:
            continue
        if idx > max_idx:
            max_idx = idx
    return max_idx + 1 if max_idx >= 0 else 0


def _parse_day_key(value: str):
    text = str(value or "").strip()
    if not text:
        return (2, "")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = dt.datetime.strptime(text, fmt)
            return (0, d)
        except Exception:
            continue
    return (1, text)


def _parse_rule_scores(summary: str) -> Dict[str, float]:
    scores = {cause: 0.0 for cause in RULE_CAUSES}
    if not summary:
        return scores
    line = ""
    for row in str(summary).splitlines():
        if row.strip().startswith("RULE_SCORE:"):
            line = row.strip()
            break
    if not line:
        return scores
    for cause in RULE_CAUSES:
        m = re.search(rf"{cause}\s*=\s*([0-9]+(?:\.[0-9]+)?)", line)
        if m:
            scores[cause] = _safe_float(m.group(1), 0.0)
    return scores


def _rule_top_and_margin(summary: str) -> Tuple[Optional[str], float]:
    scores = _parse_rule_scores(summary)
    pairs = sorted(((v, k) for k, v in scores.items()), reverse=True)
    if not pairs:
        return None, 0.0
    top_score, top_cause = pairs[0]
    second_score = pairs[1][0] if len(pairs) > 1 else 0.0
    return top_cause, max(0.0, float(top_score) - float(second_score))


def _load_rule_map(window_text_path: Optional[str]) -> Dict[Tuple[str, str], Tuple[Optional[str], float]]:
    if not window_text_path:
        return {}
    path = Path(window_text_path)
    if not path.exists():
        raise FileNotFoundError(f"window_text_path not found: {window_text_path}")
    out: Dict[Tuple[str, str], Tuple[Optional[str], float]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            disk_id = str(row.get("disk_id", "")).strip()
            day = str(row.get("window_end_time", "")).strip()
            if not disk_id or not day:
                continue
            summary = str(row.get("summary_text", ""))
            out[(disk_id, day)] = _rule_top_and_margin(summary)
    return out


def _ema(prev: Optional[float], value: float, span: int) -> float:
    alpha = 2.0 / (float(span) + 1.0)
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


def _read_rows(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _build_dense_features(
    row: Dict,
    state: Dict,
    rule_info: Optional[Tuple[Optional[str], float]],
    streak_cap: int,
) -> List[float]:
    risk = _clip01(_safe_float(row.get("risk_hint"), 0.0))
    conf = _clip01(_safe_float(row.get("confidence"), 0.0))
    noise = _clip01(_safe_float(row.get("label_noise_risk"), 0.0))
    q = _clip01(min(risk, conf) * (1.0 - noise))

    risk_ema3 = _ema(state.get("risk_ema3"), risk, 3)
    risk_ema7 = _ema(state.get("risk_ema7"), risk, 7)
    q_ema3 = _ema(state.get("q_ema3"), q, 3)
    q_ema7 = _ema(state.get("q_ema7"), q, 7)

    state["risk_ema3"] = risk_ema3
    state["risk_ema7"] = risk_ema7
    state["q_ema3"] = q_ema3
    state["q_ema7"] = q_ema7

    risk_delta3 = risk - risk_ema3
    q_delta3 = q - q_ema3

    root = str(row.get("root_cause_pred", row.get("root_cause", "unknown"))).strip().lower()
    if root != "unknown":
        state["non_unknown_streak"] = int(state.get("non_unknown_streak", 0)) + 1
    else:
        state["non_unknown_streak"] = 0
    streak_norm = min(float(state["non_unknown_streak"]), float(streak_cap)) / float(max(streak_cap, 1))

    max_sev = _clip01(_safe_float(row.get("z_llm_12"), 0.0))
    mapped_cnt_norm = _clip01(_safe_float(row.get("z_llm_11"), 0.0))
    uncertainty = 1.0 - conf

    rule_margin = 0.0
    rule_agree = 0.5
    if rule_info is not None:
        top_cause, margin = rule_info
        rule_margin = _clip01(_safe_float(margin, 0.0))
        if top_cause is None:
            rule_agree = 0.5
        else:
            rule_agree = 1.0 if root == top_cause else 0.0

    # dense_v1 (14 dims)
    return [
        risk,          # 0
        conf,          # 1
        q,             # 2
        risk_ema3,     # 3
        risk_ema7,     # 4
        q_ema3,        # 5
        q_ema7,        # 6
        risk_delta3,   # 7
        q_delta3,      # 8
        streak_norm,   # 9
        max_sev,       # 10
        mapped_cnt_norm,  # 11
        rule_margin,   # 12
        rule_agree,    # 13
    ]


def transform_cache(
    in_cache: str,
    out_cache: str,
    target_dims: List[int],
    compact_front: bool,
    preserve_non_target: bool,
    window_text_path: Optional[str],
    streak_cap: int,
    stats_out: Optional[str],
) -> Dict:
    in_path = Path(in_cache)
    out_path = Path(out_cache)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _read_rows(in_path)
    if not rows:
        raise ValueError(f"empty cache: {in_cache}")

    vector_dim = _infer_vector_dim(rows[0])
    if vector_dim <= 0:
        raise ValueError(f"no z_llm_* fields found in {in_cache}")

    if not compact_front:
        bad = [d for d in target_dims if d < 0 or d >= vector_dim]
        if bad:
            raise ValueError(f"target_dims out of range for vector_dim={vector_dim}: {bad}")

    rule_map = _load_rule_map(window_text_path)

    # Bucket by disk_id, preserve original index for final stable output.
    buckets: Dict[str, List[Tuple[int, Tuple, Dict]]] = defaultdict(list)
    for idx, row in enumerate(rows):
        disk_id = str(row.get("disk_id", "")).strip()
        if not disk_id:
            disk_id = "__MISSING_DISK__"
        day = str(row.get("window_end_time", "")).strip()
        buckets[disk_id].append((idx, _parse_day_key(day), row))

    processed: List[Tuple[int, Dict]] = []
    total = 0
    with_rule = 0
    for disk_id, items in buckets.items():
        items.sort(key=lambda x: x[1])
        state: Dict[str, float] = {}
        for original_idx, _, row in items:
            day = str(row.get("window_end_time", "")).strip()
            rule_info = rule_map.get((str(row.get("disk_id", "")).strip(), day))
            if rule_info is not None:
                with_rule += 1
            dense = _build_dense_features(row, state, rule_info, streak_cap=streak_cap)
            total += 1

            out_row = {k: v for k, v in row.items() if not k.startswith("z_llm_")}
            if compact_front:
                for j, val in enumerate(dense):
                    out_row[f"z_llm_{j}"] = float(val)
            else:
                if preserve_non_target:
                    for i in range(vector_dim):
                        out_row[f"z_llm_{i}"] = _safe_float(row.get(f"z_llm_{i}"), 0.0)
                else:
                    for i in range(vector_dim):
                        out_row[f"z_llm_{i}"] = 0.0
                for j, dim in enumerate(target_dims):
                    if j >= len(dense):
                        break
                    out_row[f"z_llm_{dim}"] = float(dense[j])

            processed.append((original_idx, out_row))

    processed.sort(key=lambda x: x[0])
    with out_path.open("w", encoding="utf-8") as fw:
        for _, row in processed:
            fw.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = {
        "in_cache": str(in_path),
        "out_cache": str(out_path),
        "rows": total,
        "vector_dim_in": vector_dim,
        "compact_front": bool(compact_front),
        "vector_dim_out": (14 if compact_front else vector_dim),
        "target_dims": target_dims if not compact_front else list(range(14)),
        "preserve_non_target": bool(preserve_non_target),
        "window_text_path": window_text_path,
        "with_rule_rows": with_rule,
        "with_rule_ratio": (float(with_rule) / float(total)) if total else 0.0,
        "feature_set": [
            "risk_hint",
            "confidence",
            "q_score",
            "risk_ema3",
            "risk_ema7",
            "q_ema3",
            "q_ema7",
            "risk_delta3",
            "q_delta3",
            "non_unknown_streak_norm",
            "max_event_severity",
            "mapped_event_count_norm",
            "rule_margin",
            "rule_agreement",
        ],
    }

    if stats_out:
        stats_path = Path(stats_out)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dense temporal LLM cache variant (dense_v1).")
    parser.add_argument("--in_cache", required=True, help="Input cache JSONL with z_llm_* fields.")
    parser.add_argument("--out_cache", required=True, help="Output transformed cache JSONL.")
    parser.add_argument(
        "--target_dims",
        default="0,1,2,3,4,5,6,7,8,9,10,11,12,13",
        help="When not compact_front, dense features are written into these z_llm indices.",
    )
    parser.add_argument(
        "--compact_front",
        action="store_true",
        help="Write only dense features to z_llm_0..z_llm_13 (recommended for compact experiments).",
    )
    parser.add_argument(
        "--preserve_non_target",
        action="store_true",
        help="When not compact_front, keep non-target z_llm values; default is zero-fill.",
    )
    parser.add_argument(
        "--window_text_path",
        default=None,
        help="Optional window_text JSONL for rule_top/rule_margin features.",
    )
    parser.add_argument("--streak_cap", type=int, default=10, help="Cap for non-unknown streak normalization.")
    parser.add_argument("--stats_out", default=None, help="Optional path to write transform stats JSON.")
    args = parser.parse_args()

    target_dims = [int(x.strip()) for x in str(args.target_dims).split(",") if x.strip()]
    if len(target_dims) < 14 and not args.compact_front:
        raise ValueError("target_dims must have at least 14 slots when compact_front is disabled")

    stats = transform_cache(
        in_cache=args.in_cache,
        out_cache=args.out_cache,
        target_dims=target_dims,
        compact_front=bool(args.compact_front),
        preserve_non_target=bool(args.preserve_non_target),
        window_text_path=args.window_text_path,
        streak_cap=int(args.streak_cap),
        stats_out=args.stats_out,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
