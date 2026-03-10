import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

ROOT_CAUSES = ["media", "interface", "temperature", "power", "workload", "unknown"]
DEFAULT_EVENT_FEATURES = [
    "SMART_1",
    "SMART_3",
    "SMART_4",
    "SMART_5",
    "SMART_7",
    "SMART_8",
    "SMART_9",
    "SMART_10",
    "SMART_12",
    "SMART_187",
    "SMART_188",
    "SMART_189",
    "SMART_190",
    "SMART_191",
    "SMART_194",
    "SMART_197",
]
DEFAULT_EVENT_TYPES = ["monotonic_increase", "spike", "drop"]
DEFAULT_META_DIM = 16
DEFAULT_EVENT_MAPPING: Dict[str, Any] = {}


def _normalize_feature_name(name: Any) -> str:
    if name is None:
        return ""
    s = str(name).upper()
    match = re.search(r"(SMART)[_\- ]?(\d+)", s)
    if match:
        return f"SMART_{match.group(2)}"
    return s


def _normalize_event_type(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).lower()
    if "increase" in s or "up" in s or "monotonic" in s:
        return "monotonic_increase"
    if "spike" in s or "burst" in s:
        return "spike"
    if "decrease" in s or "drop" in s or "down" in s:
        return "drop"
    return ""


def _build_event_mapping(payload: Dict[str, Any]) -> Dict[str, Any]:
    meta_dim = int(payload.get("meta_dim", DEFAULT_META_DIM))
    if meta_dim != DEFAULT_META_DIM:
        raise ValueError(f"Unsupported meta_dim={meta_dim}. Expected {DEFAULT_META_DIM}.")

    raw_features = payload.get("event_features") or DEFAULT_EVENT_FEATURES
    features = []
    seen = set()
    for feat in raw_features:
        norm = _normalize_feature_name(feat)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        features.append(norm)

    raw_types = payload.get("event_types") or DEFAULT_EVENT_TYPES
    types = []
    seen_types = set()
    for etype in raw_types:
        norm = _normalize_event_type(etype)
        if not norm or norm in seen_types:
            continue
        seen_types.add(norm)
        types.append(norm)

    if not types:
        types = list(DEFAULT_EVENT_TYPES)
    if not features:
        features = list(DEFAULT_EVENT_FEATURES)

    mapping = {
        "meta_dim": meta_dim,
        "event_features": features,
        "event_types": types,
    }
    mapping["vector_dim"] = meta_dim + len(features) * len(types)
    return mapping


def _load_yaml_or_json(path: str) -> Dict[str, Any]:
    _, ext = os.path.splitext(path)
    with open(path, "r", encoding="utf-8") as f:
        if ext.lower() in (".yaml", ".yml"):
            import yaml
            return yaml.safe_load(f) or {}
        return json.load(f) if ext.lower() == ".json" else json.load(f)


def load_event_mapping_config(path: str = None) -> Dict[str, Any]:
    if not path:
        return DEFAULT_EVENT_MAPPING
    payload = _load_yaml_or_json(path)
    if not isinstance(payload, dict):
        raise ValueError("Event mapping config must be a dict.")
    return _build_event_mapping(payload)


DEFAULT_EVENT_MAPPING = _build_event_mapping({
    "meta_dim": DEFAULT_META_DIM,
    "event_features": DEFAULT_EVENT_FEATURES,
    "event_types": DEFAULT_EVENT_TYPES,
})
VECTOR_DIM = DEFAULT_EVENT_MAPPING["vector_dim"]


