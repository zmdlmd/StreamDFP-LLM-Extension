#!/usr/bin/env python3
"""
Build per-model feature contracts from training-period data only.

The contract is a plain text file listing one feature name per line, which can
be consumed directly by:
  - llm/window_to_text.py --features_path
  - pyloader/run.py -c
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


def normalize_model_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def list_csv_files(data_root: Path) -> List[Path]:
    files = sorted(data_root.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in: {data_root}")
    return files


def parse_file_date(path: Path, date_format: str) -> datetime:
    return datetime.strptime(path.stem, date_format)


def parse_list(raw: str) -> List[str]:
    return [x.strip() for x in str(raw).split(",") if x.strip()]


@dataclass
class FeatureStats:
    nonnull: int = 0
    n_num: int = 0
    sum_num: float = 0.0
    sumsq_num: float = 0.0
    fail_nonnull: int = 0

    def update(self, values: pd.Series, fail_mask: Optional[pd.Series]) -> None:
        notna_mask = values.notna()
        self.nonnull += int(notna_mask.sum())

        num = pd.to_numeric(values, errors="coerce")
        num_valid = num.dropna()
        if not num_valid.empty:
            arr = num_valid.to_numpy(dtype=float)
            self.n_num += int(arr.size)
            self.sum_num += float(arr.sum())
            self.sumsq_num += float((arr * arr).sum())

        if fail_mask is not None and bool(fail_mask.any()):
            self.fail_nonnull += int((notna_mask & fail_mask).sum())

    def variance(self) -> float:
        if self.n_num <= 1:
            return 0.0
        # sample variance
        numer = self.sumsq_num - (self.sum_num * self.sum_num) / float(self.n_num)
        if numer <= 0.0:
            return 0.0
        return numer / float(self.n_num - 1)


@dataclass
class ModelStats:
    rows: int = 0
    fail_rows: int = 0
    features: Dict[str, FeatureStats] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.features is None:
            self.features = {}


def init_model_stats(models: Iterable[str], features: Iterable[str]) -> Dict[str, ModelStats]:
    out: Dict[str, ModelStats] = {}
    feat_list = list(features)
    for model in models:
        st = ModelStats()
        st.features = {f: FeatureStats() for f in feat_list}
        out[model] = st
    return out


def discover_models(
    data_root: Path,
    date_format: str,
    train_start: datetime,
    train_end: datetime,
) -> List[str]:
    discovered = set()
    for path in list_csv_files(data_root):
        file_date = parse_file_date(path, date_format)
        if file_date < train_start or file_date > train_end:
            continue
        cols = pd.read_csv(path, nrows=0).columns.tolist()
        if "model" not in cols:
            continue
        df = pd.read_csv(path, usecols=["model"])
        discovered.update(str(x) for x in df["model"].dropna().unique().tolist())
    return sorted(discovered)


def collect_stats(
    data_root: Path,
    features: List[str],
    models: List[str],
    date_format: str,
    train_start: datetime,
    train_end: datetime,
) -> Dict[str, ModelStats]:
    stats = init_model_stats(models, features)
    target_set = set(models)

    for path in list_csv_files(data_root):
        file_date = parse_file_date(path, date_format)
        if file_date < train_start or file_date > train_end:
            continue

        header_cols = pd.read_csv(path, nrows=0).columns.tolist()
        if "model" not in header_cols:
            continue

        use_cols = ["model"] + [f for f in features if f in header_cols]
        has_failure = "failure" in header_cols
        if has_failure:
            use_cols.append("failure")

        df = pd.read_csv(path, usecols=use_cols)
        if df.empty:
            continue

        for model_name, sub in df.groupby("model"):
            model_name = str(model_name)
            if model_name not in target_set:
                continue
            if sub.empty:
                continue

            m = stats[model_name]
            m.rows += int(len(sub))
            fail_mask: Optional[pd.Series] = None
            if has_failure:
                fail_mask = pd.to_numeric(sub["failure"], errors="coerce").fillna(0).astype(int) == 1
                m.fail_rows += int(fail_mask.sum())

            for feat in features:
                if feat not in sub.columns:
                    continue
                m.features[feat].update(sub[feat], fail_mask)

    return stats


def choose_features(
    features: List[str],
    stats: ModelStats,
    min_non_null_ratio: float,
    fallback_non_null_ratios: List[float],
    min_features: int,
    min_variance: float,
) -> Tuple[List[str], Dict[str, float], float, str]:
    if stats.rows <= 0:
        return [], {}, 0.0, "no_rows"

    ratios: Dict[str, float] = {}
    variances: Dict[str, float] = {}
    for feat in features:
        fs = stats.features[feat]
        ratios[feat] = float(fs.nonnull) / float(stats.rows)
        variances[feat] = fs.variance()

    thresholds = [min_non_null_ratio] + [x for x in fallback_non_null_ratios if x < min_non_null_ratio]
    picked: List[str] = []
    used_threshold = min_non_null_ratio
    mode = "threshold"

    for th in thresholds:
        cand = [
            f
            for f in features
            if ratios[f] >= th and variances[f] >= min_variance
        ]
        if len(cand) >= min_features:
            picked = cand
            used_threshold = th
            mode = "threshold"
            break

    if not picked:
        # Backstop: pick top-k by (coverage, variance) while preserving feature order.
        scored = sorted(
            features,
            key=lambda f: (ratios[f], variances[f]),
            reverse=True,
        )
        top = set(scored[: max(min_features, 1)])
        picked = [f for f in features if f in top and ratios[f] > 0.0]
        if not picked and scored:
            picked = [scored[0]]
        used_threshold = 0.0
        mode = "topk_backstop"

    return picked, ratios, used_threshold, mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-model feature contracts")
    parser.add_argument("--data_root", required=True, help="Directory with daily CSV files")
    parser.add_argument("--features_path", required=True, help="Candidate feature list (one per line)")
    parser.add_argument("--date_format", default="%Y-%m-%d", help="Filename date format")
    parser.add_argument("--train_start_date", required=True, help="Training start date")
    parser.add_argument("--train_end_date", required=True, help="Training end date")
    parser.add_argument(
        "--disk_models",
        required=True,
        help='Comma-separated model names, or "all" to auto-discover in training period',
    )
    parser.add_argument(
        "--out_dir",
        default="pyloader/features_erg/contracts",
        help="Output directory for <model_key>.txt contracts",
    )
    parser.add_argument("--summary_out", default="", help="Optional summary JSON path")
    parser.add_argument("--min_non_null_ratio", type=float, default=0.99)
    parser.add_argument("--fallback_non_null_ratios", default="0.95,0.9,0.8,0.5")
    parser.add_argument("--min_features", type=int, default=5)
    parser.add_argument("--min_variance", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing contracts")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_start = datetime.strptime(args.train_start_date, "%Y-%m-%d")
    train_end = datetime.strptime(args.train_end_date, "%Y-%m-%d")
    if train_end < train_start:
        raise ValueError("train_end_date must be >= train_start_date")

    with open(args.features_path, "r", encoding="utf-8") as f:
        features = [x.strip() for x in f if x.strip()]
    if not features:
        raise ValueError(f"No features loaded from: {args.features_path}")

    disk_models_raw = args.disk_models.strip()
    if disk_models_raw.lower() == "all":
        models = discover_models(
            data_root=data_root,
            date_format=args.date_format,
            train_start=train_start,
            train_end=train_end,
        )
    else:
        models = parse_list(disk_models_raw)
    if not models:
        raise ValueError("No disk models to process")

    fallback_ratios = [float(x) for x in parse_list(args.fallback_non_null_ratios)]
    stats = collect_stats(
        data_root=data_root,
        features=features,
        models=models,
        date_format=args.date_format,
        train_start=train_start,
        train_end=train_end,
    )

    summary = {
        "data_root": str(data_root),
        "features_path": str(args.features_path),
        "date_format": args.date_format,
        "train_start_date": args.train_start_date,
        "train_end_date": args.train_end_date,
        "min_non_null_ratio": args.min_non_null_ratio,
        "fallback_non_null_ratios": fallback_ratios,
        "min_features": args.min_features,
        "min_variance": args.min_variance,
        "models": [],
    }

    for model in models:
        key = normalize_model_key(model)
        out_path = out_dir / f"{key}.txt"
        model_stats = stats.get(model, ModelStats())
        selected, ratios, used_threshold, mode = choose_features(
            features=features,
            stats=model_stats,
            min_non_null_ratio=float(args.min_non_null_ratio),
            fallback_non_null_ratios=fallback_ratios,
            min_features=int(args.min_features),
            min_variance=float(args.min_variance),
        )

        if out_path.exists() and not args.overwrite:
            pass
        else:
            out_path.write_text("\n".join(selected) + ("\n" if selected else ""), encoding="utf-8")

        dropped_missing = []
        dropped_constant = []
        for feat in features:
            if feat in selected:
                continue
            ratio = ratios.get(feat, 0.0)
            var = model_stats.features.get(feat, FeatureStats()).variance()
            if ratio < used_threshold and mode == "threshold":
                dropped_missing.append((feat, ratio))
            elif var <= args.min_variance:
                dropped_constant.append((feat, var))

        summary["models"].append(
            {
                "disk_model": model,
                "model_key": key,
                "rows": int(model_stats.rows),
                "fail_rows": int(model_stats.fail_rows),
                "selected_feature_count": len(selected),
                "selected_feature_path": str(out_path),
                "selected_non_null_threshold": used_threshold,
                "selection_mode": mode,
                "selected_features": selected,
                "dropped_missing_top20": sorted(dropped_missing, key=lambda x: x[1])[:20],
                "dropped_constant_top20": dropped_constant[:20],
            }
        )
        print(
            f"[contract] model={model} key={key} rows={model_stats.rows} "
            f"fail_rows={model_stats.fail_rows} selected={len(selected)} "
            f"mode={mode} threshold={used_threshold:.3f} path={out_path}"
        )

    if args.summary_out:
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[contract] wrote summary: {summary_path}")
if __name__ == "__main__":
    main()
