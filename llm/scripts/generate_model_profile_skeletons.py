#!/usr/bin/env python
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
LLM_DIR = SCRIPT_DIR.parent
if str(LLM_DIR) not in sys.path:
    sys.path.insert(0, str(LLM_DIR))

import window_to_text as wtt  # noqa: E402


def _load_selected_features(features_path: str) -> List[str]:
    if not features_path:
        return []
    with open(features_path, "r", encoding="utf-8") as f:
        return [wtt.canonicalize_feature_name(x.strip()) for x in f if x.strip()]


def _collect_model_feature_stats(
    data_root: str,
    selected_features: List[str],
    max_files: int,
    disk_model: str,
) -> Dict[str, Dict]:
    files = wtt.list_csv_files(data_root)
    if max_files and max_files > 0:
        files = files[:max_files]

    selected = set([x for x in selected_features if x])
    model_rows = defaultdict(int)
    model_feature_nonnull = defaultdict(lambda: defaultdict(int))

    for path in files:
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        if "model" not in cols:
            continue

        feature_cols = [c for c in cols if wtt.canonicalize_feature_name(c)]
        if selected:
            feature_cols = [c for c in feature_cols if wtt.canonicalize_feature_name(c) in selected]
        usecols = ["model"] + feature_cols
        if len(usecols) <= 1:
            continue

        df = pd.read_csv(path, usecols=usecols)
        if disk_model:
            df = df[df["model"] == disk_model]
        if df.empty:
            continue

        df["model"] = df["model"].astype(str).str.strip()
        for model, group in df.groupby("model"):
            if not model:
                continue
            model_rows[model] += int(len(group))
            for col in feature_cols:
                canon = wtt.canonicalize_feature_name(col)
                if not canon:
                    continue
                model_feature_nonnull[model][canon] += int(group[col].notna().sum())

    out = {}
    for model, rows in model_rows.items():
        out[model] = {
            "rows": rows,
            "feature_nonnull": dict(model_feature_nonnull[model]),
        }
    return out


def _load_parent_payload(profile_dir: str, medium: str, vendor: str) -> Dict:
    payloads = []
    base_path = os.path.join(profile_dir, "base.yaml")
    medium_path = os.path.join(profile_dir, "medium", f"{medium}.yaml")
    vendor_path = os.path.join(profile_dir, "vendor", f"{vendor}.yaml")

    if os.path.exists(base_path):
        payloads.append(wtt._load_yaml_or_json(base_path))
    if os.path.exists(medium_path):
        payloads.append(wtt._load_yaml_or_json(medium_path))
    if os.path.exists(vendor_path):
        payloads.append(wtt._load_yaml_or_json(vendor_path))
    return wtt.merge_rule_payloads(payloads)


def _default_required_causes(medium: str) -> List[str]:
    if medium == "hdd":
        return ["media", "interface", "temperature", "power", "unknown"]
    return ["media", "interface", "temperature", "power", "workload", "unknown"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", required=True)
    parser.add_argument("--features_path", default=None)
    parser.add_argument("--profile_dir", default=str(LLM_DIR / "rules" / "profiles"))
    parser.add_argument("--out_dir", default=str(LLM_DIR / "rules" / "profiles" / "model_skeletons"))
    parser.add_argument("--min_feature_presence_ratio", type=float, default=0.2)
    parser.add_argument("--min_rows_per_model", type=int, default=1000)
    parser.add_argument("--max_files", type=int, default=0)
    parser.add_argument("--disk_model", default=None)
    parser.add_argument("--max_missing_features", type=int, default=120)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--summary_out", default=None)
    args = parser.parse_args()

    selected_features = _load_selected_features(args.features_path)
    stats = _collect_model_feature_stats(
        args.data_root,
        selected_features,
        args.max_files,
        args.disk_model,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    generated = []
    skipped = []

    for model in sorted(stats.keys()):
        rows = int(stats[model]["rows"])
        if rows < int(args.min_rows_per_model):
            skipped.append({"model": model, "reason": f"rows<{args.min_rows_per_model}", "rows": rows})
            continue

        model_key = wtt._normalize_model_key(model)
        nonnull = stats[model]["feature_nonnull"]
        present = {
            feat
            for feat, cnt in nonnull.items()
            if rows > 0 and (cnt / float(rows)) >= float(args.min_feature_presence_ratio)
        }

        medium = wtt._infer_medium(model, list(present), "auto")
        vendor = wtt._infer_vendor(model, model_key)
        parent = _load_parent_payload(args.profile_dir, medium, vendor)
        parent_features = set((parent.get("features") or {}).keys())
        missing = sorted(present - parent_features)
        if args.max_missing_features > 0:
            missing = missing[: args.max_missing_features]

        out_path = Path(args.out_dir) / f"{model_key}.yaml"
        if out_path.exists() and not args.overwrite:
            skipped.append({"model": model, "reason": "exists", "rows": rows, "path": str(out_path)})
            continue

        skeleton = {
            "meta": {
                "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_data_root": os.path.abspath(args.data_root),
                "model": model,
                "model_key": model_key,
                "rows": rows,
                "medium": medium,
                "vendor": vendor,
                "min_feature_presence_ratio": float(args.min_feature_presence_ratio),
                "parent_layers": ["base", f"medium/{medium}", f"vendor/{vendor}"],
                "present_features_count": len(present),
                "missing_vs_parent_count": len(missing),
            },
            "fewshot": {
                "required_causes": _default_required_causes(medium),
            },
            "features": {
                feat: {
                    "group": "unknown",
                    "weight": 0.70,
                }
                for feat in missing
            },
        }
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(skeleton, f, sort_keys=False, allow_unicode=False)

        generated.append(
            {
                "model": model,
                "model_key": model_key,
                "rows": rows,
                "medium": medium,
                "vendor": vendor,
                "present_features_count": len(present),
                "missing_vs_parent_count": len(missing),
                "path": str(out_path),
            }
        )

    summary = {
        "generated_count": len(generated),
        "skipped_count": len(skipped),
        "generated": generated,
        "skipped": skipped,
    }
    if args.summary_out:
        out_dir = os.path.dirname(args.summary_out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.summary_out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
