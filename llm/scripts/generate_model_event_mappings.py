#!/usr/bin/env python
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
LLM_DIR = SCRIPT_DIR.parent
if str(LLM_DIR) not in sys.path:
    sys.path.insert(0, str(LLM_DIR))

import window_to_text as wtt  # noqa: E402


DEFAULT_EVENT_TYPES = ["monotonic_increase", "spike", "drop"]
HDD_SEED_SMART_IDS = [1, 2, 3, 4, 5, 7, 8, 9, 10, 12, 192, 193, 194, 196, 197, 198, 199]
SSD_SEED_SMART_IDS = [1, 5, 9, 12, 170, 171, 172, 173, 174, 180, 183, 184, 187, 188, 194, 195, 196, 197, 198, 199, 206]


def _parse_csv_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    out: List[str] = []
    seen = set()
    for part in str(value).split(","):
        item = part.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _parse_date(value: Optional[str], date_format: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value, date_format)


def _iter_csv_files(
    data_root: str,
    date_format: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_files: int,
) -> List[str]:
    files = wtt.list_csv_files(data_root)
    start_dt = _parse_date(start_date, date_format)
    end_dt = _parse_date(end_date, date_format)
    out: List[str] = []
    for path in files:
        try:
            day = wtt.parse_date_from_filename(path, date_format)
        except Exception:
            continue
        if start_dt and day < start_dt:
            continue
        if end_dt and day > end_dt:
            continue
        out.append(path)
    if max_files and max_files > 0:
        return out[:max_files]
    return out


def _canon_to_event_feature(canon: str) -> str:
    text = str(canon or "").strip().lower()
    if not text:
        return ""
    m = re.match(r"^smart_(\d+)_(raw|normalized)$", text)
    if not m:
        return ""
    return f"SMART_{int(m.group(1))}"


def _event_feature_sort_key(value: str) -> Tuple[int, str]:
    m = re.match(r"^SMART_(\d+)$", str(value or "").upper())
    if m:
        return (int(m.group(1)), value)
    return (10**9, value)


def _seed_features_for_medium(medium: str) -> List[str]:
    ids = HDD_SEED_SMART_IDS if medium == "hdd" else SSD_SEED_SMART_IDS
    return [f"SMART_{x}" for x in ids]


def _extract_model_keys_from_window_text(glob_expr: Optional[str]) -> List[str]:
    if not glob_expr:
        return []
    import glob

    keys: List[str] = []
    seen = set()
    pattern = re.compile(r"^window_text_(.+?)_(\d{4}[-]?\d{2}[-]?\d{2})_(\d{4}[-]?\d{2}[-]?\d{2})\.jsonl$")
    for path in sorted(glob.glob(glob_expr)):
        name = os.path.basename(path)
        m = pattern.match(name)
        if not m:
            continue
        key = m.group(1)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _load_selected_features(features_path: str, data_root: str) -> List[str]:
    return wtt.load_features(features_path, data_root)


def _build_model_index(files: List[str], chunksize: int) -> Tuple[Dict[str, str], Dict[str, int]]:
    model_counter_by_key: Dict[str, Counter] = defaultdict(Counter)
    rows_by_key: Dict[str, int] = defaultdict(int)
    for path in files:
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        if "model" not in cols:
            continue
        for chunk in pd.read_csv(path, usecols=["model"], chunksize=chunksize):
            values = chunk["model"].astype(str).str.strip()
            counts = values.value_counts(dropna=False)
            for model_name, cnt in counts.items():
                model = str(model_name).strip()
                if not model or model.lower() == "nan":
                    continue
                key = wtt._normalize_model_key(model)
                model_counter_by_key[key][model] += int(cnt)
                rows_by_key[key] += int(cnt)
    preferred_model_by_key = {
        key: counter.most_common(1)[0][0]
        for key, counter in model_counter_by_key.items()
        if counter
    }
    return preferred_model_by_key, rows_by_key


