#!/usr/bin/env python
import argparse
import csv
import os
from typing import Dict, List, Tuple

import pandas as pd


def _read_metrics(path: str) -> Dict[str, float]:
    if not os.path.exists(path):
        return {"valid": False, "reason": "missing_csv"}

    df = pd.read_csv(path)
    if "date" in df.columns:
        df = df[df["date"].notna()].copy()
    if df.empty:
        return {"valid": False, "reason": "empty_csv"}

    recall_col_candidates = [
        "l_Recall_c1",
        "g_Recall_c1",
        "Recall for class 1 (percent)",
        "Recall",
    ]
    acc_col_candidates = [
        "l_clf_corrct",
        "g_clf_corrct",
        "classifications correct (percent)",
        "Accuracy",
    ]

    recall_col = next((col for col in recall_col_candidates if col in df.columns), None)
    acc_col = next((col for col in acc_col_candidates if col in df.columns), None)

    if recall_col is None or acc_col is None:
        return {"valid": False, "reason": "missing_metric_columns"}

    recall_series = pd.to_numeric(df[recall_col], errors="coerce").dropna()
    acc_series = pd.to_numeric(df[acc_col], errors="coerce").dropna()

    if len(recall_series) == 0 or len(acc_series) == 0:
        return {"valid": False, "reason": "nan_metrics"}

    return {
        "valid": True,
        "rows": int(min(len(recall_series), len(acc_series))),
        "recall_mean": float(recall_series.mean()),
        "acc_mean": float(acc_series.mean()),
        "recall_col": recall_col,
        "acc_col": acc_col,
    }


def _status(llm: Dict[str, float], nollm: Dict[str, float], acc_drop_pp: float) -> Tuple[str, str]:
    if not llm.get("valid"):
        return "N/A", f"llm_invalid:{llm.get('reason', 'unknown')}"
    if not nollm.get("valid"):
        return "N/A", f"nollm_invalid:{nollm.get('reason', 'unknown')}"

    recall_ok = llm["recall_mean"] >= nollm["recall_mean"]
    acc_ok = llm["acc_mean"] >= (nollm["acc_mean"] - float(acc_drop_pp))

    if recall_ok and acc_ok:
        return "PASS", "llm_enabled"
    return "FALLBACK", "nollm"


def _write_csv(path: str, rows: List[Dict]):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fields = [
        "model_key",
        "status",
        "action",
        "llm_recall_mean",
        "nollm_recall_mean",
        "delta_recall",
        "llm_acc_mean",
        "nollm_acc_mean",
        "delta_acc",
        "llm_csv",
        "nollm_csv",
        "llm_valid",
        "nollm_valid",
        "llm_reason",
        "nollm_reason",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})


def _write_md(path: str, rows: List[Dict], acc_drop_pp: float):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    lines = []
    lines.append("# LLM vs no-LLM 逐盘型鲁棒评估")
    lines.append("")
    lines.append(f"- 验收约束: Recall(LLM) >= Recall(no-LLM), ACC(LLM) >= ACC(no-LLM) - {acc_drop_pp:.2f}pp")
    lines.append("")
    lines.append("| model | status | action | recall_llm | recall_nollm | delta_recall | acc_llm | acc_nollm | delta_acc |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            "| {model} | {status} | {action} | {r1:.4f} | {r0:.4f} | {dr:+.4f} | {a1:.4f} | {a0:.4f} | {da:+.4f} |".format(
                model=row.get("model_key", ""),
                status=row.get("status", ""),
                action=row.get("action", ""),
                r1=float(row.get("llm_recall_mean", 0.0) or 0.0),
                r0=float(row.get("nollm_recall_mean", 0.0) or 0.0),
                dr=float(row.get("delta_recall", 0.0) or 0.0),
                a1=float(row.get("llm_acc_mean", 0.0) or 0.0),
                a0=float(row.get("nollm_acc_mean", 0.0) or 0.0),
                da=float(row.get("delta_acc", 0.0) or 0.0),
            )
        )

    lines.append("")
    lines.append("## N/A / 回退说明")
    for row in rows:
        if row.get("status") == "N/A":
            lines.append(
                "- {model}: llm={llm_reason}, nollm={nollm_reason}".format(
                    model=row.get("model_key", ""),
                    llm_reason=row.get("llm_reason", ""),
                    nollm_reason=row.get("nollm_reason", ""),
                )
            )
        elif row.get("status") == "FALLBACK":
            lines.append(
                "- {model}: recall/acc 未同时满足约束，建议上线回退 no-LLM".format(
                    model=row.get("model_key", "")
                )
            )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate LLM vs no-LLM by model with hard acceptance constraints.")
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="model_key,llm_csv,nollm_csv (repeatable)",
    )
    parser.add_argument("--acc_drop_pp", type=float, default=1.0)
    parser.add_argument("--out_csv", default="docs/llm_robust_eval_report.csv")
    parser.add_argument("--out_md", default="docs/llm_robust_eval_report.md")
    args = parser.parse_args()

    if not args.pair:
        raise ValueError("At least one --pair is required")

    rows: List[Dict] = []
    for raw in args.pair:
        parts = [item.strip() for item in str(raw).split(",")]
        if len(parts) != 3:
            raise ValueError(f"Invalid --pair: {raw}")
        model_key, llm_csv, nollm_csv = parts

        llm_metrics = _read_metrics(llm_csv)
        nollm_metrics = _read_metrics(nollm_csv)
        status, action = _status(llm_metrics, nollm_metrics, float(args.acc_drop_pp))

        llm_recall = float(llm_metrics.get("recall_mean", 0.0) or 0.0)
        nollm_recall = float(nollm_metrics.get("recall_mean", 0.0) or 0.0)
        llm_acc = float(llm_metrics.get("acc_mean", 0.0) or 0.0)
        nollm_acc = float(nollm_metrics.get("acc_mean", 0.0) or 0.0)

        rows.append(
            {
                "model_key": model_key,
                "status": status,
                "action": action,
                "llm_recall_mean": llm_recall,
                "nollm_recall_mean": nollm_recall,
                "delta_recall": llm_recall - nollm_recall,
                "llm_acc_mean": llm_acc,
                "nollm_acc_mean": nollm_acc,
                "delta_acc": llm_acc - nollm_acc,
                "llm_csv": llm_csv,
                "nollm_csv": nollm_csv,
                "llm_valid": bool(llm_metrics.get("valid", False)),
                "nollm_valid": bool(nollm_metrics.get("valid", False)),
                "llm_reason": llm_metrics.get("reason", ""),
                "nollm_reason": nollm_metrics.get("reason", ""),
            }
        )

    rows.sort(key=lambda row: row["model_key"])
    _write_csv(args.out_csv, rows)
    _write_md(args.out_md, rows, float(args.acc_drop_pp))


if __name__ == "__main__":
    main()
