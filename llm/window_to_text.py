import argparse
import heapq
import json
import math
import os
import random
import re
import sys
import time
from collections import deque
from copy import deepcopy
from datetime import datetime
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


ROOT_CAUSES = ["media", "interface", "temperature", "power", "workload", "unknown"]
ROOT_CAUSE_SET = set(ROOT_CAUSES)


def canonicalize_feature_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    text = text.replace(" ", "_").replace("-", "_")
    text = re.sub(r"_+", "_", text)

    # r_199 / n_199
    m = re.match(r"^([rn])_?(\d+)$", text)
    if m:
        suffix = "raw" if m.group(1) == "r" else "normalized"
        return f"smart_{int(m.group(2))}_{suffix}"

    # raw_199 / normalized_199 / norm_199
    m = re.match(r"^(raw|normalized|norm)_?(\d+)$", text)
    if m:
        suffix = "raw" if m.group(1) == "raw" else "normalized"
        return f"smart_{int(m.group(2))}_{suffix}"

    # smart_199_raw / smart199raw / smart_199_n
    m = re.match(r"^smart_?(\d+)(?:_?(raw|normalized|norm|n|r))?$", text)
    if m:
        tag = (m.group(2) or "raw").lower()
        suffix = "normalized" if tag in ("normalized", "norm", "n") else "raw"
        return f"smart_{int(m.group(1))}_{suffix}"

    return text


def _feature_column_priority(raw_col: str, canonical_col: str) -> int:
    text = str(raw_col or "").strip().lower()
    if text == canonical_col:
        return 4
    if text.startswith("smart_"):
        return 3
    if re.match(r"^[rn]_?\d+$", text):
        return 2
    return 1


DEFAULT_RAW_RULE = {
    "label": "",
    "direction": "high_bad",
    "group": "unknown",
    "min_abs_delta": 1.0,
    "min_pct_delta": 0.10,
    "weight": 0.70,
    "mode": "level",
    "min_points": 3,
    "cap": 1.0,
    "cooldown_days": 0,
}
DEFAULT_NORMALIZED_RULE = {
    "label": "",
    "direction": "low_bad",
    "group": "unknown",
    "min_abs_delta": 1.0,
    "min_pct_delta": 0.02,
    "weight": 0.70,
    "mode": "level",
    "min_points": 3,
    "cap": 1.0,
    "cooldown_days": 0,
}

# Hard rules used to convert numeric windows into natural-language diagnostics.
DEFAULT_FEATURE_RULES = {
    "smart_5_raw": {
        "label": "SMART 5 Reallocated Sector Count(raw)",
        "direction": "high_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.20,
        "weight": 1.30,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_197_raw": {
        "label": "SMART 197 Current Pending Sector(raw)",
        "direction": "high_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.20,
        "weight": 1.20,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_198_raw": {
        "label": "SMART 198 Offline Uncorrectable(raw)",
        "direction": "high_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.20,
        "weight": 1.20,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_199_raw": {
        "label": "SMART 199 UDMA CRC Error Count(raw)",
        "direction": "high_bad",
        "group": "interface",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.20,
        "weight": 1.10,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_188_raw": {
        "label": "SMART 188 Command Timeout(raw)",
        "direction": "high_bad",
        "group": "interface",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.20,
        "weight": 1.10,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_194_raw": {
        "label": "SMART 194 Temperature(raw)",
        "direction": "high_bad",
        "group": "temperature",
        "min_abs_delta": 2.0,
        "min_pct_delta": 0.08,
        "weight": 1.00,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 1,
    },
    "smart_192_raw": {
        "label": "SMART 192 Power-off Retract Count(raw)",
        "direction": "high_bad",
        "group": "power",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.15,
        "weight": 1.00,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_193_raw": {
        "label": "SMART 193 Load/Unload Cycle Count(raw)",
        "direction": "high_bad",
        "group": "power",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.15,
        "weight": 1.00,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_9_raw": {
        "label": "SMART 9 Power-on Hours(raw)",
        "direction": "high_warn",
        "group": "workload",
        "min_abs_delta": 6.0,
        "min_pct_delta": 0.30,
        "weight": 0.55,
        "mode": "delta",
        "min_points": 6,
        "cap": 0.9,
        "cooldown_days": 1,
    },
    "smart_5_normalized": {
        "label": "SMART 5 Normalized Health",
        "direction": "low_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.02,
        "weight": 1.20,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_197_normalized": {
        "label": "SMART 197 Normalized Health",
        "direction": "low_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.02,
        "weight": 1.20,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_198_normalized": {
        "label": "SMART 198 Normalized Health",
        "direction": "low_bad",
        "group": "media",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.02,
        "weight": 1.10,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_199_normalized": {
        "label": "SMART 199 Normalized Health",
        "direction": "low_bad",
        "group": "interface",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.02,
        "weight": 1.00,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
    "smart_194_normalized": {
        "label": "SMART 194 Normalized Health",
        "direction": "low_bad",
        "group": "temperature",
        "min_abs_delta": 1.0,
        "min_pct_delta": 0.02,
        "weight": 1.00,
        "mode": "level",
        "min_points": 4,
        "cap": 1.0,
        "cooldown_days": 0,
    },
}

DEFAULT_SCORING_CONFIG = {
    "top_k_per_group": 3,
    "low_threshold": 0.30,
    "margin_threshold": 0.08,
    "abnormal_multiplier": 1.00,
    "watch_multiplier": 0.45,
    "watch_ratio_threshold": 0.20,
    "watch_severity_threshold": 0.15,
    "recency_horizon_days": 14,
    "workload_support_threshold": 0.10,
    "workload_min_support": 1,
    "workload_min_feature_signals": 1,
}
DEFAULT_SUMMARY_CONFIG = {
    "top_k": 8,
    "include_rule_conclusion": False,
    "summary_schema": "legacy",
    "anomaly_top_k": 8,
    "emit_legacy_text": False,
}

DEFAULT_RULE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "rules", "default.yaml")
DEFAULT_RULE_PROFILE_DIR = os.path.join(os.path.dirname(__file__), "rules", "profiles")
PROFILE_MEDIA = {"hdd", "ssd"}
SUMMARY_SCHEMAS = {"legacy", "structured_v2"}

ACTIVE_DEFAULT_RULES = {
    "raw": deepcopy(DEFAULT_RAW_RULE),
    "normalized": deepcopy(DEFAULT_NORMALIZED_RULE),
}
ACTIVE_FEATURE_RULES = deepcopy(DEFAULT_FEATURE_RULES)
ACTIVE_SCORING = deepcopy(DEFAULT_SCORING_CONFIG)
ACTIVE_SUMMARY = deepcopy(DEFAULT_SUMMARY_CONFIG)


