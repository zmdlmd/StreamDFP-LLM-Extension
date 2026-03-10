#!/usr/bin/env python
import argparse
import json
from typing import Dict, List


REQUIRED_PREFIXES = [
    "WINDOW:",
    "DATA_QUALITY:",
    "RULE_SCORE:",
    "RULE_TOP2:",
    "ALLOWED_EVENT_FEATURES:",
    "ANOMALY_TABLE:",
    "CAUSE_EVIDENCE:",
    "RULE_PRED:",
]

REQUIRED_ANOMALY_KEYS = {
    "feat",
    "src",
    "mode",
    "dir",
    "baseline",
    "current",
    "delta_pct",
    "abnormal_ratio",
    "persistence",
    "slope3",
    "slope14",
    "burst_ratio",
    "severity",
    "group",
}


def _parse_anomaly_line(line: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    payload = line.strip()[2:].strip()
    if payload.lower() == "none":
        return out
    for token in payload.split("|"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        out[str(key).strip().lower()] = str(value).strip()
    return out


def validate_summary(summary: str) -> Dict[str, object]:
    lines = [str(row).strip() for row in str(summary or "").splitlines() if str(row).strip()]
    ok_prefix = {prefix: False for prefix in REQUIRED_PREFIXES}
    for line in lines:
        for prefix in REQUIRED_PREFIXES:
            if line.startswith(prefix):
                ok_prefix[prefix] = True

    anomaly_rows: List[Dict[str, str]] = []
    in_table = False
    for line in lines:
        if line.startswith("ANOMALY_TABLE:"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("- "):
            break
        parsed = _parse_anomaly_line(line)
        if parsed:
            anomaly_rows.append(parsed)
        elif line.strip().lower() == "- none":
            break

    malformed_rows = 0
    for row in anomaly_rows:
        if not REQUIRED_ANOMALY_KEYS.issubset(set(row.keys())):
            malformed_rows += 1

    missing_blocks = [k for k, v in ok_prefix.items() if not v]
    return {
        "ok": len(missing_blocks) == 0 and malformed_rows == 0,
        "missing_blocks": missing_blocks,
        "anomaly_rows": len(anomaly_rows),
        "malformed_rows": malformed_rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate structured_v2 summary_text block completeness.")
    parser.add_argument("--window_text_path", required=True, help="window_text jsonl")
    parser.add_argument("--max_rows", type=int, default=32)
    args = parser.parse_args()

    total = 0
    passed = 0
    failed = 0
    failed_samples = []
    with open(args.window_text_path, "r", encoding="utf-8") as f:
        for line in f:
            if total >= max(1, int(args.max_rows)):
                break
            row = json.loads(line)
            summary = row.get("summary_text", "")
            result = validate_summary(summary)
            total += 1
            if bool(result.get("ok", False)):
                passed += 1
            else:
                failed += 1
                failed_samples.append(
                    {
                        "disk_id": row.get("disk_id"),
                        "window_end_time": row.get("window_end_time"),
                        **result,
                    }
                )

    print(
        json.dumps(
            {
                "window_text_path": args.window_text_path,
                "checked": total,
                "passed": passed,
                "failed": failed,
                "pass_ratio": (passed / float(total)) if total else 0.0,
                "failed_samples_top5": failed_samples[:5],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