def _choose_target_models(
    preferred_model_by_key: Dict[str, str],
    requested_disk_models: List[str],
    requested_model_keys: List[str],
) -> Tuple[List[str], List[str]]:
    target_keys = set()
    for model in requested_disk_models:
        target_keys.add(wtt._normalize_model_key(model))
    for key in requested_model_keys:
        target_keys.add(wtt._normalize_model_key(key))

    missing_keys: List[str] = []
    target_models: List[str] = []
    for key in sorted(target_keys):
        model = preferred_model_by_key.get(key)
        if not model:
            # Backward compatibility: many artifact filenames drop vendor prefix
            # (e.g. hds5c3030ala630 vs hitachi_hds5c3030ala630).
            suffix_matches = [
                k for k in preferred_model_by_key.keys() if k == key or k.endswith(f"_{key}") or key.endswith(f"_{k}")
            ]
            if len(suffix_matches) == 1:
                model = preferred_model_by_key[suffix_matches[0]]
        if not model:
            missing_keys.append(key)
            continue
        target_models.append(model)
    return target_models, missing_keys


def _collect_model_feature_stats(
    files: List[str],
    target_models: List[str],
    selected_features: List[str],
    chunksize: int,
) -> Dict[str, Dict[str, Any]]:
    selected_set = set(selected_features)
    target_set = set(target_models)
    rows_by_model: Dict[str, int] = defaultdict(int)
    nonnull_by_model: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in files:
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if "model" not in header:
            continue

        # Prefer higher-priority raw columns when multiple names map to the same canonical feature.
        canon_to_raw: Dict[str, str] = {}
        canon_to_priority: Dict[str, int] = {}
        for col in header:
            canon = wtt.canonicalize_feature_name(col)
            if not canon or canon not in selected_set:
                continue
            prio = wtt._feature_column_priority(str(col), canon)
            if canon not in canon_to_raw or prio > canon_to_priority[canon]:
                canon_to_raw[canon] = col
                canon_to_priority[canon] = prio

        if not canon_to_raw:
            continue

        usecols = ["model"] + sorted(set(canon_to_raw.values()))
        for chunk in pd.read_csv(path, usecols=usecols, chunksize=chunksize):
            model_values = chunk["model"].astype(str).str.strip()
            mask = model_values.isin(target_set)
            if not mask.any():
                continue
            filtered = chunk.loc[mask].copy()
            filtered["model"] = model_values.loc[mask]

            for model, group in filtered.groupby("model"):
                rows_by_model[model] += int(len(group))
                model_nonnull = nonnull_by_model[model]
                for canon, raw_col in canon_to_raw.items():
                    cnt = int(group[raw_col].notna().sum())
                    if cnt > 0:
                        model_nonnull[canon] += cnt

    out: Dict[str, Dict[str, Any]] = {}
    for model in target_models:
        out[model] = {
            "rows": int(rows_by_model.get(model, 0)),
            "feature_nonnull": dict(nonnull_by_model.get(model, {})),
        }
    return out


