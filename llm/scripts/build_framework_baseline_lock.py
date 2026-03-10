#!/usr/bin/env python
import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Build framework baseline lock table from robust eval report.")
    parser.add_argument("--in_csv", default="docs/llm_robust_eval_report_v2.csv")
    parser.add_argument("--out_csv", default="docs/framework_v1_baseline_lock.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.in_csv)
    keep_cols = [
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
    ]
    out = df[[c for c in keep_cols if c in df.columns]].copy()
    out["acc_guard_floor"] = out["nollm_acc_mean"] - 1.0
    out["recall_target_floor"] = out["nollm_recall_mean"]
    out.to_csv(args.out_csv, index=False)
    print(f"wrote {args.out_csv} rows={len(out)}")


if __name__ == "__main__":
    main()
