import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd


def _parse_list(raw: str) -> List[float]:
    out = []
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        out.append(float(token))
    return out


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return num / den


def _daily_metrics(df: pd.DataFrame, pred_col: str) -> pd.DataFrame:
    rows = []
    for day, g in df.groupby("eval_day", sort=True):
        y = g["y_true"].astype(int)
        p = g[pred_col].astype(int)
        tp = int(((p == 1) & (y == 1)).sum())
        fp = int(((p == 1) & (y == 0)).sum())
        tn = int(((p == 0) & (y == 0)).sum())
        fn = int(((p == 0) & (y == 1)).sum())
        recall = _safe_div(tp, tp + fn)
        precision = _safe_div(tp, tp + fp)
        acc = _safe_div(tp + tn, tp + fp + tn + fn)
        fpr = _safe_div(fp, fp + tn)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        rows.append(
            {
                "date": day,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "recall": recall,
                "precision": precision,
                "f1": f1,
                "acc": acc,
                "fpr": fpr,
            }
        )
    return pd.DataFrame(rows)


def _mean_metrics(day_df: pd.DataFrame) -> Dict[str, float]:
    if day_df.empty:
        return {"recall": 0.0, "precision": 0.0, "f1": 0.0, "acc": 0.0, "fpr": 0.0}
    return {
        "recall": float(day_df["recall"].mean() * 100.0),
        "precision": float(day_df["precision"].mean() * 100.0),
        "f1": float(day_df["f1"].mean() * 100.0),
        "acc": float(day_df["acc"].mean() * 100.0),
        "fpr": float(day_df["fpr"].mean() * 100.0),
    }


def _load_nollm_baseline(path: str) -> Dict[str, float]:
    df = pd.read_csv(path)
    df = df[df["date"].notna()]
    return {
        "recall": float(df["l_Recall_c1"].mean()),
        "precision": float(df["l_Precision_c1"].mean()),
        "f1": float(df["l_F1_score_c1"].mean()),
        "acc": float(df["l_clf_corrct"].mean()),
        "fpr": float(df["l_FAR"].mean()),
    }