def _build_model_event_features(
    disk_model: str,
    model_stats: Dict[str, Any],
    selected_features: List[str],
    profile_dir: str,
    rule_medium: str,
    min_feature_presence_ratio: float,
    min_features: int,
    max_features: int,
) -> Dict[str, Any]:
    payload, profile_meta = wtt.resolve_rule_profile_payload(
        rule_profile="auto",
        profile_dir=profile_dir,
        rule_medium=rule_medium,
        disk_model=disk_model,
        features=selected_features,
    )
    medium = profile_meta.get("rule_medium", "hdd")

    rows = int(model_stats.get("rows", 0))
    feature_nonnull = model_stats.get("feature_nonnull", {})

    # Aggregate canonical feature presence to SMART_N level.
    event_presence: Dict[str, float] = defaultdict(float)
    if rows > 0:
        for canon, cnt in feature_nonnull.items():
            event = _canon_to_event_feature(canon)
            if not event:
                continue
            ratio = float(cnt) / float(rows)
            if ratio > event_presence[event]:
                event_presence[event] = ratio

    # Pull scoring hints from merged rule payload.
    rule_weight: Dict[str, float] = {}
    rule_group: Dict[str, str] = {}
    for feature_name, entry in (payload.get("features") or {}).items():
        canon = wtt.canonicalize_feature_name(feature_name)
        event = _canon_to_event_feature(canon)
        if not event:
            continue
        w = float((entry or {}).get("weight", 0.70))
        g = str((entry or {}).get("group", "unknown")).strip().lower()
        if event not in rule_weight or w > rule_weight[event]:
            rule_weight[event] = w
        if g in wtt.ROOT_CAUSE_SET and g != "unknown":
            rule_group[event] = g

    available_events = {
        _canon_to_event_feature(canon)
        for canon in selected_features
        if _canon_to_event_feature(canon)
    }
    seed_features = [x for x in _seed_features_for_medium(medium) if x in available_events]

    candidates = set(event_presence.keys()) | set(rule_weight.keys()) | set(seed_features)
    scored: List[Tuple[float, float, int, str]] = []
    for event in candidates:
        pres = float(event_presence.get(event, 0.0))
        weight = float(rule_weight.get(event, 0.70))
        grouped = 1.0 if event in rule_group else 0.35
        seed_bonus = 0.05 if event in seed_features else 0.0
        score = pres * (1.0 + weight * grouped) + seed_bonus

        # Keep weakly-supported rule/seed features for robustness, but strongly prefer present features.
        if pres < float(min_feature_presence_ratio) and event not in rule_weight and event not in seed_features:
            continue
        sid = _event_feature_sort_key(event)[0]
        scored.append((score, pres, -sid, event))

    scored.sort(reverse=True)
    ordered = [item[3] for item in scored[: max_features if max_features > 0 else len(scored)]]

    # Backfill for stability when a model has sparse rows.
    if (min_features and len(ordered) < min_features) or not ordered:
        for event in sorted(rule_weight.keys(), key=lambda x: (rule_weight[x], -_event_feature_sort_key(x)[0]), reverse=True):
            if event not in ordered:
                ordered.append(event)
            if min_features and len(ordered) >= min_features:
                break
    if min_features and len(ordered) < min_features:
        for event in seed_features:
            if event not in ordered:
                ordered.append(event)
            if len(ordered) >= min_features:
                break
    if not ordered:
        ordered = seed_features[:]

    # Enforce deterministic ordering by the computed rank first, numeric id second.
    keep = ordered[: max_features] if max_features > 0 else ordered
    seen = set()
    final_features: List[str] = []
    for item in keep:
        if item in seen:
            continue
        seen.add(item)
        final_features.append(item)

    return {
        "event_features": final_features,
        "medium": medium,
        "vendor": profile_meta.get("rule_vendor", "unknown"),
        "model_key": profile_meta.get("rule_model_key", wtt._normalize_model_key(disk_model)),
        "profile_id": profile_meta.get("rule_profile_id", ""),
        "rule_layers": profile_meta.get("rule_profile_layers", []),
        "rows": rows,
        "present_event_features": len([x for x in event_presence.keys() if event_presence[x] >= min_feature_presence_ratio]),
        "scored_candidates": len(scored),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate per-model event_mapping yaml files for llm_offline_extract.py.",
    )
    parser.add_argument("--data_root", required=True)
    parser.add_argument("--features_path", required=True)
    parser.add_argument("--profile_dir", default=str(LLM_DIR / "rules" / "profiles"))
    parser.add_argument("--rule_medium", default="auto", choices=["auto", "hdd", "ssd"])
    parser.add_argument("--date_format", default="%Y-%m-%d")
    parser.add_argument("--start_date", default=None)
    parser.add_argument("--end_date", default=None)
    parser.add_argument("--max_files", type=int, default=0)
    parser.add_argument("--disk_models", default=None, help="Comma-separated raw model names.")
    parser.add_argument("--model_keys", default=None, help="Comma-separated normalized model keys.")
    parser.add_argument(
        "--window_text_glob",
        default=None,
        help="Optional glob like 'llm/window_text_*_20140901_20141109.jsonl' to infer model keys.",
    )
    parser.add_argument("--min_rows_per_model", type=int, default=1000)
    parser.add_argument("--min_feature_presence_ratio", type=float, default=0.02)
    parser.add_argument("--min_features", type=int, default=12)
    parser.add_argument("--max_features", type=int, default=24)
    parser.add_argument("--meta_dim", type=int, default=16)
    parser.add_argument("--event_types", default="monotonic_increase,spike,drop")
    parser.add_argument("--chunksize", type=int, default=200000)
    parser.add_argument("--out_dir", default=str(LLM_DIR / "event_mappings" / "models"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--summary_out", default=None)
    args = parser.parse_args()

    files = _iter_csv_files(
        data_root=args.data_root,
        date_format=args.date_format,
        start_date=args.start_date,
        end_date=args.end_date,
        max_files=args.max_files,
    )
    if not files:
        raise ValueError("No CSV files found after date filtering.")

    selected_features = _load_selected_features(args.features_path, args.data_root)
    event_types = _parse_csv_list(args.event_types) or DEFAULT_EVENT_TYPES

    preferred_model_by_key, rows_by_key = _build_model_index(files, chunksize=args.chunksize)

    model_keys = _parse_csv_list(args.model_keys)
    model_keys.extend(_extract_model_keys_from_window_text(args.window_text_glob))
    disk_models = _parse_csv_list(args.disk_models)

    if not model_keys and not disk_models:
        model_keys = sorted(rows_by_key.keys())

    target_models, missing_keys = _choose_target_models(
        preferred_model_by_key=preferred_model_by_key,
        requested_disk_models=disk_models,
        requested_model_keys=model_keys,
    )
    if not target_models:
        raise ValueError("No target models resolved from --disk_models/--model_keys/--window_text_glob.")

    model_stats = _collect_model_feature_stats(
        files=files,
        target_models=target_models,
        selected_features=selected_features,
        chunksize=args.chunksize,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    generated = []
    skipped = []

    for model in sorted(target_models):
        rows = int(model_stats.get(model, {}).get("rows", 0))
        model_key = wtt._normalize_model_key(model)
        if rows < int(args.min_rows_per_model):
            skipped.append({"model": model, "model_key": model_key, "rows": rows, "reason": "rows_too_small"})
            continue

        mapping_info = _build_model_event_features(
            disk_model=model,
            model_stats=model_stats.get(model, {}),
            selected_features=selected_features,
            profile_dir=args.profile_dir,
            rule_medium=args.rule_medium,
            min_feature_presence_ratio=float(args.min_feature_presence_ratio),
            min_features=int(args.min_features),
            max_features=int(args.max_features),
        )
        event_features = mapping_info["event_features"]
        vector_dim = int(args.meta_dim) + len(event_features) * len(event_types)

        out_path = Path(args.out_dir) / f"event_mapping_{model_key}.yaml"
        if out_path.exists() and not args.overwrite:
            skipped.append({"model": model, "model_key": model_key, "rows": rows, "reason": "exists", "path": str(out_path)})
            continue

        payload = {
            "meta_dim": int(args.meta_dim),
            "event_types": event_types,
            "event_features": event_features,
            "meta": {
                "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_data_root": os.path.abspath(args.data_root),
                "model": model,
                "model_key": model_key,
                "rows": rows,
                "vector_dim": vector_dim,
                "rule_profile_id": mapping_info["profile_id"],
                "rule_medium": mapping_info["medium"],
                "rule_vendor": mapping_info["vendor"],
                "rule_layers": mapping_info["rule_layers"],
                "present_event_features": mapping_info["present_event_features"],
                "scored_candidates": mapping_info["scored_candidates"],
                "min_feature_presence_ratio": float(args.min_feature_presence_ratio),
            },
        }
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=False)

        generated.append(
            {
                "model": model,
                "model_key": model_key,
                "rows": rows,
                "medium": mapping_info["medium"],
                "vendor": mapping_info["vendor"],
                "event_feature_count": len(event_features),
                "vector_dim": vector_dim,
                "path": str(out_path),
            }
        )

    summary = {
        "generated_count": len(generated),
        "skipped_count": len(skipped),
        "missing_model_keys": sorted(set(missing_keys)),
        "date_range": {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "date_format": args.date_format,
            "files": len(files),
        },
        "generated": generated,
        "skipped": skipped,
    }

    if args.summary_out:
        out_parent = os.path.dirname(args.summary_out)
        if out_parent:
            os.makedirs(out_parent, exist_ok=True)
        with open(args.summary_out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
