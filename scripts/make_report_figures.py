#!/usr/bin/env python3
"""Generate report-ready PNG figures from retained CSV summaries."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "docs" / "tables"
REPORTS_DIR = ROOT / "docs" / "reports"
OUTPUT_DIR = REPORTS_DIR / "figures"

HDD_COMPARE_CSV = TABLES_DIR / "qwen3_instruct_vs_qwen35_4b_vs_qwen35_plus_comparison_20260315.csv"
MC1_PHASE2_CSV = TABLES_DIR / "mc1_phase2_quality_comparison_stratified_v2_20260319.csv"
MC1_PHASE3_CSV = TABLES_DIR / "mc1_phase3_comparison_stratified_v2_20260323.csv"


def configure_matplotlib() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linestyle": "--",
            "legend.frameon": False,
        }
    )


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def format_bar_labels(ax: plt.Axes, bars, fmt: str = "{:.1f}", dy: float = 0.4) -> None:
    for bar in bars:
        height = bar.get_height()
        if math.isnan(height):
            continue
        y = height + dy if height >= 0 else height - dy * 1.8
        va = "bottom" if height >= 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y,
            fmt.format(height),
            ha="center",
            va=va,
            fontsize=9,
        )


def prettify_model_name(name: str) -> str:
    mapping = {
        "Qwen3-4B-Instruct-2507": "Qwen3-Instruct",
        "Qwen3.5-4B": "Qwen3.5-4B",
        "Qwen3.5-Plus": "Qwen3.5-Plus",
        "Qwen3.5-4B (tp2+eager)": "Qwen3.5-4B",
    }
    return mapping.get(name, name)


def make_hdd_model_summary() -> Path:
    df = pd.read_csv(HDD_COMPARE_CSV)
    df = df[df["model_key"] != "mc1_pilot20k"]

    models = [
        ("Qwen3-Instruct", "action_qwen3_instruct", "delta_recall_qwen3_instruct"),
        ("Qwen3.5-4B", "action_qwen35_4b", "delta_recall_qwen35_4b"),
        ("Qwen3.5-Plus", "action_qwen35_plus", "delta_recall_qwen35_plus"),
    ]

    enabled_counts = []
    avg_delta_recalls = []
    for label, action_col, delta_col in models:
        enabled = df[action_col] == "llm_enabled"
        enabled_counts.append(int(enabled.sum()))
        avg_delta_recalls.append(float(df.loc[enabled, delta_col].mean()))

    colors = ["#375a7f", "#c97b2a", "#2d936c"]
    labels = [m[0] for m in models]
    x = np.arange(len(labels))

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    bars0 = axes[0].bar(x, enabled_counts, color=colors, width=0.62)
    axes[0].set_title("Enabled HDD Models")
    axes[0].set_ylabel("Count")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, max(enabled_counts) + 2)
    format_bar_labels(axes[0], bars0, "{:.0f}", dy=0.1)

    bars1 = axes[1].bar(x, avg_delta_recalls, color=colors, width=0.62)
    axes[1].set_title("Average Delta Recall on Accepted HDD Models")
    axes[1].set_ylabel("Delta Recall (pp)")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylim(0, max(avg_delta_recalls) + 4)
    format_bar_labels(axes[1], bars1, "{:.2f}", dy=0.25)

    fig.suptitle("HDD Cross-Model Summary", y=1.04, fontsize=16)
    return save_figure(fig, "fig_hdd_model_summary.png")


def make_hdd_per_model_delta_recall() -> Path:
    df = pd.read_csv(HDD_COMPARE_CSV)
    df = df[df["model_key"] != "mc1_pilot20k"].copy()

    short_labels = {
        "hds5c3030ala630": "hds5c3030",
        "hds723030ala640": "hds723030",
        "hgsthms5c4040ale640": "hgst-hms",
        "hi7": "hi7",
        "hitachihds5c4040ale630": "hitachi-hds",
        "hms5c4040ble640": "hms5c4040",
        "st3000dm001": "st3000",
        "st31500341as": "st315003",
        "st31500541as": "st315005",
        "st4000dm000": "st4000",
        "wdcwd10eads": "wd10eads",
        "wdcwd30efrx": "wd30efrx",
    }
    df["label"] = df["model_key"].map(short_labels).fillna(df["model_key"])

    x = np.arange(len(df))
    width = 0.26
    colors = ["#375a7f", "#c97b2a", "#2d936c"]

    fig, ax = plt.subplots(figsize=(14, 5.8))
    bars0 = ax.bar(x - width, df["delta_recall_qwen3_instruct"], width, label="Qwen3-Instruct", color=colors[0])
    bars1 = ax.bar(x, df["delta_recall_qwen35_4b"], width, label="Qwen3.5-4B", color=colors[1])
    bars2 = ax.bar(x + width, df["delta_recall_qwen35_plus"], width, label="Qwen3.5-Plus", color=colors[2])

    ax.axhline(0, color="#444444", linewidth=1.0)
    ax.set_title("HDD Delta Recall by Disk Model")
    ax.set_ylabel("Delta Recall (pp)")
    ax.set_xticks(x, df["label"], rotation=30, ha="right")
    ax.legend(ncol=3, loc="upper right")

    for bars in (bars0, bars1, bars2):
        for bar in bars:
            height = bar.get_height()
            if abs(height) >= 20:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + (1.1 if height >= 0 else -1.7),
                    f"{height:.1f}",
                    ha="center",
                    va="bottom" if height >= 0 else "top",
                    fontsize=7,
                )

    fig.suptitle("Disk-Model-Level HDD Comparison Across Three Candidate Models", y=1.02, fontsize=16)
    return save_figure(fig, "fig_hdd_per_model_delta_recall.png")


def make_mc1_phase2_quality() -> Path:
    df = pd.read_csv(MC1_PHASE2_CSV).copy()
    df["short_model"] = df["model"].map(prettify_model_name)
    colors = ["#c97b2a", "#2d936c", "#375a7f"]

    x = np.arange(len(df))
    width = 0.34

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    bars0 = axes[0].bar(x - width / 2, df["non_unknown_pct"], width, label="Non-unknown %", color="#2d936c")
    bars1 = axes[0].bar(x + width / 2, df["mapped_event_ratio_pct"], width, label="Mapped event %", color="#375a7f")
    axes[0].set_title("MC1 Phase2 Coverage Quality")
    axes[0].set_ylabel("Percentage")
    axes[0].set_xticks(x, df["short_model"], rotation=15, ha="right")
    axes[0].set_ylim(0, 100)
    axes[0].legend(loc="upper left")
    format_bar_labels(axes[0], bars0, "{:.2f}", dy=0.8)
    format_bar_labels(axes[0], bars1, "{:.2f}", dy=0.8)

    score_cols = ["avg_confidence", "avg_risk_hint", "avg_llm_q_score"]
    score_labels = ["Avg confidence", "Avg risk hint", "Avg llm_q_score"]
    score_x = np.arange(len(score_cols))
    model_width = 0.23
    for i, (_, row) in enumerate(df.iterrows()):
        vals = [row[c] for c in score_cols]
        axes[1].bar(score_x + (i - 1) * model_width, vals, model_width, label=row["short_model"], color=colors[i])
    axes[1].set_title("MC1 Phase2 Scalar Quality Scores")
    axes[1].set_ylabel("Score")
    axes[1].set_xticks(score_x, score_labels, rotation=15, ha="right")
    axes[1].set_ylim(0, 1.0)
    axes[1].legend(loc="upper left")

    fig.suptitle("MC1 Phase2 Quality Comparison on Repaired stratified_v2 Input", y=1.04, fontsize=16)
    return save_figure(fig, "fig_mc1_phase2_quality.png")


def parse_status_counts(text: str) -> dict[str, int]:
    result = {"ok": 0, "degenerate_skip": 0, "existing": 0}
    for part in str(text).split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in result:
            result[key] = int(value)
    return result


def make_mc1_phase3_summary() -> Path:
    df = pd.read_csv(MC1_PHASE3_CSV).copy()
    df["short_model"] = df["model"].map(prettify_model_name)

    parsed = df["status_counts"].apply(parse_status_counts)
    df["ok_count"] = parsed.apply(lambda x: x["ok"])
    df["degenerate_skip_count"] = parsed.apply(lambda x: x["degenerate_skip"])
    df["existing_count"] = parsed.apply(lambda x: x["existing"])

    x = np.arange(len(df))
    colors = ["#c97b2a", "#2d936c", "#375a7f"]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    width = 0.36
    bars0 = axes[0].bar(x - width / 2, df["delta_recall_vs_nollm"], width, label="Delta Recall", color="#2d936c")
    bars1 = axes[0].bar(x + width / 2, df["delta_acc_vs_nollm"], width, label="Delta ACC", color="#375a7f")
    axes[0].set_title("MC1 Best Phase3 Improvement vs Baseline")
    axes[0].set_ylabel("Improvement")
    axes[0].set_xticks(x, df["short_model"], rotation=15, ha="right")
    axes[0].legend(loc="upper left")
    format_bar_labels(axes[0], bars0, "{:.3f}", dy=0.05)
    format_bar_labels(axes[0], bars1, "{:.3f}", dy=0.02)

    stack_bottom = np.zeros(len(df))
    for col, label, color in [
        ("existing_count", "Existing", "#adb5bd"),
        ("ok_count", "OK", "#2d936c"),
        ("degenerate_skip_count", "Degenerate skip", "#c97b2a"),
    ]:
        axes[1].bar(x, df[col], bottom=stack_bottom, label=label, color=color, width=0.55)
        stack_bottom += df[col].to_numpy()
    axes[1].set_title("MC1 Phase3 Execution Status by Model")
    axes[1].set_ylabel("Combination count")
    axes[1].set_xticks(x, df["short_model"], rotation=15, ha="right")
    axes[1].legend(loc="upper left")

    fig.suptitle("MC1 Phase3 Best Result and Execution Profile", y=1.04, fontsize=16)
    return save_figure(fig, "fig_mc1_phase3_summary.png")


def main() -> None:
    configure_matplotlib()
    ensure_output_dir()

    outputs = [
        make_hdd_model_summary(),
        make_hdd_per_model_delta_recall(),
        make_mc1_phase2_quality(),
        make_mc1_phase3_summary(),
    ]

    print("Generated figures:")
    for path in outputs:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