def _deep_merge_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(overlay, dict):
        return out
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def merge_rule_payloads(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        merged = _deep_merge_dict(merged, payload)
    return merged


def _normalize_model_key(model: Optional[str]) -> str:
    text = (model or "").strip().lower()
    if not text:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _infer_medium(disk_model: Optional[str], features: List[str], override: str) -> str:
    ov = str(override or "auto").strip().lower()
    if ov in PROFILE_MEDIA:
        return ov

    model_text = (disk_model or "").strip().lower()
    ssd_keywords = ("ssd", "nvme", "mc1", "ma1", "ma2", "alibaba")
    hdd_keywords = ("hdd", "hds", "hitachi", "hgst", "wd", "seagate", "st")
    if any(k in model_text for k in ssd_keywords):
        return "ssd"
    if any(k in model_text for k in hdd_keywords):
        return "hdd"

    has_nr = any(str(f).strip().lower().startswith(("n_", "r_")) for f in features)
    has_smart = any(str(f).strip().lower().startswith("smart_") for f in features)
    if has_nr and not has_smart:
        return "ssd"
    if has_smart and not has_nr:
        return "hdd"
    if has_nr and has_smart:
        return "ssd"
    return "hdd"


def _infer_vendor(disk_model: Optional[str], model_key: str) -> str:
    model_text = (disk_model or "").strip().lower()
    token_match = re.match(r"[a-z0-9]+", model_text)
    first_token = token_match.group(0) if token_match else ""

    if model_key.startswith(("mc1", "ma1", "ma2")):
        return "alibaba"

    alias = {
        "hitachi": "hitachi",
        "hgst": "hitachi",
        "alibaba": "alibaba",
        "ma1": "alibaba",
        "ma2": "alibaba",
        "mc1": "alibaba",
        "wd": "wd",
        "wdc": "wd",
        "western": "wd",
        "seagate": "seagate",
        "st": "seagate",
    }

    if first_token in alias:
        return alias[first_token]
    for key, vendor in alias.items():
        if key and key in model_text:
            return vendor
    return "generic"


def _resolve_custom_profile_path(profile_key: str, profile_dir: str) -> Optional[str]:
    if not profile_key:
        return None
    key = str(profile_key).strip()
    if not key:
        return None

    candidates: List[str] = []
    if os.path.isabs(key):
        candidates.append(key)
    else:
        has_suffix = key.endswith((".yaml", ".yml", ".json"))
        if has_suffix:
            candidates.append(os.path.join(profile_dir, key))
        else:
            candidates.append(os.path.join(profile_dir, f"{key}.yaml"))
            candidates.append(os.path.join(profile_dir, f"{key}.yml"))
            candidates.append(os.path.join(profile_dir, "model", f"{key}.yaml"))
            candidates.append(os.path.join(profile_dir, "medium", f"{key}.yaml"))
            candidates.append(os.path.join(profile_dir, "vendor", f"{key}.yaml"))
            if "/" in key:
                candidates.append(os.path.join(profile_dir, f"{key}.yaml"))

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _normalize_required_causes(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        tokens = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        tokens = list(raw)
    else:
        return []

    out: List[str] = []
    seen = set()
    for token in tokens:
        cause = str(token).strip().lower()
        if not cause or cause not in ROOT_CAUSE_SET or cause in seen:
            continue
        seen.add(cause)
        out.append(cause)
    return out


def _resolve_recommended_required_causes(payload: Dict[str, Any], medium: str) -> List[str]:
    if not isinstance(payload, dict):
        payload = {}

    fewshot_cfg = payload.get("fewshot", {})
    if not isinstance(fewshot_cfg, dict):
        fewshot_cfg = {}

    # prefer explicit config in payload, then medium-aware defaults.
    explicit = _normalize_required_causes(
        fewshot_cfg.get("required_causes", payload.get("recommended_fewshot_required_causes"))
    )
    if explicit:
        return explicit

    if medium == "hdd":
        return ["media", "interface", "temperature", "power", "unknown"]
    return ROOT_CAUSES.copy()


def resolve_rule_profile_payload(
    rule_profile: str,
    profile_dir: Optional[str],
    rule_medium: str,
    disk_model: Optional[str],
    features: List[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    profile_root = os.path.abspath(profile_dir or DEFAULT_RULE_PROFILE_DIR)
    model_key = _normalize_model_key(disk_model)
    medium = _infer_medium(disk_model, features, rule_medium)
    vendor = _infer_vendor(disk_model, model_key)

    layers: List[Tuple[str, str]] = []
    base_path = os.path.join(profile_root, "base.yaml")
    if os.path.exists(base_path):
        layers.append(("base", base_path))

    profile_mode = str(rule_profile or "auto").strip()
    profile_mode_lc = profile_mode.lower()
    if profile_mode_lc == "auto":
        medium_path = os.path.join(profile_root, "medium", f"{medium}.yaml")
        vendor_path = os.path.join(profile_root, "vendor", f"{vendor}.yaml")
        model_path = os.path.join(profile_root, "model", f"{model_key}.yaml")
        if os.path.exists(medium_path):
            layers.append((f"medium:{medium}", medium_path))
        if os.path.exists(vendor_path):
            layers.append((f"vendor:{vendor}", vendor_path))
        if os.path.exists(model_path):
            layers.append((f"model:{model_key}", model_path))
        profile_id = f"{medium}.{vendor}.{model_key}"
    else:
        custom_path = _resolve_custom_profile_path(profile_mode, profile_root)
        if custom_path is None:
            raise FileNotFoundError(f"Rule profile not found: {profile_mode}")
        layers.append((f"profile:{profile_mode}", custom_path))
        profile_id = profile_mode

    payloads = [_load_yaml_or_json(path) for _, path in layers]
    merged_payload = merge_rule_payloads(payloads)
    meta = {
        "rule_profile_id": profile_id,
        "rule_medium": medium,
        "rule_vendor": vendor,
        "rule_model_key": model_key,
        "rule_profile_layers": [{"name": name, "path": path} for name, path in layers],
        "rule_profile_dir": profile_root,
        "recommended_fewshot_required_causes": _resolve_recommended_required_causes(merged_payload, medium),
    }
    return merged_payload, meta


def list_csv_files(data_root: str) -> List[str]:
    files = []
    for name in os.listdir(data_root):
        if not name.endswith(".csv"):
            continue
        if name == "ssd_failure_label.csv":
            continue
        files.append(os.path.join(data_root, name))
    return sorted(files)


def parse_date_from_filename(path: str, date_format: str) -> datetime:
    base = os.path.basename(path)
    stem = base[:-4]
    return datetime.strptime(stem, date_format)


def load_features(features_path: str, data_root: str) -> List[str]:
    def _normalize_list(raw: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in raw:
            key = canonicalize_feature_name(item)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    if features_path:
        with open(features_path, "r", encoding="utf-8") as f:
            return _normalize_list([line.strip() for line in f if line.strip()])

    files = list_csv_files(data_root)
    if not files:
        raise ValueError("No CSV files found in data_root")
    df = pd.read_csv(files[0], nrows=1)
    return _normalize_list([c for c in df.columns if str(c).startswith(("smart_", "r_", "n_"))])


def _load_yaml_or_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            payload = json.load(f)
        else:
            import yaml

            payload = yaml.safe_load(f)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Rule config must be a dict-like object: {path}")
    return payload


def _parse_ymd(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d")


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _format_eta(elapsed: float, done: int, total: Optional[int]) -> str:
    if total is None or total <= 0 or done <= 0:
        return "--:--"
    remaining = total - done
    if remaining <= 0:
        return "00:00"
    rate = done / max(elapsed, 1e-6)
    if rate <= 0:
        return "--:--"
    return _format_duration(remaining / rate)


def _progress_print(enabled: bool, message: str):
    if enabled:
        print(f"[window_to_text] {message}", flush=True)


def _normalize_rule_entry(feature: str, entry: Dict[str, Any], default_rules: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    mode = str(entry.get("mode", "level")).strip().lower()
    if mode not in ("level", "delta"):
        mode = "level"
    direction = str(entry.get("direction", "high_bad")).strip().lower()
    if direction not in ("high_bad", "high_warn", "low_bad"):
        direction = "high_bad"
    group = str(entry.get("group", "unknown")).strip().lower()
    if group not in ROOT_CAUSES:
        group = "unknown"
    base_defaults = default_rules[_infer_default_rule_key(feature)]
    out = deepcopy(base_defaults)
    out.update(entry)
    out["label"] = str(out.get("label", feature) or feature)
    out["group"] = group
    out["direction"] = direction
    out["mode"] = mode
    out["min_abs_delta"] = float(out.get("min_abs_delta", base_defaults["min_abs_delta"]))
    out["min_pct_delta"] = float(out.get("min_pct_delta", base_defaults["min_pct_delta"]))
    out["weight"] = float(out.get("weight", base_defaults["weight"]))
    out["min_points"] = max(1, int(out.get("min_points", base_defaults["min_points"])))
    out["cap"] = float(out.get("cap", base_defaults["cap"]))
    out["cooldown_days"] = max(0, int(out.get("cooldown_days", base_defaults["cooldown_days"])))
    return out


def _normalize_rule_payload(
    payload: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    default_rules = {
        "raw": deepcopy(DEFAULT_RAW_RULE),
        "normalized": deepcopy(DEFAULT_NORMALIZED_RULE),
    }
    features = deepcopy(DEFAULT_FEATURE_RULES)
    scoring = deepcopy(DEFAULT_SCORING_CONFIG)
    summary = deepcopy(DEFAULT_SUMMARY_CONFIG)

    payload = payload or {}
    payload_defaults = payload.get("defaults", {})
    if isinstance(payload_defaults, dict):
        for key in ("raw", "normalized"):
            entry = payload_defaults.get(key)
            if isinstance(entry, dict):
                merged = deepcopy(default_rules[key])
                merged.update(entry)
                default_rules[key] = merged

    payload_features = payload.get("features", {})
    if isinstance(payload_features, dict):
        for feature, entry in payload_features.items():
            if isinstance(entry, dict):
                canon = canonicalize_feature_name(feature)
                if not canon:
                    continue
                merged = deepcopy(features.get(canon, {}))
                merged.update(entry)
                features[canon] = merged

    payload_scoring = payload.get("scoring", {})
    if isinstance(payload_scoring, dict):
        scoring.update(payload_scoring)

    payload_summary = payload.get("summary", {})
    if isinstance(payload_summary, dict):
        summary.update(payload_summary)

    normalized_features = {
        feature: _normalize_rule_entry(feature, entry, default_rules)
        for feature, entry in features.items()
    }

    scoring["top_k_per_group"] = max(1, int(scoring.get("top_k_per_group", DEFAULT_SCORING_CONFIG["top_k_per_group"])))
    scoring["low_threshold"] = float(scoring.get("low_threshold", DEFAULT_SCORING_CONFIG["low_threshold"]))
    scoring["margin_threshold"] = float(scoring.get("margin_threshold", DEFAULT_SCORING_CONFIG["margin_threshold"]))
    scoring["abnormal_multiplier"] = float(scoring.get("abnormal_multiplier", DEFAULT_SCORING_CONFIG["abnormal_multiplier"]))
    scoring["watch_multiplier"] = float(scoring.get("watch_multiplier", DEFAULT_SCORING_CONFIG["watch_multiplier"]))
    scoring["watch_ratio_threshold"] = float(scoring.get("watch_ratio_threshold", DEFAULT_SCORING_CONFIG["watch_ratio_threshold"]))
    scoring["watch_severity_threshold"] = float(scoring.get("watch_severity_threshold", DEFAULT_SCORING_CONFIG["watch_severity_threshold"]))
    scoring["recency_horizon_days"] = max(1, int(scoring.get("recency_horizon_days", DEFAULT_SCORING_CONFIG["recency_horizon_days"])))
    scoring["workload_support_threshold"] = float(
        scoring.get("workload_support_threshold", DEFAULT_SCORING_CONFIG["workload_support_threshold"])
    )
    scoring["workload_min_support"] = max(0, int(scoring.get("workload_min_support", DEFAULT_SCORING_CONFIG["workload_min_support"])))
    scoring["workload_min_feature_signals"] = max(
        1, int(scoring.get("workload_min_feature_signals", DEFAULT_SCORING_CONFIG["workload_min_feature_signals"]))
    )

    summary["top_k"] = max(1, int(summary.get("top_k", DEFAULT_SUMMARY_CONFIG["top_k"])))
    summary["include_rule_conclusion"] = bool(summary.get("include_rule_conclusion", DEFAULT_SUMMARY_CONFIG["include_rule_conclusion"]))
    summary_schema = str(summary.get("summary_schema", DEFAULT_SUMMARY_CONFIG["summary_schema"])).strip().lower()
    if summary_schema not in SUMMARY_SCHEMAS:
        summary_schema = DEFAULT_SUMMARY_CONFIG["summary_schema"]
    summary["summary_schema"] = summary_schema
    summary["anomaly_top_k"] = max(1, int(summary.get("anomaly_top_k", summary.get("top_k", DEFAULT_SUMMARY_CONFIG["anomaly_top_k"]))))
    summary["emit_legacy_text"] = bool(summary.get("emit_legacy_text", DEFAULT_SUMMARY_CONFIG["emit_legacy_text"]))

    return normalized_features, scoring, summary, default_rules


def load_rule_config(path: Optional[str]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Rule config file not found: {path}")
        payload = _load_yaml_or_json(path)
        return _normalize_rule_payload(payload)
    return _normalize_rule_payload({})


def load_rule_config_from_payload(payload: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    return _normalize_rule_payload(payload or {})


def set_active_rule_config(
    feature_rules: Dict[str, Dict[str, Any]],
    scoring: Dict[str, Any],
    summary: Dict[str, Any],
    default_rules: Dict[str, Dict[str, Any]],
) -> None:
    global ACTIVE_FEATURE_RULES, ACTIVE_SCORING, ACTIVE_SUMMARY, ACTIVE_DEFAULT_RULES
    ACTIVE_FEATURE_RULES = deepcopy(feature_rules)
    ACTIVE_SCORING = deepcopy(scoring)
    ACTIVE_SUMMARY = deepcopy(summary)
    ACTIVE_DEFAULT_RULES = deepcopy(default_rules)


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _ratio_last_flags(flags: List[bool], width: int) -> float:
    if not flags:
        return 0.0
    n = min(len(flags), max(1, int(width)))
    if n <= 0:
        return 0.0
    tail = flags[-n:]
    return sum(1 for x in tail if x) / float(n)


def _tail_true_streak(flags: List[bool]) -> int:
    streak = 0
    for flag in reversed(flags):
        if not flag:
            break
        streak += 1
    return streak


def _max_true_streak(flags: List[bool]) -> int:
    best = 0
    cur = 0
    for flag in flags:
        if flag:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _tail_slope(values: List[float], width: int) -> float:
    if not values:
        return 0.0
    n = min(len(values), max(2, int(width)))
    if n < 2:
        return 0.0
    start = float(values[-n])
    end = float(values[-1])
    return (end - start) / float(n - 1)


def _default_rule(feature: str) -> Dict:
    default_key = _infer_default_rule_key(feature)
    out = deepcopy(ACTIVE_DEFAULT_RULES[default_key])
    out["label"] = feature
    return out


def _infer_default_rule_key(feature: str) -> str:
    name = canonicalize_feature_name(feature)
    if name.endswith("_normalized") or name.startswith("n_"):
        return "normalized"
    if name.endswith("_raw") or name.startswith("r_"):
        return "raw"
    return "raw"


def _rule_of(feature: str) -> Dict:
    key = canonicalize_feature_name(feature)
    entry = ACTIVE_FEATURE_RULES.get(key)
    if entry is None:
        return _default_rule(key or str(feature))
    return entry


def compute_feature_series(window_items: List[Tuple[datetime, Dict[str, float]]], features: List[str]) -> Dict[str, List[Tuple[datetime, float]]]:
    out: Dict[str, List[Tuple[datetime, float]]] = {f: [] for f in features}
    for dt, row in window_items:
        for feat in features:
            val = _safe_float(row.get(feat))
            if val is None:
                continue
            out[feat].append((dt, val))
    return {k: v for k, v in out.items() if v}


def _threshold_abs(rule: Dict, baseline: float, robust_floor: float = 0.0) -> float:
    return max(float(rule["min_abs_delta"]), abs(baseline) * float(rule["min_pct_delta"]), float(robust_floor))


def _is_abnormal(value: float, baseline: float, rule: Dict) -> bool:
    thr = _threshold_abs(rule, baseline)
    direction = rule["direction"]
    if direction in ("high_bad", "high_warn"):
        return value - baseline >= thr
    return baseline - value >= thr


def evaluate_feature(feature: str, series: List[Tuple[datetime, float]]) -> Dict:
    values = [v for _, v in series]
    dates = [d for d, _ in series]
    n = len(values)

    rule = _rule_of(feature)
    mode = str(rule.get("mode", "level"))
    min_points = max(1, int(rule.get("min_points", 3)))

    if mode == "delta" and n >= 2:
        signal_values = [values[i] - values[i - 1] for i in range(1, n)]
        signal_dates = dates[1:]
        signal_kind = "delta"
    else:
        signal_values = values
        signal_dates = dates
        signal_kind = "level"

    signal_n = len(signal_values)
    n_base_signal = max(1, min(signal_n, int(math.ceil(signal_n * 0.40))))
    base_signal_slice = signal_values[:n_base_signal]
    signal_baseline = median(base_signal_slice) if base_signal_slice else 0.0
    signal_mad = median([abs(x - signal_baseline) for x in base_signal_slice]) if base_signal_slice else 0.0
    robust_floor = 1.5 * 1.4826 * signal_mad
    thr_signal = _threshold_abs(rule, signal_baseline, robust_floor=robust_floor)

    abnormal_flags = [_is_abnormal(v, signal_baseline, rule) for v in signal_values]
    first_abnormal_date = None
    last_abnormal_date = None
    for dt, flag in zip(signal_dates, abnormal_flags):
        if not flag:
            continue
        if first_abnormal_date is None:
            first_abnormal_date = dt.strftime("%Y-%m-%d")
        last_abnormal_date = dt.strftime("%Y-%m-%d")

    current_abnormal = abnormal_flags[-1] if abnormal_flags else False
    abnormal_ratio = (sum(1 for x in abnormal_flags if x) / signal_n) if signal_n else 0.0
    current_signal = signal_values[-1] if signal_values else 0.0

    if rule["direction"] in ("high_bad", "high_warn"):
        deviation_abs = current_signal - signal_baseline
    else:
        deviation_abs = signal_baseline - current_signal
    deviation_pct = deviation_abs / (abs(signal_baseline) + 1.0)

    severity = _clip01(abs(deviation_abs) / (thr_signal * 2.0 + 1e-9))
    severity = min(severity, max(0.0, float(rule.get("cap", 1.0))))
    reliability = _clip01(signal_n / float(min_points))

    ratio_3d = _ratio_last_flags(abnormal_flags, 3)
    ratio_7d = _ratio_last_flags(abnormal_flags, 7)
    ratio_14d = _ratio_last_flags(abnormal_flags, 14)
    tail_streak = _tail_true_streak(abnormal_flags)
    max_streak = _max_true_streak(abnormal_flags)
    slope_3 = _tail_slope(signal_values, 3)
    slope_14 = _tail_slope(signal_values, 14)
    burst_ratio = abs(slope_3) / (abs(slope_14) + 1e-9)

    if signal_n < min_points:
        current_abnormal = False
        abnormal_ratio = 0.0
        severity = min(severity, 0.25)
        watch_flag = False
        status = "数据不足"
    else:
        cooldown_days = int(rule.get("cooldown_days", 0))
        if current_abnormal and cooldown_days > 0:
            lookback = min(len(abnormal_flags), cooldown_days + 1)
            if sum(1 for x in abnormal_flags[-lookback:] if x) < lookback:
                current_abnormal = False

        watch_flag = (not current_abnormal) and (
            abnormal_ratio >= float(ACTIVE_SCORING["watch_ratio_threshold"])
            or severity >= float(ACTIVE_SCORING["watch_severity_threshold"])
        )
        if current_abnormal:
            status = "异常"
        elif watch_flag:
            status = "观察"
        elif first_abnormal_date is not None:
            status = "曾异常"
        else:
            status = "正常"

    n_base = max(1, min(n, int(math.ceil(n * 0.40))))
    baseline = median(values[:n_base])
    current = values[-1]
    prev = values[-2] if n >= 2 else values[-1]
    delta = current - prev
    mean_value = sum(values) / n
    std_value = (sum((x - mean_value) ** 2 for x in values) / n) ** 0.5
    z_like = abs(deviation_abs) / (std_value + 1e-9)
    z_like = min(float(z_like), 99.0)

    return {
        "feature": feature,
        "label": rule["label"],
        "group": rule["group"],
        "direction": rule["direction"],
        "mode": mode,
        "weight": float(rule.get("weight", 1.0)),
        "min_points": min_points,
        "reliability": reliability,
        "count": n,
        "current": current,
        "baseline": baseline,
        "delta": delta,
        "mean": mean_value,
        "std": std_value,
        "min": min(values),
        "max": max(values),
        "threshold_abs": thr_signal,
        "signal_kind": signal_kind,
        "signal_current": current_signal,
        "signal_baseline": signal_baseline,
        "signal_threshold_abs": thr_signal,
        "deviation_abs": deviation_abs,
        "deviation_pct": deviation_pct,
        "current_abnormal": current_abnormal,
        "watch_flag": watch_flag,
        "first_abnormal_date": first_abnormal_date,
        "last_abnormal_date": last_abnormal_date,
        "abnormal_ratio": abnormal_ratio,
        "abnormal_ratio_3d": ratio_3d,
        "abnormal_ratio_7d": ratio_7d,
        "abnormal_ratio_14d": ratio_14d,
        "abnormal_streak_tail": int(tail_streak),
        "abnormal_streak_max": int(max_streak),
        "trend_slope_3": float(slope_3),
        "trend_slope_14": float(slope_14),
        "trend_burst_ratio": float(min(burst_ratio, 999.0)),
        "severity": severity,
        "status": status,
        "z_like": z_like,
        "last_date": dates[-1].strftime("%Y-%m-%d"),
    }


def compute_feature_stats(window_items: List[Tuple[datetime, Dict[str, float]]], features: List[str]) -> Dict[str, Dict]:
    series = compute_feature_series(window_items, features)
    return {feat: evaluate_feature(feat, s) for feat, s in series.items()}


def infer_root_cause(stats: Dict[str, Dict]) -> Tuple[str, Dict[str, float]]:
    scores = {k: 0.0 for k in ROOT_CAUSES}
    grouped_contrib: Dict[str, List[float]] = {k: [] for k in ROOT_CAUSES}
    available_counts: Dict[str, int] = {k: 0 for k in ROOT_CAUSES}
    active_signal_counts: Dict[str, int] = {k: 0 for k in ROOT_CAUSES}

    for item in stats.values():
        group = item["group"]
        if group not in grouped_contrib or group == "unknown":
            continue
        available_counts[group] += 1
        if item["current_abnormal"]:
            state_multiplier = float(ACTIVE_SCORING["abnormal_multiplier"])
            recency_factor = 1.0
        elif item["watch_flag"] or item["abnormal_ratio"] >= float(ACTIVE_SCORING["watch_ratio_threshold"]):
            state_multiplier = float(ACTIVE_SCORING["watch_multiplier"])
            if item.get("last_abnormal_date"):
                last_dt = datetime.strptime(item["last_date"], "%Y-%m-%d")
                last_abn_dt = datetime.strptime(item["last_abnormal_date"], "%Y-%m-%d")
                days_since = (last_dt - last_abn_dt).days
                recency_factor = max(
                    0.35,
                    1.0 - days_since / float(ACTIVE_SCORING["recency_horizon_days"]),
                )
            else:
                recency_factor = 0.35
        else:
            continue

        contribution = (
            float(item["weight"])
            * float(item["severity"])
            * float(item["reliability"])
            * state_multiplier
            * recency_factor
        )
        if contribution <= 0:
            continue
        grouped_contrib[group].append(contribution)
        active_signal_counts[group] += 1

    top_k = int(ACTIVE_SCORING["top_k_per_group"])
    for group in ("media", "interface", "temperature", "power", "workload"):
        group_scores = sorted(grouped_contrib[group], reverse=True)
        raw_score = float(sum(group_scores[:top_k]))
        available = int(available_counts.get(group, 0))
        active = int(active_signal_counts.get(group, 0))
        if available <= 0:
            scores[group] = 0.0
            continue
        availability_ratio = active / float(available)
        # Normalize by available signal surface to reduce cross-model bias.
        normalized = raw_score / math.sqrt(float(max(1, available)))
        normalized *= (0.75 + 0.25 * availability_ratio)
        scores[group] = float(normalized)

    ranked = sorted(
        ((group, scores[group]) for group in ("media", "interface", "temperature", "power", "workload")),
        key=lambda x: x[1],
        reverse=True,
    )
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score < float(ACTIVE_SCORING["low_threshold"]):
        return "unknown", scores
    if best_score - second_score < float(ACTIVE_SCORING["margin_threshold"]):
        return "unknown", scores

    if best == "workload":
        available_workload = int(available_counts.get("workload", 0))
        if available_workload <= 0:
            return "unknown", scores

        available_non_workload_groups = sum(
            1
            for group in ("media", "interface", "temperature", "power")
            if int(available_counts.get(group, 0)) > 0
        )
        dynamic_min_support = min(
            int(ACTIVE_SCORING["workload_min_support"]),
            available_non_workload_groups,
        )
        dynamic_min_feature_signals = min(
            int(ACTIVE_SCORING["workload_min_feature_signals"]),
            max(1, available_workload),
        )
        dynamic_support_threshold = float(ACTIVE_SCORING["workload_support_threshold"])
        if available_workload <= 1:
            dynamic_support_threshold *= 0.85

        non_workload_support = sum(
            1
            for group in ("media", "interface", "temperature", "power")
            if scores[group] >= dynamic_support_threshold
        )
        if (
            non_workload_support < dynamic_min_support
            and active_signal_counts.get("workload", 0) < dynamic_min_feature_signals
        ):
            return "unknown", scores

    return best, scores


def _smart_name(feature: str) -> str:
    m = re.search(r"smart_(\d+)", feature)
    if m:
        return f"SMART_{m.group(1)}"
    m = re.match(r"[nr]_(\d+)$", str(feature))
    if m:
        return f"SMART_{m.group(1)}"
    return str(feature).upper()


def build_events(stats: Dict[str, Dict], top_k: int = 3) -> List[Dict]:
    events = []
    for item in stats.values():
        if not item["current_abnormal"] or item["group"] == "unknown":
            continue
        direction = item["direction"]
        if item.get("mode") == "delta":
            event_type = "spike"
        elif direction in ("high_bad", "high_warn"):
            event_type = "monotonic_increase"
        else:
            event_type = "drop"
        events.append({
            "feature": _smart_name(item["feature"]),
            "type": event_type,
            "severity": float(_clip01(item["severity"])),
            "window_days": int(item["count"]),
            "_rank": abs(item["deviation_abs"]),
        })

    events.sort(key=lambda x: (x["severity"], x["_rank"]), reverse=True)
    out = []
    for e in events[:top_k]:
        e.pop("_rank", None)
        out.append(e)
    return out


def build_target_json(stats: Dict[str, Dict], n_rows: int) -> Dict:
    root_cause, scores = infer_root_cause(stats)
    events = build_events(stats, top_k=3)
    max_signal = max(scores.values()) if scores else 0.0

    risk_hint = _clip01(max_signal / 2.0)
    hardness = _clip01(max_signal / 2.4)
    confidence = _clip01(0.25 + 0.5 * max_signal / 2.0)

    if n_rows < 3:
        root_cause = "unknown"
        risk_hint = min(risk_hint, 0.30)
        hardness = min(hardness, 0.30)
        confidence = min(confidence, 0.35)

    near_positive = bool(risk_hint >= 0.6)
    label_noise_risk = _clip01(0.4 if root_cause == "unknown" and risk_hint > 0.35 else 0.1)

    return {
        "events": events,
        "root_cause": root_cause,
        "risk_hint": float(risk_hint),
        "hardness": float(hardness),
        "near_positive": near_positive,
        "label_noise_risk": float(label_noise_risk),
        "confidence": float(confidence),
    }


def _format_feature_line(item: Dict) -> str:
    feature = _smart_name(item["feature"])
    source = _infer_default_rule_key(str(item["feature"]))
    mode = str(item.get("mode", "level"))
    baseline = float(item["signal_baseline"] if mode == "delta" else item["baseline"])
    current = float(item["signal_current"] if mode == "delta" else item["current"])
    delta_pct = float(item["deviation_pct"]) * 100.0
    sign = "+" if delta_pct >= 0 else ""
    severity = float(_clip01(item["severity"]))
    z_like = float(item.get("z_like", 0.0))
    if bool(item.get("current_abnormal")):
        state = "abnormal"
    elif bool(item.get("watch_flag")) or float(item.get("abnormal_ratio", 0.0)) >= float(ACTIVE_SCORING["watch_ratio_threshold"]):
        state = "watch"
    else:
        state = "history"
    return (
        f"- {feature} {source} {mode} baseline={baseline:.2f} "
        f"current={current:.2f} delta_pct={sign}{delta_pct:.1f} z={z_like:.2f} "
        f"severity={severity:.2f} state={state}"
    )


def _format_anomaly_table_row(item: Dict) -> str:
    feature = _smart_name(item["feature"])
    source = _infer_default_rule_key(str(item["feature"]))
    mode = str(item.get("mode", "level"))
    direction = str(item.get("direction", "high_bad"))
    baseline = float(item["signal_baseline"] if mode == "delta" else item["baseline"])
    current = float(item["signal_current"] if mode == "delta" else item["current"])
    delta_pct = float(_safe_float(item.get("deviation_pct")) or 0.0) * 100.0
    sign = "+" if delta_pct >= 0 else ""
    abnormal_ratio = float(_clip01(_safe_float(item.get("abnormal_ratio")) or 0.0))
    persistence = float(_clip01(_safe_float(item.get("abnormal_ratio_14d")) or abnormal_ratio))
    slope3 = float(_safe_float(item.get("trend_slope_3")) or 0.0)
    slope14 = float(_safe_float(item.get("trend_slope_14")) or 0.0)
    burst_ratio = float(_safe_float(item.get("trend_burst_ratio")) or 0.0)
    severity = float(_clip01(_safe_float(item.get("severity")) or 0.0))
    group = str(item.get("group", "unknown"))
    return (
        f"- feat={feature}|src={source}|mode={mode}|dir={direction}|baseline={baseline:.2f}|current={current:.2f}|"
        f"delta_pct={sign}{delta_pct:.1f}|abnormal_ratio={abnormal_ratio:.2f}|persistence={persistence:.2f}|"
        f"slope3={slope3:+.3f}|slope14={slope14:+.3f}|burst_ratio={burst_ratio:.2f}|severity={severity:.2f}|group={group}"
    )


def _format_anomaly_table_lines(selected_items: List[Dict], top_k: int) -> List[str]:
    lines = ["ANOMALY_TABLE:"]
    if not selected_items:
        lines.append("- none")
        return lines
    ranked = sorted(
        selected_items,
        key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
        reverse=True,
    )
    for item in ranked[: max(1, int(top_k))]:
        lines.append(_format_anomaly_table_row(item))
    return lines


def _select_summary_features(stats: Dict[str, Dict], top_k: int) -> List[str]:
    if not stats:
        return []
    watch_ratio_threshold = float(ACTIVE_SCORING["watch_ratio_threshold"])
    ranked_abnormal = [
        (feat, item)
        for feat, item in sorted(
            stats.items(),
            key=lambda kv: (kv[1]["severity"], abs(kv[1]["deviation_abs"])),
            reverse=True,
        )
        if item["current_abnormal"]
    ]
    ranked_watch = [
        (feat, item)
        for feat, item in sorted(
            stats.items(),
            key=lambda kv: (kv[1]["severity"], abs(kv[1]["deviation_abs"])),
            reverse=True,
        )
        if (not item["current_abnormal"])
        and (item.get("watch_flag") or float(item.get("abnormal_ratio", 0.0)) >= watch_ratio_threshold)
    ]

    def split_known_unknown(items: List[Tuple[str, Dict]]) -> Tuple[List[str], List[str]]:
        known_feats = [feat for feat, item in items if str(item.get("group", "unknown")) != "unknown"]
        unknown_feats = [feat for feat, item in items if str(item.get("group", "unknown")) == "unknown"]
        return known_feats, unknown_feats

    known_abn, unknown_abn = split_known_unknown(ranked_abnormal)
    known_watch, unknown_watch = split_known_unknown(ranked_watch)
    preferred = known_abn + known_watch
    fallback = unknown_abn + unknown_watch
    return (preferred + fallback)[: max(1, int(top_k))]


def _format_persistence_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "ANOMALY_PERSISTENCE: none"
    dedup: Dict[str, float] = {}
    for item in selected_items:
        ratio = float(_clip01(_safe_float(item.get("abnormal_ratio")) or 0.0))
        feat = _smart_name(item["feature"])
        dedup[feat] = max(dedup.get(feat, 0.0), ratio)
    parts = [f"{feat}={ratio:.2f}" for feat, ratio in dedup.items()]
    return "ANOMALY_PERSISTENCE: " + " ".join(parts)


def _format_trend_delta_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "TREND_DELTA: none"
    dedup: Dict[str, float] = {}
    for item in selected_items:
        trend_delta = float(_safe_float(item.get("deviation_pct")) or 0.0)
        feat = _smart_name(item["feature"])
        prev = dedup.get(feat)
        if prev is None or abs(trend_delta) > abs(prev):
            dedup[feat] = trend_delta
    parts = []
    for feat, trend_delta in dedup.items():
        sign = "+" if trend_delta >= 0 else ""
        parts.append(f"{feat}={sign}{trend_delta:.3f}")
    return "TREND_DELTA: " + " ".join(parts)


def _format_feature_delta_topk_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "FEATURE_DELTA_TOPK: none"
    dedup: Dict[str, Dict] = {}
    for item in selected_items:
        feat = _smart_name(item["feature"])
        prev = dedup.get(feat)
        cur_key = (float(item.get("severity", 0.0)), abs(float(item.get("deviation_abs", 0.0))))
        prev_key = (
            float(prev.get("severity", 0.0)),
            abs(float(prev.get("deviation_abs", 0.0))),
        ) if prev is not None else (-1.0, -1.0)
        if prev is None or cur_key > prev_key:
            dedup[feat] = item
    parts: List[str] = []
    ranked = sorted(
        dedup.values(),
        key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
        reverse=True,
    )
    for item in ranked[:5]:
        feat = _smart_name(item["feature"])
        delta_pct = float(_safe_float(item.get("deviation_pct")) or 0.0) * 100.0
        sign = "+" if delta_pct >= 0 else ""
        z_like = float(_safe_float(item.get("z_like")) or 0.0)
        severity = float(_clip01(_safe_float(item.get("severity")) or 0.0))
        parts.append(f"{feat}={sign}{delta_pct:.1f}%|z{z_like:.2f}|sev{severity:.2f}")
    return "FEATURE_DELTA_TOPK: " + " ".join(parts)


def _format_persistence_profile_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "PERSISTENCE_PROFILE: none"
    dedup: Dict[str, Dict] = {}
    for item in selected_items:
        feat = _smart_name(item["feature"])
        prev = dedup.get(feat)
        cur_key = (float(item.get("severity", 0.0)), abs(float(item.get("deviation_abs", 0.0))))
        prev_key = (
            float(prev.get("severity", 0.0)),
            abs(float(prev.get("deviation_abs", 0.0))),
        ) if prev is not None else (-1.0, -1.0)
        if prev is None or cur_key > prev_key:
            dedup[feat] = item
    parts: List[str] = []
    ranked = sorted(
        dedup.values(),
        key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
        reverse=True,
    )
    for item in ranked[:5]:
        feat = _smart_name(item["feature"])
        p3 = float(_clip01(_safe_float(item.get("abnormal_ratio_3d")) or 0.0))
        p7 = float(_clip01(_safe_float(item.get("abnormal_ratio_7d")) or 0.0))
        p14 = float(_clip01(_safe_float(item.get("abnormal_ratio_14d")) or 0.0))
        streak = int(_safe_float(item.get("abnormal_streak_tail")) or 0.0)
        parts.append(f"{feat}=p3:{p3:.2f},p7:{p7:.2f},p14:{p14:.2f},streak:{streak}")
    return "PERSISTENCE_PROFILE: " + " ".join(parts)


def _format_burst_vs_drift_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "BURST_VS_DRIFT: none"
    dedup: Dict[str, Dict] = {}
    for item in selected_items:
        feat = _smart_name(item["feature"])
        prev = dedup.get(feat)
        cur_key = (float(item.get("severity", 0.0)), abs(float(item.get("deviation_abs", 0.0))))
        prev_key = (
            float(prev.get("severity", 0.0)),
            abs(float(prev.get("deviation_abs", 0.0))),
        ) if prev is not None else (-1.0, -1.0)
        if prev is None or cur_key > prev_key:
            dedup[feat] = item
    parts: List[str] = []
    ranked = sorted(
        dedup.values(),
        key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
        reverse=True,
    )
    for item in ranked[:5]:
        feat = _smart_name(item["feature"])
        slope3 = float(_safe_float(item.get("trend_slope_3")) or 0.0)
        slope14 = float(_safe_float(item.get("trend_slope_14")) or 0.0)
        burst = float(_safe_float(item.get("trend_burst_ratio")) or 0.0)
        parts.append(f"{feat}=s3:{slope3:+.3f},s14:{slope14:+.3f},burst:{burst:.2f}")
    return "BURST_VS_DRIFT: " + " ".join(parts)


def _format_cause_evidence_line(stats: Dict[str, Dict]) -> str:
    if not stats:
        return "CAUSE_EVIDENCE: none"
    watch_ratio_threshold = float(ACTIVE_SCORING.get("watch_ratio_threshold", 0.2))
    parts: List[str] = []
    for group in ("media", "interface", "temperature", "power", "workload"):
        group_items = [item for item in stats.values() if item.get("group") == group]
        if not group_items:
            parts.append(f"{group}=none")
            continue
        positives = [
            item
            for item in group_items
            if item.get("current_abnormal")
            or item.get("watch_flag")
            or float(item.get("abnormal_ratio", 0.0)) >= watch_ratio_threshold
        ]
        dedup_pos: Dict[str, Dict] = {}
        for item in positives:
            feat = _smart_name(item["feature"])
            prev = dedup_pos.get(feat)
            cur_key = (float(item.get("severity", 0.0)), abs(float(item.get("deviation_abs", 0.0))))
            prev_key = (
                float(prev.get("severity", 0.0)),
                abs(float(prev.get("deviation_abs", 0.0))),
            ) if prev is not None else (-1.0, -1.0)
            if prev is None or cur_key > prev_key:
                dedup_pos[feat] = item
        positives = sorted(
            dedup_pos.values(),
            key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
            reverse=True,
        )
        negatives = [item for item in group_items if item not in positives]
        negatives = sorted(
            negatives,
            key=lambda x: (float(x.get("severity", 0.0)), abs(float(x.get("deviation_abs", 0.0)))),
        )

        tokens: List[str] = []
        for item in positives[:2]:
            feat = _smart_name(item["feature"])
            sev = float(_clip01(_safe_float(item.get("severity")) or 0.0))
            tokens.append(f"+{feat}({sev:.2f})")
        if negatives:
            item = negatives[0]
            feat = _smart_name(item["feature"])
            sev = float(_clip01(_safe_float(item.get("severity")) or 0.0))
            tokens.append(f"-{feat}({sev:.2f})")
        elif not positives:
            tokens.append("-none")
        parts.append(f"{group}=" + ",".join(tokens if tokens else ["none"]))
    return "CAUSE_EVIDENCE: " + " ".join(parts)


def _format_data_quality_line(stats: Dict[str, Dict], n_rows: int) -> str:
    if n_rows <= 0:
        return "DATA_QUALITY: valid_days=0 missing_ratio=1.00 active_features=0/0 known_features=0"
    total_features = len(stats)
    if total_features <= 0:
        return f"DATA_QUALITY: valid_days={n_rows} missing_ratio=1.00 active_features=0/0 known_features=0"

    coverage_ratios = [min(1.0, max(0.0, float(item.get("count", 0)) / float(n_rows))) for item in stats.values()]
    avg_coverage = sum(coverage_ratios) / float(len(coverage_ratios))
    missing_ratio = _clip01(1.0 - avg_coverage)
    watch_ratio_threshold = float(ACTIVE_SCORING.get("watch_ratio_threshold", 0.2))
    active_features = sum(
        1
        for item in stats.values()
        if item.get("current_abnormal")
        or item.get("watch_flag")
        or float(item.get("abnormal_ratio", 0.0)) >= watch_ratio_threshold
    )
    known_features = sum(1 for item in stats.values() if str(item.get("group", "unknown")) != "unknown")
    return (
        f"DATA_QUALITY: valid_days={n_rows} missing_ratio={missing_ratio:.2f} "
        f"active_features={active_features}/{total_features} known_features={known_features}"
    )


def _format_allowed_event_features_line(selected_items: List[Dict]) -> str:
    if not selected_items:
        return "ALLOWED_EVENT_FEATURES: none"
    features: List[str] = []
    seen = set()
    for item in selected_items:
        feat = _smart_name(item["feature"])
        if feat in seen:
            continue
        seen.add(feat)
        features.append(feat)
    if not features:
        return "ALLOWED_EVENT_FEATURES: none"
    return "ALLOWED_EVENT_FEATURES: " + " ".join(features)


def _format_group_signal_line(stats: Dict[str, Dict]) -> str:
    if not stats:
        return "GROUP_SIGNAL: none"
    watch_ratio_threshold = float(ACTIVE_SCORING.get("watch_ratio_threshold", 0.2))
    parts: List[str] = []
    for group in ("media", "interface", "temperature", "power", "workload"):
        available = 0
        active = 0
        max_severity = 0.0
        for item in stats.values():
            if item.get("group") != group:
                continue
            available += 1
            is_active = bool(item.get("current_abnormal")) or bool(item.get("watch_flag")) or (
                float(item.get("abnormal_ratio", 0.0)) >= watch_ratio_threshold
            )
            if is_active:
                active += 1
                max_severity = max(max_severity, float(item.get("severity", 0.0)))
        parts.append(f"{group}={active}/{available}:{_clip01(max_severity):.2f}")
    return "GROUP_SIGNAL: " + " ".join(parts)


def _format_rule_top2_line(scores: Dict[str, float]) -> str:
    if not scores:
        return "RULE_TOP2: none"
    ranked = sorted(
        ((group, float(scores.get(group, 0.0))) for group in ("media", "interface", "temperature", "power", "workload")),
        key=lambda x: x[1],
        reverse=True,
    )
    top1_group, top1_score = ranked[0]
    top2_group, top2_score = ranked[1]
    margin = top1_score - top2_score
    return (
        "RULE_TOP2: "
        f"{top1_group}={top1_score:.3f} "
        f"{top2_group}={top2_score:.3f} "
        f"margin={margin:.3f}"
    )


def _mask_disk_id(disk_id: str) -> str:
    token = str(disk_id or "").strip()
    if not token:
        return "none"
    # Avoid leaking long numeric substrings that LLM may misread as SMART ids.
    masked = []
    for ch in token[:16]:
        if ch.isdigit():
            masked.append("N")
        elif ch.isalpha():
            masked.append("A")
        else:
            masked.append("_")
    return "".join(masked)


def build_summary_text(
    disk_id: str,
    window_end_time: str,
    stats: Dict[str, Dict],
    window_items: List[Tuple[datetime, Dict[str, float]]],
    top_k: Optional[int] = None,
) -> str:
    if top_k is None:
        top_k = int(ACTIVE_SUMMARY["top_k"])
    n_rows = len(window_items)

    if window_items:
        start_day = window_items[0][0].strftime("%Y-%m-%d")
        end_day = window_items[-1][0].strftime("%Y-%m-%d")
    else:
        start_day = window_end_time
        end_day = window_end_time

    root_cause, scores = infer_root_cause(stats) if stats else ("unknown", {k: 0.0 for k in ROOT_CAUSES})
    selected = _select_summary_features(stats, top_k)

    selected_items: List[Dict] = []
    for feat in selected:
        item = stats[feat]
        selected_items.append(item)

    rule_score_line = (
        "RULE_SCORE: "
        f"media={scores['media']:.3f} "
        f"interface={scores['interface']:.3f} "
        f"temperature={scores['temperature']:.3f} "
        f"power={scores['power']:.3f} "
        f"workload={scores['workload']:.3f}"
    )

    summary_schema = str(ACTIVE_SUMMARY.get("summary_schema", "legacy")).strip().lower()
    if summary_schema not in SUMMARY_SCHEMAS:
        summary_schema = "legacy"

    if summary_schema == "structured_v2":
        anomaly_top_k = max(1, int(ACTIVE_SUMMARY.get("anomaly_top_k", top_k)))
        lines = [
            f"WINDOW: {start_day}~{end_day} ({n_rows}d) disk={_mask_disk_id(disk_id)}",
            _format_data_quality_line(stats, n_rows),
            rule_score_line,
            _format_rule_top2_line(scores),
            _format_allowed_event_features_line(selected_items),
        ]
        lines.extend(_format_anomaly_table_lines(selected_items, anomaly_top_k))
        lines.append(_format_cause_evidence_line(stats))
        lines.append(f"RULE_PRED: {root_cause}")
        if bool(ACTIVE_SUMMARY.get("emit_legacy_text", False)):
            lines.append(_format_persistence_line(selected_items))
            lines.append(_format_trend_delta_line(selected_items))
            lines.append(_format_feature_delta_topk_line(selected_items))
            lines.append(_format_persistence_profile_line(selected_items))
            lines.append(_format_burst_vs_drift_line(selected_items))
            lines.append(_format_group_signal_line(stats))
        return "\n".join(lines)

    lines = [f"WINDOW: {start_day}~{end_day} ({n_rows}d) disk={_mask_disk_id(disk_id)}", "ANOMALIES:"]
    if selected_items:
        for item in selected_items:
            lines.append(_format_feature_line(item))
    else:
        lines.append("- none")

    lines.append(_format_allowed_event_features_line(selected_items))
    lines.append(_format_persistence_line(selected_items))
    lines.append(_format_trend_delta_line(selected_items))
    lines.append(_format_feature_delta_topk_line(selected_items))
    lines.append(_format_persistence_profile_line(selected_items))
    lines.append(_format_burst_vs_drift_line(selected_items))
    lines.append(_format_cause_evidence_line(stats))
    lines.append(_format_data_quality_line(stats, n_rows))
    lines.append(_format_group_signal_line(stats))
    lines.append(_format_rule_top2_line(scores))
    lines.append(rule_score_line)
    lines.append(f"RULE_PRED: {root_cause}")
    return "\n".join(lines)


def iter_window_records(
    data_root: str,
    features: List[str],
    window_days: int,
    date_format: str,
    disk_model: Optional[str] = None,
    max_windows: Optional[int] = None,
    disk_id_prefix: str = "",
    output_start_date: Optional[datetime] = None,
    output_end_date: Optional[datetime] = None,
    show_progress: bool = False,
    progress_prefix: str = "output",
    progress_every_files: int = 10,
    progress_every_rows: int = 200000,
    progress_every_windows: int = 5000,
) -> Iterable[Tuple[str, str, str, Dict[str, Dict], Dict, int]]:
    files = list_csv_files(data_root)
    buffers: Dict[str, deque] = {}
    count = 0
    rows_seen = 0
    start_ts = time.time()
    total_files = len(files)
    file_step = max(1, int(progress_every_files))
    row_step = max(1, int(progress_every_rows))
    win_step = max(1, int(progress_every_windows))

    _progress_print(
        show_progress,
        (
            f"{progress_prefix} start files={total_files} window_days={window_days} "
            f"sample_max={max_windows if max_windows is not None else 'all'}"
        ),
    )

    for file_idx, path in enumerate(files, start=1):
        if show_progress and (file_idx == 1 or file_idx % file_step == 0 or file_idx == total_files):
            elapsed = time.time() - start_ts
            eta = _format_eta(elapsed, file_idx, total_files)
            _progress_print(
                show_progress,
                (
                    f"{progress_prefix} file {file_idx}/{total_files} "
                    f"elapsed={_format_duration(elapsed)} eta={eta} path={os.path.basename(path)}"
                ),
            )
        file_date = parse_date_from_filename(path, date_format)
        if output_end_date is not None and file_date.date() > output_end_date.date():
            break
        header_cols = pd.read_csv(path, nrows=0).columns.tolist()
        if "serial_number" in header_cols:
            disk_col = "serial_number"
        elif "disk_id" in header_cols:
            disk_col = "disk_id"
        else:
            raise ValueError("CSV must contain serial_number or disk_id column")

        feature_set = set(features)
        canonical_to_source: Dict[str, str] = {}
        canonical_score: Dict[str, int] = {}
        for col in header_cols:
            canon = canonicalize_feature_name(col)
            if not canon or canon not in feature_set:
                continue
            score = _feature_column_priority(col, canon)
            if canon not in canonical_to_source or score > canonical_score[canon]:
                canonical_to_source[canon] = col
                canonical_score[canon] = score

        feature_cols = sorted(set(canonical_to_source.values()))
        use_cols = [disk_col] + feature_cols
        if "model" in header_cols:
            use_cols.append("model")
        if "date" in header_cols:
            use_cols.append("date")

        # Read only the columns needed by downstream window stats.
        df = pd.read_csv(path, usecols=use_cols)

        if disk_model is not None and "model" in df.columns:
            df = df[df["model"] == disk_model]

        if df.empty:
            continue

        col_idx = {c: i for i, c in enumerate(df.columns)}
        disk_idx = col_idx[disk_col]
        has_date = "date" in col_idx
        date_values = (
            pd.to_datetime(df["date"], format=date_format, errors="coerce").tolist()
            if has_date
            else None
        )
        feature_idx = {
            canon: col_idx[source]
            for canon, source in canonical_to_source.items()
            if source in col_idx
        }

        for row_i, row in enumerate(df.itertuples(index=False, name=None)):
            rows_seen += 1
            if show_progress and rows_seen % row_step == 0:
                elapsed = time.time() - start_ts
                _progress_print(
                    show_progress,
                    (
                        f"{progress_prefix} rows_seen={rows_seen} windows={count} "
                        f"elapsed={_format_duration(elapsed)}"
                    ),
                )
            disk_id = str(row[disk_idx])
            if disk_id_prefix and not disk_id.startswith(disk_id_prefix):
                disk_id = f"{disk_id_prefix}{disk_id}"

            cur_date = file_date
            if has_date and date_values is not None:
                parsed_date = date_values[row_i]
                if not pd.isna(parsed_date):
                    cur_date = parsed_date.to_pydatetime()

            buf = buffers.setdefault(disk_id, deque())
            row_dict = {
                feat: row[feature_idx[feat]]
                for feat in features
                if feat in feature_idx
            }
            buf.append((cur_date, row_dict))

            while buf and (cur_date - buf[0][0]).days >= window_days:
                buf.popleft()

            if output_start_date is not None and cur_date.date() < output_start_date.date():
                continue
            if output_end_date is not None and cur_date.date() > output_end_date.date():
                continue

            window_items = list(buf)
            stats = compute_feature_stats(window_items, features)
            summary = build_summary_text(disk_id, cur_date.strftime("%Y-%m-%d"), stats, window_items)
            n_rows = len(window_items)
            target = build_target_json(stats, n_rows)

            yield disk_id, cur_date.strftime("%Y-%m-%d"), summary, stats, target, n_rows

            count += 1
            if show_progress and count % win_step == 0:
                elapsed = time.time() - start_ts
                rate = count / max(elapsed, 1e-6)
                _progress_print(
                    show_progress,
                    (
                        f"{progress_prefix} windows={count} rows_seen={rows_seen} "
                        f"rate={rate:.2f} win/s elapsed={_format_duration(elapsed)}"
                    ),
                )
            if max_windows is not None and count >= max_windows:
                elapsed = time.time() - start_ts
                _progress_print(
                    show_progress,
                    (
                        f"{progress_prefix} reached max_windows={max_windows} "
                        f"rows_seen={rows_seen} elapsed={_format_duration(elapsed)}"
                    ),
                )
                return

    elapsed = time.time() - start_ts
    _progress_print(
        show_progress,
        f"{progress_prefix} finished windows={count} rows_seen={rows_seen} elapsed={_format_duration(elapsed)}",
    )


def _allocate_day_quotas(day_counts: Dict[str, int], max_windows: int, seed: int) -> Dict[str, int]:
    if max_windows <= 0 or not day_counts:
        return {}

    days = sorted(day_counts.keys())
    rng = random.Random(seed)
    quotas = {day: 0 for day in days}

    if len(days) >= max_windows:
        for day in rng.sample(days, max_windows):
            quotas[day] = 1
        return quotas

    # ensure every day participates at least once, then allocate remainder by volume.
    for day in days:
        quotas[day] = 1
    remaining = max_windows - len(days)
    if remaining <= 0:
        return quotas

    total = sum(max(1, int(day_counts[day])) for day in days)
    if total <= 0:
        return quotas

    fractional = []
    assigned = 0
    for day in days:
        exact = remaining * (max(1, int(day_counts[day])) / float(total))
        extra = int(math.floor(exact))
        quotas[day] += extra
        assigned += extra
        fractional.append((exact - extra, day))

    left = remaining - assigned
    if left > 0:
        rng.shuffle(fractional)
        fractional.sort(key=lambda x: x[0], reverse=True)
        for _, day in fractional[:left]:
            quotas[day] += 1
    return quotas


def iter_window_records_sampled(
    data_root: str,
    features: List[str],
    window_days: int,
    date_format: str,
    disk_model: Optional[str],
    max_windows: Optional[int],
    disk_id_prefix: str,
    output_start_date: Optional[datetime],
    output_end_date: Optional[datetime],
    sample_mode: str,
    sample_seed: int,
    show_progress: bool = False,
    progress_prefix: str = "output",
    progress_every_files: int = 10,
    progress_every_rows: int = 200000,
    progress_every_windows: int = 5000,
) -> Iterable[Tuple[str, str, str, Dict[str, Dict], Dict, int]]:
    if sample_mode == "sequential" or max_windows is None or max_windows <= 0:
        yield from iter_window_records(
            data_root,
            features,
            window_days,
            date_format,
            disk_model,
            max_windows,
            disk_id_prefix,
            output_start_date,
            output_end_date,
            show_progress=show_progress,
            progress_prefix=progress_prefix,
            progress_every_files=progress_every_files,
            progress_every_rows=progress_every_rows,
            progress_every_windows=progress_every_windows,
        )
        return

    if sample_mode != "stratified_day_disk":
        raise ValueError(f"Unsupported sample mode: {sample_mode}")

    _progress_print(
        show_progress,
        (
            f"{progress_prefix} sampling mode=stratified_day_disk max_windows={max_windows} "
            f"seed={sample_seed}"
        ),
    )

    day_counts: Dict[str, int] = {}
    pass1_count = 0
    pass1_ts = time.time()
    pass_step = max(1, int(progress_every_windows))
    for _, day, _, _, _, _ in iter_window_records(
        data_root,
        features,
        window_days,
        date_format,
        disk_model,
        None,
        disk_id_prefix,
        output_start_date,
        output_end_date,
        show_progress=False,
    ):
        pass1_count += 1
        if show_progress and pass1_count % pass_step == 0:
            elapsed = time.time() - pass1_ts
            _progress_print(
                show_progress,
                (
                    f"{progress_prefix} pass1_count={pass1_count} unique_days={len(day_counts)} "
                    f"elapsed={_format_duration(elapsed)}"
                ),
            )
        day_counts[day] = day_counts.get(day, 0) + 1

    quotas = _allocate_day_quotas(day_counts, int(max_windows), int(sample_seed))
    _progress_print(
        show_progress,
        (
            f"{progress_prefix} pass1_done windows={pass1_count} active_days={len(day_counts)} "
            f"quota_days={len([d for d, q in quotas.items() if q > 0])}"
        ),
    )
    if not quotas:
        return

    rng = random.Random(int(sample_seed))
    heaps: Dict[str, List[Tuple[float, Tuple[str, str, str, Dict[str, Dict], Dict, int]]]] = {
        day: [] for day, quota in quotas.items() if quota > 0
    }
    seen_per_day_disk: Dict[Tuple[str, str], int] = {}

    pass2_count = 0
    pass2_ts = time.time()
    for rec in iter_window_records(
        data_root,
        features,
        window_days,
        date_format,
        disk_model,
        None,
        disk_id_prefix,
        output_start_date,
        output_end_date,
        show_progress=False,
    ):
        pass2_count += 1
        if show_progress and pass2_count % pass_step == 0:
            elapsed = time.time() - pass2_ts
            _progress_print(
                show_progress,
                (
                    f"{progress_prefix} pass2_scanned={pass2_count} selected_so_far="
                    f"{sum(len(h) for h in heaps.values())} elapsed={_format_duration(elapsed)}"
                ),
            )
        disk_id, day, *_ = rec
        quota = quotas.get(day, 0)
        if quota <= 0:
            continue

        key = (day, disk_id)
        seen = seen_per_day_disk.get(key, 0) + 1
        seen_per_day_disk[key] = seen
        # prefer rare disks within each day while keeping randomness.
        weight = 1.0 / math.sqrt(float(seen))
        priority = rng.random() ** (1.0 / max(weight, 1e-6))
        heap = heaps[day]
        item = (priority, rec)
        if len(heap) < quota:
            heapq.heappush(heap, item)
        elif priority > heap[0][0]:
            heapq.heapreplace(heap, item)

    selected: List[Tuple[str, str, str, Dict[str, Dict], Dict, int]] = []
    for day in sorted(heaps.keys()):
        day_records = [it[1] for it in heaps[day]]
        day_records.sort(key=lambda x: (x[1], x[0]))
        selected.extend(day_records)

    selected.sort(key=lambda x: (x[1], x[0]))
    if len(selected) > max_windows:
        selected = selected[:max_windows]
    _progress_print(
        show_progress,
        (
            f"{progress_prefix} sampling_done selected={len(selected)} "
            f"pass1={pass1_count} pass2={pass2_count}"
        ),
    )
    for rec in selected:
        yield rec


def _reference_score(rec: Dict[str, Any]) -> float:
    target = rec.get("target", {}) if isinstance(rec, dict) else {}
    if not isinstance(target, dict):
        target = {}
    confidence = float(target.get("confidence", 0.0))
    signal = float(target.get("risk_hint", 0.0))
    events = target.get("events", [])
    events_bonus = min(3, len(events)) / 3.0 if isinstance(events, list) else 0.0
    return 0.55 * confidence + 0.35 * signal + 0.10 * events_bonus


def _pick_diverse_examples(
    scored_items: List[Tuple[float, Dict[str, Any]]],
    n_pick: int,
    used_disks: set,
    used_days: set,
) -> List[Dict[str, Any]]:
    if n_pick <= 0 or not scored_items:
        return []

    pool = sorted(scored_items, key=lambda x: x[0], reverse=True)
    picked: List[Dict[str, Any]] = []
    while pool and len(picked) < n_pick:
        best_idx = 0
        best_score = -1e9
        for idx, (score, rec) in enumerate(pool):
            disk_id = str(rec.get("disk_id", ""))
            day = str(rec.get("window_end_time", ""))
            bonus = 0.0
            if disk_id and disk_id not in used_disks:
                bonus += 0.05
            if day and day not in used_days:
                bonus += 0.03
            candidate_score = score + bonus
            if candidate_score > best_score:
                best_score = candidate_score
                best_idx = idx
        _, rec = pool.pop(best_idx)
        picked.append(rec)
        disk_id = str(rec.get("disk_id", ""))
        day = str(rec.get("window_end_time", ""))
        if disk_id:
            used_disks.add(disk_id)
        if day:
            used_days.add(day)
    return picked


def build_reference_examples(
    records: List[Dict],
    per_cause: int = 1,
    strategy: str = "stratified",
    min_per_cause: int = 1,
    min_non_unknown: int = 3,
) -> Tuple[List[Dict], Dict[str, Any]]:
    bucket: Dict[str, List[Tuple[float, Dict[str, Any]]]] = {k: [] for k in ROOT_CAUSES}
    fallback: List[Tuple[float, Dict[str, Any]]] = []
    seen_keys = set()
    dedup_records: List[Dict[str, Any]] = []

    for rec in records:
        key = (str(rec.get("disk_id", "")), str(rec.get("window_end_time", "")))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        dedup_records.append(rec)

    pool_coverage = {k: 0 for k in ROOT_CAUSES}
    for rec in dedup_records:
        target = rec.get("target", {})
        if not isinstance(target, dict):
            continue
        cause = str(target.get("root_cause", "unknown")).strip().lower()
        if cause not in ROOT_CAUSES:
            cause = "unknown"
        pool_coverage[cause] += 1
        score = _reference_score(rec)

        if rec.get("n_rows", 0) >= 3:
            bucket[cause].append((score, rec))
        fallback.append((score, rec))

    chosen_records: List[Dict[str, Any]] = []
    used_disks: set = set()
    used_days: set = set()
    selected_keys: set = set()

    per_cause = max(1, int(per_cause))
    min_per_cause = max(1, int(min_per_cause))
    min_non_unknown = max(0, int(min_non_unknown))
    target_per_cause = per_cause if strategy == "legacy" else max(per_cause, min_per_cause)

    for cause in ["media", "interface", "temperature", "power", "workload", "unknown"]:
        picked = _pick_diverse_examples(bucket[cause], target_per_cause, used_disks, used_days)
        for rec in picked:
            key = (str(rec.get("disk_id", "")), str(rec.get("window_end_time", "")))
            if key in selected_keys:
                continue
            selected_keys.add(key)
            chosen_records.append(rec)

    if not chosen_records:
        for rec in _pick_diverse_examples(fallback, max(1, per_cause), used_disks, used_days):
            key = (str(rec.get("disk_id", "")), str(rec.get("window_end_time", "")))
            if key in selected_keys:
                continue
            selected_keys.add(key)
            chosen_records.append(rec)

    non_unknown_selected = sum(
        1
        for rec in chosen_records
        if str(rec.get("target", {}).get("root_cause", "unknown")).strip().lower() != "unknown"
    )
    if non_unknown_selected < min_non_unknown:
        non_unknown_pool = [
            item
            for item in fallback
            if str(item[1].get("target", {}).get("root_cause", "unknown")).strip().lower() != "unknown"
        ]
        need = min_non_unknown - non_unknown_selected
        for rec in _pick_diverse_examples(non_unknown_pool, need, used_disks, used_days):
            key = (str(rec.get("disk_id", "")), str(rec.get("window_end_time", "")))
            if key in selected_keys:
                continue
            selected_keys.add(key)
            chosen_records.append(rec)

    chosen = [
        {
            "disk_id": rec.get("disk_id"),
            "window_end_time": rec.get("window_end_time"),
            "summary_text": rec["summary_text"],
            "target": rec["target"],
        }
        for rec in chosen_records
    ]
    coverage_by_cause = {k: 0 for k in ROOT_CAUSES}
    for rec in chosen_records:
        cause = str(rec.get("target", {}).get("root_cause", "unknown")).strip().lower()
        if cause not in coverage_by_cause:
            cause = "unknown"
        coverage_by_cause[cause] += 1

    selected_non_unknown = sum(v for k, v in coverage_by_cause.items() if k != "unknown")
    total_selected = len(chosen_records)
    non_unknown_ratio = (selected_non_unknown / total_selected) if total_selected > 0 else 0.0
    top_missing_causes = [
        cause
        for cause in ["media", "interface", "temperature", "power", "workload"]
        if coverage_by_cause.get(cause, 0) == 0
    ]

    quality = {
        "selected_examples": total_selected,
        "pool_records": len(dedup_records),
        "coverage_by_cause": coverage_by_cause,
        "pool_coverage_by_cause": pool_coverage,
        "non_unknown_ratio": round(non_unknown_ratio, 6),
        "top_missing_causes": top_missing_causes,
        "reference_min_non_unknown": min_non_unknown,
    }
    return chosen, quality


def write_jsonl(path: str, rows: List[Dict]):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", required=True, help="Directory with daily CSV files")
    parser.add_argument("--out", required=True, help="Output path for window text (.jsonl)")
    parser.add_argument("--features_path", required=True, help="Path to selected feature list")
    parser.add_argument("--window_days", type=int, default=30, help="Sliding window size (days)")
    parser.add_argument("--date_format", default="%Y-%m-%d", help="Date format for CSV filenames")
    parser.add_argument("--disk_model", default=None, help="Only convert windows for a specific disk model")
    parser.add_argument("--max_windows", type=int, default=None, help="Limit number of windows for testing")
    parser.add_argument(
        "--sample_mode",
        default="sequential",
        choices=["sequential", "stratified_day_disk"],
        help="Window sampling mode when --max_windows is set",
    )
    parser.add_argument("--sample_seed", type=int, default=42, help="Random seed for sampled modes")
    parser.add_argument(
        "--show_progress",
        dest="show_progress",
        action="store_true",
        default=True,
        help="Print stage/file/window progress logs (enabled by default)",
    )
    parser.add_argument(
        "--no_progress",
        dest="show_progress",
        action="store_false",
        help="Disable progress logs",
    )
    parser.add_argument("--progress_every_files", type=int, default=10, help="Progress interval in files")
    parser.add_argument("--progress_every_rows", type=int, default=200000, help="Progress interval in raw rows")
    parser.add_argument("--progress_every_windows", type=int, default=5000, help="Progress interval in output windows")
    parser.add_argument("--rule_config", default=None, help="Optional explicit rule override yaml/json path")
    parser.add_argument("--rule_profile", default="auto", help="Rule profile key: auto or explicit profile id/path")
    parser.add_argument("--rule_profile_dir", default=DEFAULT_RULE_PROFILE_DIR, help="Directory for hierarchical rule profiles")
    parser.add_argument("--rule_medium", default="auto", choices=["auto", "hdd", "ssd"], help="Force rule medium")
    parser.add_argument("--summary_top_k", type=int, default=None, help="Override summary top-k lines")
    parser.add_argument(
        "--summary_schema",
        default=None,
        choices=["legacy", "structured_v2"],
        help="Summary schema: legacy free-form or structured_v2 fixed blocks",
    )
    parser.add_argument("--summary_anomaly_top_k", type=int, default=None, help="Top-k anomaly rows for structured_v2 ANOMALY_TABLE")
    parser.add_argument(
        "--summary_emit_legacy_text",
        action="store_true",
        help="When summary_schema=structured_v2, append legacy helper lines for compatibility/debug",
    )
    parser.add_argument("--disk_id_prefix", default="", help="Optional prefix for disk_id output (e.g., 's' for SSD)")
    parser.add_argument("--reference_out", default=None, help="Optional output json for real-data reference examples")
    parser.add_argument("--reference_per_cause", type=int, default=1, help="How many examples to keep per root cause")
    parser.add_argument("--reference_strategy", default="stratified", choices=["stratified", "legacy"])
    parser.add_argument("--reference_min_per_cause", type=int, default=1, help="Min examples per cause in stratified mode")
    parser.add_argument("--reference_min_non_unknown", type=int, default=3, help="Min non-unknown examples to keep")
    parser.add_argument("--reference_quality_report_out", default=None, help="Optional path to dump reference quality report json")
    parser.add_argument(
        "--reference_fail_on_low_quality",
        action="store_true",
        help="Fail when selected references miss non-unknown minimum or required causes",
    )
    parser.add_argument("--reference_pool_windows", type=int, default=None, help="Optional larger pool size for reference mining")
    parser.add_argument("--reference_start_date", default=None, help="Only use reference windows on/after this date (YYYY-MM-DD)")
    parser.add_argument("--reference_end_date", default=None, help="Only use reference windows on/before this date (YYYY-MM-DD)")
    parser.add_argument("--output_start_date", default=None, help="Only output windows on/after this date (YYYY-MM-DD)")
    parser.add_argument("--output_end_date", default=None, help="Only output windows on/before this date (YYYY-MM-DD)")
    args = parser.parse_args()

    features = load_features(args.features_path, args.data_root)
    profile_payload, profile_meta = resolve_rule_profile_payload(
        args.rule_profile,
        args.rule_profile_dir,
        args.rule_medium,
        args.disk_model,
        features,
    )

    rule_config_path = args.rule_config
    if rule_config_path == DEFAULT_RULE_CONFIG_PATH and not os.path.exists(rule_config_path):
        rule_config_path = None
    explicit_rule_config = bool(rule_config_path) and ("--rule_config" in sys.argv)
    if explicit_rule_config and not os.path.exists(rule_config_path):
        raise FileNotFoundError(f"Rule config file not found: {rule_config_path}")
    override_payload = _load_yaml_or_json(rule_config_path) if explicit_rule_config else {}
    merged_payload = merge_rule_payloads([profile_payload, override_payload])

    if merged_payload:
        feature_rules, scoring_cfg, summary_cfg, default_rules = load_rule_config_from_payload(merged_payload)
    else:
        fallback_path = DEFAULT_RULE_CONFIG_PATH if os.path.exists(DEFAULT_RULE_CONFIG_PATH) else None
        feature_rules, scoring_cfg, summary_cfg, default_rules = load_rule_config(fallback_path)
        profile_meta["rule_profile_id"] = "legacy_default"

    if args.summary_top_k is not None:
        summary_cfg["top_k"] = max(1, int(args.summary_top_k))
    if args.summary_schema is not None:
        summary_cfg["summary_schema"] = str(args.summary_schema).strip().lower()
    if args.summary_anomaly_top_k is not None:
        summary_cfg["anomaly_top_k"] = max(1, int(args.summary_anomaly_top_k))
    if args.summary_emit_legacy_text:
        summary_cfg["emit_legacy_text"] = True
    set_active_rule_config(feature_rules, scoring_cfg, summary_cfg, default_rules)

    feature_rule_total = max(1, len(features))
    matched_features = [feat for feat in features if feat in feature_rules]
    missing_features = [feat for feat in features if feat not in feature_rules]
    feature_rule_coverage = {
        "matched": len(matched_features),
        "total": len(features),
        "ratio": round(len(matched_features) / float(feature_rule_total), 6),
        "missing_features_topk": missing_features[:50],
    }

    output_start = _parse_ymd(args.output_start_date)
    output_end = _parse_ymd(args.output_end_date)

    rows = []
    records_for_ref = []
    _progress_print(
        args.show_progress,
        (
            f"main output generation start sample_mode={args.sample_mode} "
            f"max_windows={args.max_windows if args.max_windows is not None else 'all'}"
        ),
    )
    for disk_id, window_end_time, summary, stats, target, n_rows in iter_window_records_sampled(
        args.data_root,
        features,
        args.window_days,
        args.date_format,
        disk_model=args.disk_model,
        max_windows=args.max_windows,
        disk_id_prefix=args.disk_id_prefix,
        output_start_date=output_start,
        output_end_date=output_end,
        sample_mode=args.sample_mode,
        sample_seed=args.sample_seed,
        show_progress=bool(args.show_progress),
        progress_prefix="output",
        progress_every_files=max(1, int(args.progress_every_files)),
        progress_every_rows=max(1, int(args.progress_every_rows)),
        progress_every_windows=max(1, int(args.progress_every_windows)),
    ):
        rows.append({
            "disk_id": disk_id,
            "window_end_time": window_end_time,
            "summary_text": summary,
            "summary_schema": str(ACTIVE_SUMMARY.get("summary_schema", "legacy")),
            "rule_profile_id": profile_meta["rule_profile_id"],
            "rule_medium": profile_meta["rule_medium"],
            "rule_vendor": profile_meta["rule_vendor"],
            "rule_model_key": profile_meta["rule_model_key"],
        })
        records_for_ref.append({
            "disk_id": disk_id,
            "window_end_time": window_end_time,
            "summary_text": summary,
            "target": target,
            "stats": stats,
            "n_rows": n_rows,
        })

    write_jsonl(args.out, rows)
    _progress_print(
        args.show_progress,
        f"main output written rows={len(rows)} path={args.out}",
    )

    if args.reference_out:
        reference_records = records_for_ref
        ref_start = _parse_ymd(args.reference_start_date)
        ref_end = _parse_ymd(args.reference_end_date)

        if args.reference_pool_windows is not None:
            _progress_print(
                args.show_progress,
                (
                    f"reference generation start pool_windows={args.reference_pool_windows} "
                    f"mode={args.sample_mode}"
                ),
            )
            reference_records = []
            for disk_id, window_end_time, summary, stats, target, n_rows in iter_window_records_sampled(
                args.data_root,
                features,
                args.window_days,
                args.date_format,
                disk_model=args.disk_model,
                max_windows=args.reference_pool_windows,
                disk_id_prefix=args.disk_id_prefix,
                output_start_date=ref_start,
                output_end_date=ref_end,
                sample_mode=args.sample_mode,
                sample_seed=args.sample_seed,
                show_progress=bool(args.show_progress),
                progress_prefix="reference_pool",
                progress_every_files=max(1, int(args.progress_every_files)),
                progress_every_rows=max(1, int(args.progress_every_rows)),
                progress_every_windows=max(1, int(args.progress_every_windows)),
            ):
                reference_records.append({
                    "disk_id": disk_id,
                    "window_end_time": window_end_time,
                    "summary_text": summary,
                    "target": target,
                    "stats": stats,
                    "n_rows": n_rows,
                })
            _progress_print(
                args.show_progress,
                f"reference generation collected={len(reference_records)}",
            )
        if ref_start or ref_end:
            filtered = []
            for rec in reference_records:
                try:
                    wdt = datetime.strptime(str(rec.get("window_end_time", "")), "%Y-%m-%d")
                except Exception:
                    continue
                if ref_start and wdt < ref_start:
                    continue
                if ref_end and wdt > ref_end:
                    continue
                filtered.append(rec)
            reference_records = filtered

        refs, quality = build_reference_examples(
            reference_records,
            per_cause=args.reference_per_cause,
            strategy=args.reference_strategy,
            min_per_cause=args.reference_min_per_cause,
            min_non_unknown=args.reference_min_non_unknown,
        )
        if args.reference_fail_on_low_quality:
            required_causes = profile_meta.get("recommended_fewshot_required_causes", ROOT_CAUSES)
            coverage_now = quality.get("coverage_by_cause", {})
            missing_causes = [cause for cause in required_causes if int(coverage_now.get(cause, 0)) <= 0]
            non_unknown_selected = sum(
                int(coverage_now.get(cause, 0))
                for cause in ["media", "interface", "temperature", "power", "workload"]
            )
            if non_unknown_selected < int(args.reference_min_non_unknown):
                raise RuntimeError(
                    f"Reference quality check failed: non_unknown={non_unknown_selected} "
                    f"< reference_min_non_unknown={int(args.reference_min_non_unknown)}"
                )
            if missing_causes:
                raise RuntimeError(
                    "Reference quality check failed: missing causes="
                    + ",".join(missing_causes)
                )
        payload = {
            "source": "auto_generated_from_real_windows",
            "features_path": args.features_path,
            "num_records": len(rows),
            "reference_pool_windows": args.reference_pool_windows if args.reference_pool_windows is not None else len(reference_records),
            "rule_config": rule_config_path if explicit_rule_config else None,
            "profile_resolved": profile_meta,
            "recommended_fewshot_required_causes": profile_meta.get("recommended_fewshot_required_causes", ROOT_CAUSES),
            "coverage_by_cause": quality.get("coverage_by_cause", {}),
            "non_unknown_ratio": quality.get("non_unknown_ratio", 0.0),
            "top_missing_causes": quality.get("top_missing_causes", []),
            "feature_rule_coverage": feature_rule_coverage,
            "reference_scope": {
                "disk_model": args.disk_model,
                "rule_model_key": profile_meta.get("rule_model_key"),
                "rule_medium": profile_meta.get("rule_medium"),
                "rule_vendor": profile_meta.get("rule_vendor"),
                "reference_start_date": args.reference_start_date,
                "reference_end_date": args.reference_end_date,
                "output_start_date": args.output_start_date,
                "output_end_date": args.output_end_date,
            },
            "reference_selector": {
                "strategy": "per_model_train_period_diverse",
                "reference_per_cause": int(args.reference_per_cause),
                "reference_min_per_cause": int(args.reference_min_per_cause),
                "reference_min_non_unknown": int(args.reference_min_non_unknown),
                "sample_mode": args.sample_mode,
                "sample_seed": int(args.sample_seed),
            },
            "summary_config": {
                "summary_schema": str(ACTIVE_SUMMARY.get("summary_schema", "legacy")),
                "top_k": int(ACTIVE_SUMMARY.get("top_k", 8)),
                "anomaly_top_k": int(ACTIVE_SUMMARY.get("anomaly_top_k", ACTIVE_SUMMARY.get("top_k", 8))),
                "emit_legacy_text": bool(ACTIVE_SUMMARY.get("emit_legacy_text", False)),
            },
            "quality": quality,
            "examples": refs,
        }
        reference_out_dir = os.path.dirname(args.reference_out)
        if reference_out_dir:
            os.makedirs(reference_out_dir, exist_ok=True)
        with open(args.reference_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        if args.reference_quality_report_out:
            quality_payload = {
                "profile_resolved": profile_meta,
                "recommended_fewshot_required_causes": profile_meta.get("recommended_fewshot_required_causes", ROOT_CAUSES),
                "feature_rule_coverage": feature_rule_coverage,
                "summary_config": {
                    "summary_schema": str(ACTIVE_SUMMARY.get("summary_schema", "legacy")),
                    "top_k": int(ACTIVE_SUMMARY.get("top_k", 8)),
                    "anomaly_top_k": int(ACTIVE_SUMMARY.get("anomaly_top_k", ACTIVE_SUMMARY.get("top_k", 8))),
                    "emit_legacy_text": bool(ACTIVE_SUMMARY.get("emit_legacy_text", False)),
                },
                "quality": quality,
                "reference_pool_windows": args.reference_pool_windows if args.reference_pool_windows is not None else len(reference_records),
                "examples_count": len(refs),
            }
            quality_out_dir = os.path.dirname(args.reference_quality_report_out)
            if quality_out_dir:
                os.makedirs(quality_out_dir, exist_ok=True)
            with open(args.reference_quality_report_out, "w", encoding="utf-8") as f:
                json.dump(quality_payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
