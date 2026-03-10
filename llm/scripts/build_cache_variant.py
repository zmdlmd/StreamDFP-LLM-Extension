#!/usr/bin/env python
import argparse
import json
import os
import re
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple

RULE_CAUSES = ["media", "interface", "temperature", "power", "workload"]
TOP3_EVENT_DIMS = [16, 34, 46]
TOP8_EVENT_DIMS = [46, 34, 16, 25, 31, 55, 28, 37]
DEFAULT_META_DIMS = [6, 7, 9, 11, 12, 13]
DEFAULT_META_DIM = 16
DEFAULT_EVENT_TYPES = ["monotonic_increase", "spike", "drop"]
META_KEY_ALIASES = {
    "root_media": 0,
    "root_interface": 1,
    "root_temperature": 2,
    "root_power": 3,
    "root_workload": 4,
    "root_unknown": 5,
    "root_cause_media": 0,
    "root_cause_interface": 1,
    "root_cause_temperature": 2,
    "root_cause_power": 3,
    "root_cause_workload": 4,
    "root_cause_unknown": 5,
    "risk_hint": 6,
    "hardness": 7,
    "label_noise_risk": 8,
    "confidence": 9,
    "near_positive": 10,
    "mapped_event_count": 11,
    "event_count_norm": 11,
    "max_event_severity": 12,
    "severity_persistence": 13,
    "persistence": 14,
    "trend_positive": 15,
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        out = float(value)
        if out != out:  # NaN
            return float(default)
        return out
    except Exception:
        return float(default)


def _normalize_feature_name(value: str) -> str:
    text = str(value or "").strip().upper()
    m = re.search(r"SMART[_\- ]?(\d+)", text)
    if m:
        return f"SMART_{m.group(1)}"
    return text


def _normalize_event_type(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"monotonic_increase", "increase", "up", "monotonic"}:
        return "monotonic_increase"
    if text in {"spike", "burst"}:
        return "spike"
    if text in {"drop", "decrease", "down"}:
        return "drop"
    return text


def _load_yaml_or_json(path: str) -> Dict:
    _, ext = os.path.splitext(path)
    with open(path, "r", encoding="utf-8") as f:
        if ext.lower() in (".yaml", ".yml"):
            import yaml
            return yaml.safe_load(f) or {}
        return json.load(f) if ext.lower() == ".json" else json.load(f)


def _load_event_mapping(path: Optional[str]) -> Optional[Dict]:
    if not path:
        return None
    payload = _load_yaml_or_json(path)
    if not isinstance(payload, dict):
        raise ValueError("event_mapping_config must be a dict")
    meta_dim = int(payload.get("meta_dim", DEFAULT_META_DIM))
    event_features = []
    seen_feat = set()
    for feat in payload.get("event_features") or []:
        key = _normalize_feature_name(feat)
        if not key or key in seen_feat:
            continue
        seen_feat.add(key)
        event_features.append(key)
    event_types = []
    seen_types = set()
    for et in payload.get("event_types") or DEFAULT_EVENT_TYPES:
        key = _normalize_event_type(et)
        if not key or key in seen_types:
            continue
        seen_types.add(key)
        event_types.append(key)
    if not event_features:
        raise ValueError("event_mapping_config has empty event_features")
    if not event_types:
        event_types = list(DEFAULT_EVENT_TYPES)
    vector_dim = int(payload.get("vector_dim", meta_dim + len(event_features) * len(event_types)))
    return {
        "meta_dim": meta_dim,
        "event_features": event_features,
        "event_types": event_types,
        "vector_dim": vector_dim,
    }


def _parse_csv_list(raw: Optional[str]) -> List[str]:
    if raw is None:
        return []
    out: List[str] = []
    seen = set()
    for token in str(raw).split(","):
        key = token.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _resolve_meta_dims(meta_keys: List[str], meta_dim: int) -> List[int]:
    if not meta_keys:
        return [idx for idx in DEFAULT_META_DIMS if idx < meta_dim]
    dims: List[int] = []
    for token in meta_keys:
        key = str(token).strip().lower()
        if not key:
            continue
        if key in {"all_meta", "meta_all"}:
            return list(range(max(0, int(meta_dim))))
        if key.isdigit():
            idx = int(key)
            if 0 <= idx < meta_dim:
                dims.append(idx)
            continue
        if key in META_KEY_ALIASES:
            idx = int(META_KEY_ALIASES[key])
            if 0 <= idx < meta_dim:
                dims.append(idx)
    return _dedupe_keep_order(dims)


def _resolve_event_dims(event_keys: List[str], mapping: Dict) -> List[int]:
    if not event_keys:
        return []
    event_features = list(mapping.get("event_features") or [])
    event_types = list(mapping.get("event_types") or [])
    meta_dim = int(mapping.get("meta_dim", DEFAULT_META_DIM))
    if not event_features or not event_types:
        return []

    feature_to_idx = {feat: i for i, feat in enumerate(event_features)}
    type_to_idx = {tp: i for i, tp in enumerate(event_types)}
    dims: List[int] = []
    for token in event_keys:
        raw = str(token).strip()
        if not raw:
            continue
        if raw.lower() in {"all_events", "events_all"}:
            for fi in range(len(event_features)):
                for ti in range(len(event_types)):
                    dims.append(meta_dim + fi * len(event_types) + ti)
            continue
        if ":" in raw:
            f_raw, t_raw = raw.split(":", 1)
            feat = _normalize_feature_name(f_raw)
            etype = _normalize_event_type(t_raw)
            if feat not in feature_to_idx:
                continue
            if etype in {"all", "*"}:
                for ti in range(len(event_types)):
                    dims.append(meta_dim + feature_to_idx[feat] * len(event_types) + ti)
                continue
            if etype not in type_to_idx:
                continue
            dims.append(meta_dim + feature_to_idx[feat] * len(event_types) + type_to_idx[etype])
            continue
        feat = _normalize_feature_name(raw)
        if feat not in feature_to_idx:
            continue
        for ti in range(len(event_types)):
            dims.append(meta_dim + feature_to_idx[feat] * len(event_types) + ti)
    return _dedupe_keep_order(dims)


def _infer_vector_dim(row: Dict) -> int:
    max_idx = -1
    for key in row.keys():
        if key.startswith("z_llm_"):
            try:
                idx = int(key.split("_")[-1])
            except Exception:
                continue
            if idx > max_idx:
                max_idx = idx
    return max_idx + 1 if max_idx >= 0 else 0


def _parse_rule_scores_from_summary(summary: str) -> Dict[str, float]:
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


def _top_rule_cause(summary: str) -> Optional[str]:
    scores = _parse_rule_scores_from_summary(summary)
    if not scores:
        return None
    return max(RULE_CAUSES, key=lambda c: scores.get(c, 0.0))


def _load_rule_top_map(window_text_path: Optional[str]) -> Dict[Tuple[str, str], str]:
    if not window_text_path:
        return {}
    out: Dict[Tuple[str, str], str] = {}
    with open(window_text_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            disk_id = str(row.get("disk_id", ""))
            day = str(row.get("window_end_time", ""))
            summary = str(row.get("summary_text", ""))
            if not disk_id or not day:
                continue
            top = _top_rule_cause(summary)
            if top:
                out[(disk_id, day)] = top
    return out


def _pick_keep_event_dims(profile: str, top8_event_dims: Optional[List[int]]) -> List[int]:
    if profile == "all":
        return []
    if profile == "event_top3_plus_meta":
        return list(TOP3_EVENT_DIMS)
    if profile == "event_top8_plus_meta":
        if top8_event_dims:
            return list(top8_event_dims)
        return list(TOP8_EVENT_DIMS)
    raise ValueError(f"Unsupported keep_profile={profile}")


def _dedupe_keep_order(items: List[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _ensure_parent(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _iter_jsonl(path: str) -> Iterable[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def build_variant(
    in_cache: str,
    out_cache: str,
    q_gate: float,
    sev_sum_gate: float,
    require_rule_match: bool,
    keep_profile: Optional[str],
    root_cause_field: str,
    window_text_path: Optional[str],
    top8_event_dims: Optional[List[int]],
    event_mapping_config: Optional[str],
    keep_event_keys: List[str],
    keep_meta_keys: List[str],
    compact_front: bool,
    show_progress: bool,
    progress_every_rows: int,
):
    rule_top = _load_rule_top_map(window_text_path) if require_rule_match else {}
    mapping = _load_event_mapping(event_mapping_config)
    semantic_mode = bool(keep_event_keys or keep_meta_keys)
    if semantic_mode and mapping is None:
        raise ValueError("--event_mapping_config is required when --keep_event_keys/--keep_meta_keys is used")

    if semantic_mode:
        meta_dim = int(mapping.get("meta_dim", DEFAULT_META_DIM))
        keep_meta = _resolve_meta_dims(keep_meta_keys, meta_dim)
        keep_events = _resolve_event_dims(keep_event_keys, mapping)
        keep_dims_ordered = _dedupe_keep_order(keep_meta + keep_events)
        keep_all = False
    else:
        if not keep_profile:
            raise ValueError("--keep_profile is required when semantic keep keys are not used")
        keep_all = (keep_profile == "all")
        if keep_all:
            keep_events = []
            keep_dims_ordered = []
        else:
            keep_events = _pick_keep_event_dims(keep_profile, top8_event_dims)
            keep_dims_ordered = _dedupe_keep_order(DEFAULT_META_DIMS + keep_events)
    keep_dims = set(keep_dims_ordered)

    _ensure_parent(out_cache)

    total = 0
    kept = 0
    drop_unknown = 0
    drop_q = 0
    drop_rule = 0
    drop_sev = 0
    missing_rule_key = 0
    vector_dim = None
    total_bytes = os.path.getsize(in_cache) if os.path.exists(in_cache) else 0
    start_ts = time.time()
    row_step = max(1, int(progress_every_rows))

    if show_progress:
        print(
            (
                f"[build_cache_variant] start in={in_cache} out={out_cache} "
                f"size={total_bytes}B row_step={row_step}"
            ),
            file=sys.stderr,
            flush=True,
        )

    with open(in_cache, "r", encoding="utf-8") as fr, open(out_cache, "w", encoding="utf-8") as fw:
        for line in fr:
            row = json.loads(line)
            total += 1
            if vector_dim is None:
                vector_dim = _infer_vector_dim(row)

            root_cause = str(row.get(root_cause_field, row.get("root_cause", "unknown"))).strip().lower()
            risk_hint = _safe_float(row.get("risk_hint"), 0.0)
            confidence = _safe_float(row.get("confidence"), 0.0)
            label_noise = _safe_float(row.get("label_noise_risk"), 0.0)
            q = min(confidence, risk_hint) * (1.0 - max(0.0, min(1.0, label_noise)))

            keep = True
            if root_cause == "unknown":
                keep = False
                drop_unknown += 1
            elif q < q_gate:
                keep = False
                drop_q += 1

            if keep and require_rule_match:
                disk_id = str(row.get("disk_id", ""))
                day = str(row.get("window_end_time", ""))
                top = rule_top.get((disk_id, day))
                if top is None:
                    keep = False
                    drop_rule += 1
                    missing_rule_key += 1
                elif root_cause != top:
                    keep = False
                    drop_rule += 1

            if keep:
                sev_sum = 0.0
                if keep_all:
                    dim_bound = int(vector_dim or 0)
                    for d in range(DEFAULT_META_DIM, dim_bound):
                        sev_sum += _safe_float(row.get(f"z_llm_{d}"), 0.0)
                else:
                    for d in keep_events:
                        sev_sum += _safe_float(row.get(f"z_llm_{d}"), 0.0)
                if sev_sum < sev_sum_gate:
                    keep = False
                    drop_sev += 1

            if keep:
                kept += 1

            dim_bound = int(vector_dim or 0)
            if compact_front:
                row_out = {k: v for k, v in row.items() if not k.startswith("z_llm_")}
                for out_idx, src_idx in enumerate(keep_dims_ordered):
                    val = _safe_float(row.get(f"z_llm_{src_idx}"), 0.0) if keep else 0.0
                    row_out[f"z_llm_{out_idx}"] = val
                fw.write(json.dumps(row_out, ensure_ascii=False) + "\n")
            else:
                for idx in range(dim_bound):
                    key = f"z_llm_{idx}"
                    if keep and (keep_all or idx in keep_dims):
                        row[key] = _safe_float(row.get(key), 0.0)
                    else:
                        row[key] = 0.0
                fw.write(json.dumps(row, ensure_ascii=False) + "\n")

            if show_progress and total % row_step == 0:
                elapsed = time.time() - start_ts
                rate = total / max(elapsed, 1e-6)
                read_pos = fr.tell()
                pct = (100.0 * read_pos / float(total_bytes)) if total_bytes > 0 else 0.0
                print(
                    (
                        f"[build_cache_variant] rows={total} kept={kept} "
                        f"read={pct:.2f}% rate={rate:.1f} rows/s "
                        f"elapsed={_format_duration(elapsed)}"
                    ),
                    file=sys.stderr,
                    flush=True,
                )

    if show_progress:
        elapsed = time.time() - start_ts
        rate = total / max(elapsed, 1e-6) if total > 0 else 0.0
        print(
            (
                f"[build_cache_variant] done rows={total} kept={kept} "
                f"rate={rate:.1f} rows/s elapsed={_format_duration(elapsed)}"
            ),
            file=sys.stderr,
            flush=True,
        )

    print(
        json.dumps(
            {
                "in_cache": in_cache,
                "out_cache": out_cache,
                "q_gate": q_gate,
                "sev_sum_gate": sev_sum_gate,
                "require_rule_match": require_rule_match,
                "keep_profile": keep_profile,
                "event_mapping_config": event_mapping_config,
                "keep_event_keys": keep_event_keys,
                "keep_meta_keys": keep_meta_keys,
                "semantic_mode": semantic_mode,
                "root_cause_field": root_cause_field,
                "window_text_path": window_text_path,
                "vector_dim": vector_dim,
                "keep_events": keep_events,
                "keep_dims": "all" if keep_all else keep_dims_ordered,
                "compact_front": compact_front,
                "compact_dim": len(keep_dims_ordered) if compact_front else int(vector_dim or 0),
                "total": total,
                "kept": kept,
                "kept_ratio": (kept / total) if total else 0.0,
                "dropped_unknown": drop_unknown,
                "dropped_q": drop_q,
                "dropped_rule": drop_rule,
                "dropped_sev": drop_sev,
                "missing_rule_key": missing_rule_key,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Build filtered LLM cache variants; optionally repack kept dims to a compact front layout."
    )
    parser.add_argument("--in_cache", required=True)
    parser.add_argument("--out_cache", required=True)
    parser.add_argument("--q_gate", type=float, required=True)
    parser.add_argument("--sev_sum_gate", type=float, required=True)
    parser.add_argument("--require_rule_match", action="store_true")
    parser.add_argument(
        "--keep_profile",
        required=False,
        default=None,
        choices=["all", "event_top3_plus_meta", "event_top8_plus_meta"],
        help="Preset keep profile (legacy mode). Optional when semantic keep keys are provided.",
    )
    parser.add_argument(
        "--root_cause_field",
        default="root_cause_pred",
        choices=["root_cause_pred", "root_cause"],
    )
    parser.add_argument(
        "--window_text_path",
        default=None,
        help="Optional window_text jsonl used to resolve RULE_SCORE top cause when --require_rule_match is set.",
    )
    parser.add_argument(
        "--top8_event_dims",
        default=None,
        help="Override top8 event dims, e.g. 46,34,16,25,31,55,28,37",
    )
    parser.add_argument(
        "--event_mapping_config",
        default=None,
        help="Event mapping yaml/json used to resolve semantic event keys to z_llm indices",
    )
    parser.add_argument(
        "--keep_event_keys",
        default=None,
        help="Semantic event selection, e.g. SMART_5:monotonic_increase,SMART_197:all,SMART_199",
    )
    parser.add_argument(
        "--keep_meta_keys",
        default=None,
        help="Semantic meta selection, e.g. risk_hint,confidence,mapped_event_count",
    )
    parser.add_argument(
        "--compact_front",
        action="store_true",
        help="Repack kept dimensions to contiguous z_llm_0..z_llm_{k-1} to reduce ARFF LLM columns.",
    )
    parser.add_argument(
        "--show_progress",
        dest="show_progress",
        action="store_true",
        default=True,
        help="Print progress to stderr (enabled by default)",
    )
    parser.add_argument(
        "--no_progress",
        dest="show_progress",
        action="store_false",
        help="Disable progress logs",
    )
    parser.add_argument(
        "--progress_every_rows",
        type=int,
        default=100000,
        help="Emit progress every N processed rows",
    )

    args = parser.parse_args()
    top8_event_dims = None
    if args.top8_event_dims:
        top8_event_dims = [int(x.strip()) for x in str(args.top8_event_dims).split(",") if x.strip()]
    keep_event_keys = _parse_csv_list(args.keep_event_keys)
    keep_meta_keys = _parse_csv_list(args.keep_meta_keys)

    build_variant(
        in_cache=args.in_cache,
        out_cache=args.out_cache,
        q_gate=float(args.q_gate),
        sev_sum_gate=float(args.sev_sum_gate),
        require_rule_match=bool(args.require_rule_match),
        keep_profile=str(args.keep_profile) if args.keep_profile else None,
        root_cause_field=str(args.root_cause_field),
        window_text_path=args.window_text_path,
        top8_event_dims=top8_event_dims,
        event_mapping_config=args.event_mapping_config,
        keep_event_keys=keep_event_keys,
        keep_meta_keys=keep_meta_keys,
        compact_front=bool(args.compact_front),
        show_progress=bool(args.show_progress),
        progress_every_rows=max(1, int(args.progress_every_rows)),
    )


if __name__ == "__main__":
    main()