def get_logger() -> logging.Logger:
    logger = logging.getLogger("llm_feature_mapping")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def map_llm_json_to_vector(
    data: Dict[str, Any],
    dim: int = None,
    logger: logging.Logger = None,
    mapping: Dict[str, Any] = None,
) -> Tuple[List[float], Dict[str, Any]]:
    if logger is None:
        logger = get_logger()

    if mapping is None:
        mapping = DEFAULT_EVENT_MAPPING
    vector_dim = int(mapping.get("vector_dim", VECTOR_DIM))
    meta_dim = int(mapping.get("meta_dim", DEFAULT_META_DIM))
    if meta_dim != DEFAULT_META_DIM:
        raise ValueError(f"Unsupported meta_dim={meta_dim}. Expected {DEFAULT_META_DIM}.")
    if dim is not None and dim != vector_dim:
        raise ValueError(f"Unsupported dim={dim}. Expected {vector_dim}.")

    event_features = mapping.get("event_features", DEFAULT_EVENT_FEATURES)
    event_types = mapping.get("event_types", DEFAULT_EVENT_TYPES)

    vec = [0.0] * vector_dim

    root_cause = _normalize_root_cause(data.get("root_cause"), logger)
    vec[ROOT_CAUSES.index(root_cause)] = 1.0

    risk_hint = _safe_float(data.get("risk_hint"))
    hardness = _safe_float(data.get("hardness"))
    label_noise_risk = _safe_float(data.get("label_noise_risk"))
    confidence = _safe_float(data.get("confidence"))
    near_positive = 1.0 if bool(data.get("near_positive")) else 0.0

    vec[6] = _clip01(risk_hint)
    vec[7] = _clip01(hardness)
    vec[8] = _clip01(label_noise_risk)
    vec[9] = _clip01(confidence)
    vec[10] = near_positive

    events = data.get("events") or []
    if not isinstance(events, list):
        logger.info("Invalid events field, expected list.")
        events = []

    event_count = len(events)
    mapped_event_count = 0
    max_severity = 0.0
    sum_severity = 0.0
    max_window_days = 0.0
    sum_persistence = 0.0
    max_persistence = 0.0
    sum_trend_pos = 0.0

    for event in events:
        feature = _normalize_feature_name(event.get("feature"))
        etype = _normalize_event_type(event.get("type"))
        severity = _clip01(_safe_float(event.get("severity")))
        window_days = _safe_float(event.get("window_days"))
        persistence = _clip01(_safe_float(event.get("persistence")))
        trend_delta = _safe_float(event.get("trend_delta"))
        trend_pos = _clip01(max(0.0, trend_delta))

        if feature not in event_features or etype not in event_types:
            logger.info("Unknown event mapping: feature=%s type=%s", feature, etype)
            continue

        f_idx = event_features.index(feature)
        t_idx = event_types.index(etype)
        offset = meta_dim + f_idx * len(event_types) + t_idx
        vec[offset] = max(vec[offset], severity if severity > 0 else 1.0)
        mapped_event_count += 1

        max_severity = max(max_severity, severity)
        sum_severity += severity
        max_window_days = max(max_window_days, window_days)
        sum_persistence += persistence
        max_persistence = max(max_persistence, persistence)
        sum_trend_pos += trend_pos

    vec[11] = min(1.0, mapped_event_count / 10.0)
    vec[12] = max_severity
    avg_severity = (sum_severity / mapped_event_count) if mapped_event_count > 0 else 0.0
    avg_persistence = (sum_persistence / mapped_event_count) if mapped_event_count > 0 else 0.0
    avg_trend_pos = (sum_trend_pos / mapped_event_count) if mapped_event_count > 0 else 0.0
    vec[13] = _clip01(0.6 * avg_severity + 0.4 * avg_persistence)
    vec[14] = min(1.0, max_window_days / 30.0) if max_window_days > 0 else 0.0
    if max_persistence > 0:
        vec[14] = _clip01(0.5 * vec[14] + 0.5 * max_persistence)
    vec[15] = _clip01(avg_trend_pos)

    meta = {
        "root_cause": root_cause,
        "hardness": hardness,
        "near_positive": bool(data.get("near_positive")) if data.get("near_positive") is not None else False,
        "label_noise_risk": label_noise_risk,
        "risk_hint": risk_hint,
        "confidence": confidence,
    }

    return vec, meta


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _normalize_root_cause(value: Any, logger: logging.Logger) -> str:
    if value is None:
        return "unknown"

    s = str(value).strip().lower()
    if s in ROOT_CAUSES:
        return s

    # Handle outputs like "media|interface|temperature|power|workload|unknown".
    parts = re.split(r"[|,/;\s]+", s)
    matches = [p for p in parts if p in ROOT_CAUSES]
    unique_matches = list(dict.fromkeys(matches))
    if len(unique_matches) == 1:
        return unique_matches[0]
    if len(unique_matches) > 1:
        logger.info("Ambiguous root_cause list: %s", value)
        return "unknown"

    logger.info("Unknown root_cause: %s", value)
    return "unknown"