def _load_trace(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["eval_day", "source_day", "serial_number"]:
        df[col] = df[col].astype(str)
    df["y_true"] = pd.to_numeric(df["true_class"], errors="coerce").fillna(0).astype(int)
    df["pred_model"] = pd.to_numeric(df["pred_class"], errors="coerce").fillna(0).astype(int)
    df["source_day"] = df["source_day"].replace("nan", "")
    df.loc[df["source_day"] == "", "source_day"] = df["eval_day"]
    return df


def _load_cache(path: str) -> pd.DataFrame:
    df = pd.read_json(path, lines=True)
    df["disk_id"] = df["disk_id"].astype(str)
    df["window_end_time"] = pd.to_datetime(df["window_end_time"]).dt.strftime("%Y-%m-%d")
    for col in [
        "llm_q_score",
        "risk_hint",
        "confidence",
        "llm_mapped_event_ratio",
        "label_noise_risk",
        "llm_rule_top_score",
    ]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    if "root_cause_pred" in df.columns:
        root_col = "root_cause_pred"
    elif "root_cause" in df.columns:
        root_col = "root_cause"
    else:
        root_col = None
    if root_col:
        df["root_cause_pred"] = df[root_col].astype(str).str.lower()
    else:
        df["root_cause_pred"] = "unknown"
    keep = [
        "disk_id",
        "window_end_time",
        "llm_q_score",
        "risk_hint",
        "confidence",
        "llm_mapped_event_ratio",
        "label_noise_risk",
        "llm_rule_top_score",
        "root_cause_pred",
    ]
    return df[keep]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate true OR fusion on delayed trace.")
    parser.add_argument("--trace_csv", required=True)
    parser.add_argument("--cache_jsonl", required=True)
    parser.add_argument("--out_csv", required=True)
    parser.add_argument("--out_md", required=True)
    parser.add_argument("--nollm_csv", default="")
    parser.add_argument("--acc_drop_pp", type=float, default=1.0)
    parser.add_argument("--q_values", default="0.35,0.45,0.55,0.65")
    parser.add_argument("--risk_values", default="0.45,0.55,0.65")
    parser.add_argument("--map_values", default="0.3,0.5,0.7")
    parser.add_argument("--rule_values", default="0.35,0.45,0.55")
    parser.add_argument("--noise_values", default="0.6,0.4")
    args = parser.parse_args()

    trace = _load_trace(args.trace_csv)
    cache = _load_cache(args.cache_jsonl)
    merged = trace.merge(
        cache,
        left_on=["serial_number", "source_day"],
        right_on=["disk_id", "window_end_time"],
        how="left",
    )
    for c in [
        "llm_q_score",
        "risk_hint",
        "confidence",
        "llm_mapped_event_ratio",
        "label_noise_risk",
        "llm_rule_top_score",
    ]:
        merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0)
    merged["root_cause_pred"] = merged["root_cause_pred"].fillna("unknown").astype(str).str.lower()

    # Baseline from model trace itself.
    model_day = _daily_metrics(merged, "pred_model")
    model_base = _mean_metrics(model_day)
    if args.nollm_csv:
        nollm_base = _load_nollm_baseline(args.nollm_csv)
    else:
        nollm_base = model_base

    q_values = _parse_list(args.q_values)
    risk_values = _parse_list(args.risk_values)
    map_values = _parse_list(args.map_values)
    rule_values = _parse_list(args.rule_values)
    noise_values = _parse_list(args.noise_values)

    rows: List[Dict] = []
    for q in q_values:
        for risk in risk_values:
            for map_thr in map_values:
                for rule in rule_values:
                    for noise_max in noise_values:
                        trigger = (
                            (merged["llm_q_score"] >= q)
                            & (merged["risk_hint"] >= risk)
                            & (merged["llm_mapped_event_ratio"] >= map_thr)
                            & (merged["label_noise_risk"] <= noise_max)
                            & (merged["root_cause_pred"] != "unknown")
                            & (
                                (merged["llm_rule_top_score"] >= rule)
                                | (merged["confidence"] >= risk)
                            )
                        )
                        merged["pred_fused"] = (
                            (merged["pred_model"].astype(int) == 1) | trigger
                        ).astype(int)
                        day_df = _daily_metrics(merged, "pred_fused")
                        mm = _mean_metrics(day_df)
                        rows.append(
                            {
                                "q": q,
                                "risk": risk,
                                "map_thr": map_thr,
                                "rule": rule,
                                "noise_max": noise_max,
                                "recall": mm["recall"],
                                "precision": mm["precision"],
                                "f1": mm["f1"],
                                "acc": mm["acc"],
                                "fpr": mm["fpr"],
                                "d_recall_vs_model": mm["recall"] - model_base["recall"],
                                "d_acc_vs_model": mm["acc"] - model_base["acc"],
                                "d_recall_vs_nollm": mm["recall"] - nollm_base["recall"],
                                "d_acc_vs_nollm": mm["acc"] - nollm_base["acc"],
                            }
                        )

    out = pd.DataFrame(rows)
    acc_guard = nollm_base["acc"] - float(args.acc_drop_pp)
    out["pass_acc_guard"] = out["acc"] >= acc_guard
    out = out.sort_values(
        ["pass_acc_guard", "recall", "precision"], ascending=[False, False, False]
    )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

    lines = [
        "# True OR Fusion Evaluation",
        "",
        f"- trace model baseline: recall={model_base['recall']:.4f}, acc={model_base['acc']:.4f}",
        f"- no-LLM baseline: recall={nollm_base['recall']:.4f}, acc={nollm_base['acc']:.4f}",
        f"- acc guard: {acc_guard:.4f} (drop <= {float(args.acc_drop_pp):.2f}pp vs no-LLM)",
        "",
        "| q | risk | map | rule | noise<= | recall | precision | f1 | acc | fpr | Δrecall(model) | Δacc(model) | Δrecall(noLLM) | Δacc(noLLM) | guard |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for _, r in out.head(20).iterrows():
        lines.append(
            f"| {r['q']:.2f} | {r['risk']:.2f} | {r['map_thr']:.2f} | {r['rule']:.2f} | {r['noise_max']:.2f} "
            f"| {r['recall']:.4f} | {r['precision']:.4f} | {r['f1']:.4f} | {r['acc']:.4f} | {r['fpr']:.4f} "
            f"| {r['d_recall_vs_model']:+.4f} | {r['d_acc_vs_model']:+.4f} "
            f"| {r['d_recall_vs_nollm']:+.4f} | {r['d_acc_vs_nollm']:+.4f} | {'Y' if r['pass_acc_guard'] else 'N'} |"
        )

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "rows": int(len(merged)),
        "model_base": model_base,
        "nollm_base": nollm_base,
        "acc_guard": acc_guard,
        "top": out.head(1).to_dict(orient="records"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
