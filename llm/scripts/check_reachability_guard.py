#!/usr/bin/env python3
"""
Reachability hard check for LLM injection effectiveness.

Given an experiment CSV and its zeroed-z_llm control CSV:
- If key metrics are identical (within epsilon), treat the experiment as not reachable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


DEFAULT_METRICS = [
    "l_Recall_c1",
    "l_clf_corrct",
    "l_Precision_c1",
    "l_F1_score_c1",
]


def _mean_metrics(df: pd.DataFrame, metrics: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in metrics:
        if m in df.columns:
            out[m] = float(df[m].mean())
    return out


def _read_eval_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" in df.columns:
        df = df[df["date"].notna()].copy()
    return df


def _count_changed_days(df_a: pd.DataFrame, df_b: pd.DataFrame, eps: float, fields: List[str]) -> int:
    if "date" not in df_a.columns or "date" not in df_b.columns:
        return 0
    cols = ["date"] + [f for f in fields if f in df_a.columns and f in df_b.columns]
    if len(cols) <= 1:
        return 0
    ma = df_a[cols].copy()
    mb = df_b[cols].copy()
    merged = ma.merge(mb, on="date", suffixes=("_a", "_b"))
    if merged.empty:
        return 0
    changed = 0
    for _, row in merged.iterrows():
        diff_sum = 0.0
        for f in cols[1:]:
            diff_sum += abs(float(row[f"{f}_a"]) - float(row[f"{f}_b"]))
        if diff_sum > eps:
            changed += 1
    return int(changed)


def run_check(
    exp_csv: Path,
    zero_csv: Path,
    baseline_csv: Path | None,
    eps: float,
    metrics: List[str],
) -> Dict:
    exp_df = _read_eval_csv(exp_csv)
    zero_df = _read_eval_csv(zero_csv)
    if exp_df.empty or zero_df.empty:
        raise ValueError("exp_csv or zero_csv has no valid rows after date filtering")

    exp_mean = _mean_metrics(exp_df, metrics)
    zero_mean = _mean_metrics(zero_df, metrics)

    diffs = {}
    for m in metrics:
        if m in exp_mean and m in zero_mean:
            diffs[m] = float(exp_mean[m] - zero_mean[m])

    max_abs_diff = max((abs(v) for v in diffs.values()), default=0.0)
    changed_days = _count_changed_days(exp_df, zero_df, eps, metrics)
    reachable = bool(max_abs_diff > eps or changed_days > 0)

    result = {
        "exp_csv": str(exp_csv),
        "zero_csv": str(zero_csv),
        "baseline_csv": str(baseline_csv) if baseline_csv else None,
        "epsilon": float(eps),
        "metrics": metrics,
        "exp_mean": exp_mean,
        "zero_mean": zero_mean,
        "exp_minus_zero": diffs,
        "max_abs_diff": float(max_abs_diff),
        "changed_days": int(changed_days),
        "reachable": bool(reachable),
    }

    if baseline_csv is not None and baseline_csv.exists():
        base_df = _read_eval_csv(baseline_csv)
        if not base_df.empty:
            base_mean = _mean_metrics(base_df, metrics)
            result["baseline_mean"] = base_mean
            result["exp_minus_baseline"] = {
                m: float(exp_mean[m] - base_mean[m])
                for m in metrics
                if m in exp_mean and m in base_mean
            }
            result["zero_minus_baseline"] = {
                m: float(zero_mean[m] - base_mean[m])
                for m in metrics
                if m in zero_mean and m in base_mean
            }

    return result


def render_md(payload: Dict) -> str:
    lines = []
    lines.append("# Injection Reachability Guard")
    lines.append("")
    lines.append(f"- exp_csv: `{payload['exp_csv']}`")
    lines.append(f"- zero_csv: `{payload['zero_csv']}`")
    if payload.get("baseline_csv"):
        lines.append(f"- baseline_csv: `{payload['baseline_csv']}`")
    lines.append(f"- epsilon: `{payload['epsilon']}`")
    lines.append("")
    lines.append("## Mean metrics (exp vs zero)")
    lines.append("")
    lines.append("| metric | exp | zero | exp-zero |")
    lines.append("|---|---:|---:|---:|")
    for m in payload.get("metrics", []):
        e = payload.get("exp_mean", {}).get(m, float("nan"))
        z = payload.get("zero_mean", {}).get(m, float("nan"))
        d = payload.get("exp_minus_zero", {}).get(m, float("nan"))
        lines.append(f"| {m} | {e:.6f} | {z:.6f} | {d:+.6f} |")
    lines.append("")
    lines.append(f"- changed_days: `{payload.get('changed_days', 0)}`")
    lines.append(f"- max_abs_diff: `{payload.get('max_abs_diff', 0.0):.6f}`")
    lines.append(f"- reachable: `{payload.get('reachable', False)}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reachability hard check: experiment vs zeroed-z_llm control.")
    parser.add_argument("--exp_csv", required=True)
    parser.add_argument("--zero_csv", required=True)
    parser.add_argument("--baseline_csv", default=None)
    parser.add_argument("--eps", type=float, default=1e-8)
    parser.add_argument(
        "--metrics",
        default=",".join(DEFAULT_METRICS),
        help="Comma-separated metric columns to compare.",
    )
    parser.add_argument("--out_json", default=None)
    parser.add_argument("--out_md", default=None)
    args = parser.parse_args()

    exp_csv = Path(args.exp_csv)
    zero_csv = Path(args.zero_csv)
    baseline_csv = Path(args.baseline_csv) if args.baseline_csv else None
    metrics = [x.strip() for x in str(args.metrics).split(",") if x.strip()]

    payload = run_check(
        exp_csv=exp_csv,
        zero_csv=zero_csv,
        baseline_csv=baseline_csv,
        eps=float(args.eps),
        metrics=metrics,
    )

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_text = render_md(payload)
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md_text, encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
