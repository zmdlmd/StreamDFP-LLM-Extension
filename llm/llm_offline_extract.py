import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from feature_mapping import load_event_mapping_config, map_llm_json_to_vector
from window_to_text import iter_window_records


LEGACY_SYSTEM_PROMPT = (
    "你是一个信息抽取器。"
    "你必须只输出一个严格 JSON 对象，不允许任何额外文字，不允许 markdown。"
    "root_cause 必须严格等于以下之一：media/interface/temperature/power/workload/unknown。"
    "root_cause 只能输出一个单词，禁止包含 '|' '/' 空格。"
    "events.type 必须在 monotonic_increase/spike/drop 中选择。"
    "若 ANOMALY_PERSISTENCE 较高且 TREND_DELTA 持续为正，优先 monotonic_increase；"
    "仅在短期突增时使用 spike；仅在显著下滑时使用 drop。"
    "events.feature 优先来自 ALLOWED_EVENT_FEATURES 列表；"
    "若与列表不一致，必须与窗口异常上下文语义一致且仍在 SMART 特征集合内。"
    "若证据不足，输出 unknown。"
)

LEGACY_USER_TEMPLATE = (
    "Disk window summary:\n{summary}\n\n"
    "请输出严格 JSON，字段必须齐全，格式如下（events 最多 3 条）：\n"
    "{{\"root_cause\":\"unknown\",\"risk_hint\":0.0,\"hardness\":0.0,\"confidence\":0.0,"
    "\"events\":[{{\"feature\":\"SMART_5\",\"type\":\"monotonic_increase\",\"severity\":0.0}}]}}\n"
    "ALLOWED_EVENT_FEATURES: {allowed_features}\n"
    "约束：\n"
    "- risk_hint/hardness/confidence ∈ [0,1]，保留两位小数\n"
    "- events 可为空数组 []，最多 3 条\n"
    "- 事件类型必须从 monotonic_increase/spike/drop 选择，避免全部使用同一类型\n"
    "- events.feature 优先从 ALLOWED_EVENT_FEATURES 中选择；若 ALLOWED_EVENT_FEATURES=none，则输出 events=[]\n"
    "- 若 RULE_SCORE 中某个根因得分 >= 0.80，优先选择该根因，除非摘要中明确冲突"
)

STRUCTURED_V2_SYSTEM_PROMPT = (
    "你是一个信息抽取器。"
    "你必须只输出一个严格 JSON 对象，不允许任何额外文字，不允许 markdown。"
    "你会收到固定结构块：WINDOW, DATA_QUALITY, RULE_SCORE, RULE_TOP2, ALLOWED_EVENT_FEATURES, ANOMALY_TABLE, CAUSE_EVIDENCE, RULE_PRED。"
    "root_cause 必须严格等于 media/interface/temperature/power/workload/unknown 之一。"
    "root_cause 只能输出一个词，不允许 | / 空格。"
    "events.type 必须在 monotonic_increase/spike/drop 中选择。"
    "若 persistence 高且 slope14 为正，优先 monotonic_increase；若 burst_ratio 高优先 spike；若 slope14 为负且显著下降用 drop。"
    "优先使用 ALLOWED_EVENT_FEATURES 中的特征；若为 none，则输出 events=[]。"
    "若 RULE_SCORE 最高分 >= 0.80，除非存在明确反证，否则优先该根因。"
)

STRUCTURED_V2_USER_TEMPLATE = (
    "Disk window summary (structured_v2):\n{summary}\n\n"
    "请严格按以下 JSON schema 输出（events 最多 3 条）：\n"
    "{{\"root_cause\":\"unknown\",\"risk_hint\":0.0,\"hardness\":0.0,\"confidence\":0.0,"
    "\"events\":[{{\"feature\":\"SMART_5\",\"type\":\"monotonic_increase\",\"severity\":0.0}}]}}\n"
    "ALLOWED_EVENT_FEATURES: {allowed_features}\n"
    "约束：\n"
    "- risk_hint/hardness/confidence ∈ [0,1]，保留两位小数\n"
    "- events 可为空数组 []，最多 3 条\n"
    "- events.feature 优先来自 ALLOWED_EVENT_FEATURES\n"
    "- 结合 RULE_TOP2.margin 与 ANOMALY_TABLE 中 persistence/slope/burst 决定 root_cause 和 events.type"
)

PROMPT_PROFILES = {"legacy", "structured_v2"}
RULE_BLEND_MODES = {"three_stage", "hard_gate"}
EVENT_TYPE_POLICIES = {"legacy", "strict"}

# Backward-compatible defaults.
SYSTEM_PROMPT = LEGACY_SYSTEM_PROMPT
USER_TEMPLATE = LEGACY_USER_TEMPLATE

REPAIR_SYSTEM_PROMPT = (
    "你是一个 JSON 修复器。"
    "把输入文本修复成严格 JSON 对象，只输出 JSON。"
    "禁止解释、禁止 markdown 代码块。"
)
REPAIR_USER_TEMPLATE = (
    "请修复下列模型输出，确保字段完整且为合法 JSON：\n"
    "{bad_output}\n\n"
    "必须包含 keys: root_cause, risk_hint, hardness, confidence, events"
)

ROOT_CAUSE_ENUM = {"media", "interface", "temperature", "power", "workload", "unknown"}
RULE_SCORE_CAUSES = ["media", "interface", "temperature", "power", "workload"]
EVENT_TYPES = {"monotonic_increase", "spike", "drop"}
GENERIC_EVENT_FEATURE_ALIASES = {
    "MEDIA": ["SMART_5", "SMART_197", "SMART_198", "SMART_187"],
    "INTERFACE": ["SMART_199", "SMART_188"],
    "TEMPERATURE": ["SMART_194", "SMART_190"],
    "POWER": ["SMART_192", "SMART_193", "SMART_12"],
    "WORKLOAD": ["SMART_9", "SMART_1"],
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        out = float(value)
        if out != out:  # NaN
            return float(default)
        return out
    except Exception:
        return float(default)


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _normalize_root_cause(value) -> str:
    if value is None:
        return "unknown"
    root = str(value).strip().lower()
    if root in ROOT_CAUSE_ENUM:
        return root
    return "unknown"


def _normalize_event_type(value) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    if s in EVENT_TYPES:
        return s
    if "increase" in s or "up" in s or "monotonic" in s:
        return "monotonic_increase"
    if "spike" in s or "burst" in s:
        return "spike"
    if "decrease" in s or "drop" in s or "down" in s:
        return "drop"
    return ""


def _normalize_event_feature(value, event_mapping: Optional[Dict] = None) -> str:
    if value is None:
        return ""
    text = str(value).upper().strip()
    m = re.search(r"SMART[_\- ]?(\d+)", text)
    if m:
        return f"SMART_{m.group(1)}"
    if text in GENERIC_EVENT_FEATURE_ALIASES:
        candidates = GENERIC_EVENT_FEATURE_ALIASES[text]
        if isinstance(event_mapping, dict):
            mapped_features = {
                _normalize_event_feature(feat)
                for feat in (event_mapping.get("event_features") or [])
            }
            for cand in candidates:
                if cand in mapped_features:
                    return cand
        return candidates[0]
    return text


def parse_rule_scores(summary: str) -> Dict[str, float]:
    scores = {cause: 0.0 for cause in RULE_SCORE_CAUSES}
    if not summary:
        return scores
    line = ""
    for row in str(summary).splitlines():
        if row.strip().startswith("RULE_SCORE:"):
            line = row
            break
    if not line:
        return scores
    for cause in RULE_SCORE_CAUSES:
        m = re.search(rf"{cause}\s*=\s*([0-9]+(?:\.[0-9]+)?)", line)
        if m:
            scores[cause] = _safe_float(m.group(1), 0.0)
    return scores


def parse_line_key_values(summary: str, prefix: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    if not summary:
        return values
    line = ""
    for row in str(summary).splitlines():
        if row.strip().startswith(prefix):
            line = row.strip()
            break
    if not line:
        return values
    payload = line.split(":", 1)[1].strip() if ":" in line else ""
    if not payload or payload.lower() == "none":
        return values
    for token in payload.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        feat = _normalize_event_feature(key)
        if not feat:
            continue
        values[feat] = _safe_float(value, 0.0)
    return values


def parse_anomaly_table(summary: str) -> Dict[str, Dict[str, float]]:
    """
    Parse structured_v2 anomaly rows:
    - feat=SMART_5|src=raw|...|persistence=0.72|slope14=+0.012|burst_ratio=1.25|severity=0.90|group=media
    """
    out: Dict[str, Dict[str, float]] = {}
    if not summary:
        return out

    lines = str(summary).splitlines()
    in_table = False
    for raw in lines:
        line = raw.strip()
        if not in_table:
            if line.startswith("ANOMALY_TABLE:"):
                in_table = True
            continue
        if not line.startswith("- "):
            break
        payload = line[2:].strip()
        if payload.lower() == "none":
            break
        fields: Dict[str, str] = {}
        for token in payload.split("|"):
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            fields[str(key).strip().lower()] = str(value).strip()
        feat = _normalize_event_feature(fields.get("feat"))
        if not feat:
            continue
        out[feat] = {
            "persistence": _clip01(_safe_float(fields.get("persistence"), 0.0)),
            "trend_delta": _safe_float(fields.get("slope14"), 0.0),
            "burst_ratio": _safe_float(fields.get("burst_ratio"), 0.0),
            "severity": _clip01(_safe_float(fields.get("severity"), 0.0)),
        }
    return out


def _resolve_prompt_profile(prompt_profile: str) -> Tuple[str, str]:
    key = str(prompt_profile or "legacy").strip().lower()
    if key not in PROMPT_PROFILES:
        key = "legacy"
    if key == "structured_v2":
        return STRUCTURED_V2_SYSTEM_PROMPT, STRUCTURED_V2_USER_TEMPLATE
    return LEGACY_SYSTEM_PROMPT, LEGACY_USER_TEMPLATE


def parse_allowed_event_features(summary: str) -> List[str]:
    if not summary:
        return []
    allowed: List[str] = []
    seen = set()

    for row in str(summary).splitlines():
        line = row.strip()
        if line.startswith("ALLOWED_EVENT_FEATURES:"):
            payload = line.split(":", 1)[1].strip()
            if not payload or payload.lower() == "none":
                return []
            for token in payload.split():
                feat = _normalize_event_feature(token)
                if feat and feat not in seen:
                    seen.add(feat)
                    allowed.append(feat)
            return allowed

    # Backward compatible fallback: infer from anomaly lines.
    for row in str(summary).splitlines():
        line = row.strip()
        if not line.startswith("- "):
            continue
        feat = ""
        m = re.match(r"-\s+(SMART[_\- ]?\d+)\b", line, flags=re.IGNORECASE)
        if m:
            feat = _normalize_event_feature(m.group(1))
        else:
            m2 = re.search(r"\bfeat=([^|\s]+)", line, flags=re.IGNORECASE)
            if m2:
                feat = _normalize_event_feature(m2.group(1))
        if feat and feat not in seen:
            seen.add(feat)
            allowed.append(feat)
    return allowed


def parse_group_signal(summary: str) -> Dict[str, Dict[str, float]]:
    # Example:
    # GROUP_SIGNAL: media=1/5:0.83 interface=0/2:0.00 temperature=1/3:0.66 ...
    out: Dict[str, Dict[str, float]] = {
        cause: {"active": 0.0, "available": 0.0, "max_severity": 0.0}
        for cause in RULE_SCORE_CAUSES
    }
    if not summary:
        return out

    line = ""
    for row in str(summary).splitlines():
        if row.strip().startswith("GROUP_SIGNAL:"):
            line = row.strip()
            break
    if not line:
        return out

    payload = line.split(":", 1)[1].strip() if ":" in line else ""
    if not payload or payload.lower() == "none":
        return out

    for token in payload.split():
        m = re.match(r"(media|interface|temperature|power|workload)\s*=\s*(\d+)\s*/\s*(\d+)\s*:\s*([0-9]+(?:\.[0-9]+)?)", token)
        if not m:
            continue
        cause = m.group(1)
        out[cause] = {
            "active": float(_safe_float(m.group(2), 0.0)),
            "available": float(_safe_float(m.group(3), 0.0)),
            "max_severity": float(_clip01(_safe_float(m.group(4), 0.0))),
        }
    return out


def parse_rule_top_cause(summary: str) -> str:
    scores = parse_rule_scores(summary)
    return max(scores, key=lambda c: scores.get(c, 0.0)) if scores else "unknown"


def _derive_fields(data: Dict) -> Dict:
    risk_hint = _clip01(_safe_float(data.get("risk_hint"), 0.0))
    root_cause = _normalize_root_cause(data.get("root_cause"))
    data["risk_hint"] = round(risk_hint, 2)
    data["hardness"] = round(_clip01(_safe_float(data.get("hardness"), 0.0)), 2)
    data["confidence"] = round(_clip01(_safe_float(data.get("confidence"), 0.0)), 2)
    data["near_positive"] = bool(risk_hint >= 0.6)
    data["label_noise_risk"] = round(_clip01(0.4 if root_cause == "unknown" and risk_hint > 0.35 else 0.1), 2)
    data["root_cause"] = root_cause
    return data


def normalize_llm_json(
    payload: Dict,
    summary: str,
    rule_score_gate: float,
    rule_score_soft_gate: float = 0.55,
    rule_blend_mode: str = "three_stage",
    event_type_policy: str = "legacy",
    event_quality_gate: float = 0.0,
    event_sev_sum_gate: float = 0.0,
    event_require_rule_match: bool = False,
    enforce_event_feature_whitelist: bool = False,
    strict_allowed_event_features: bool = False,
    event_min_count: int = 0,
    event_mapping: Optional[Dict] = None,
) -> Dict:
    data = payload if isinstance(payload, dict) else {}

    root_cause = _normalize_root_cause(data.get("root_cause"))
    risk_hint = round(_clip01(_safe_float(data.get("risk_hint"), 0.0)), 2)
    hardness = round(_clip01(_safe_float(data.get("hardness"), 0.0)), 2)
    confidence = round(_clip01(_safe_float(data.get("confidence"), 0.0)), 2)

    persistence_map = parse_line_key_values(summary, "ANOMALY_PERSISTENCE:")
    trend_delta_map = parse_line_key_values(summary, "TREND_DELTA:")
    anomaly_table = parse_anomaly_table(summary)
    for feat, metrics in anomaly_table.items():
        if feat not in persistence_map:
            persistence_map[feat] = _clip01(_safe_float(metrics.get("persistence"), 0.0))
        if feat not in trend_delta_map:
            trend_delta_map[feat] = _safe_float(metrics.get("trend_delta"), 0.0)

    events_raw = data.get("events")
    if not isinstance(events_raw, list):
        events_raw = []
    raw_event_count = len([e for e in events_raw if isinstance(e, dict)])

    mapping_features = set()
    if isinstance(event_mapping, dict):
        mapping_features = {
            _normalize_event_feature(feat)
            for feat in (event_mapping.get("event_features") or [])
            if _normalize_event_feature(feat)
        }

    allowed_features = set(parse_allowed_event_features(summary))
    events = []
    strict_event_type = str(event_type_policy or "legacy").strip().lower() == "strict"
    for event in events_raw[:3]:
        if not isinstance(event, dict):
            continue
        feature = _normalize_event_feature(event.get("feature"), event_mapping=event_mapping)
        event_type = _normalize_event_type(event.get("type"))
        if not feature:
            continue
        table_metrics = anomaly_table.get(feature, {})
        if strict_event_type:
            persistence = _clip01(_safe_float(table_metrics.get("persistence"), persistence_map.get(feature, 0.0)))
            trend_delta = _safe_float(table_metrics.get("trend_delta"), trend_delta_map.get(feature, 0.0))
            burst_ratio = _safe_float(table_metrics.get("burst_ratio"), 0.0)
            if burst_ratio >= 1.35:
                event_type = "spike"
            elif trend_delta <= -0.03:
                event_type = "drop"
            elif persistence >= 0.55 and trend_delta > 0.0:
                event_type = "monotonic_increase"
            elif trend_delta > 0.0:
                event_type = "monotonic_increase"
            elif trend_delta < 0.0:
                event_type = "drop"
            else:
                event_type = event_type or "monotonic_increase"
        if not event_type:
            continue
        relaxed_miss = False
        if allowed_features and feature not in allowed_features:
            if strict_allowed_event_features:
                continue
            # Relaxed mode: keep non-listed feature only if it is known by mapping.
            if mapping_features and feature not in mapping_features:
                continue
            relaxed_miss = True
        if enforce_event_feature_whitelist and mapping_features and feature not in mapping_features:
            continue
        severity = round(_clip01(_safe_float(event.get("severity"), 0.0)), 2)
        if relaxed_miss:
            severity = round(_clip01(severity * 0.85), 2)
        persistence = round(_clip01(_safe_float(table_metrics.get("persistence"), persistence_map.get(feature, 0.0))), 2)
        trend_delta = round(_safe_float(table_metrics.get("trend_delta"), trend_delta_map.get(feature, 0.0)), 3)
        events.append({
            "feature": feature,
            "type": event_type,
            "severity": severity,
            "persistence": persistence,
            "trend_delta": trend_delta,
        })

    scores = parse_rule_scores(summary)
    group_signal = parse_group_signal(summary)
    top_cause = max(scores, key=lambda k: scores[k]) if scores else "unknown"
    top_score = scores.get(top_cause, 0.0) if scores else 0.0
    top_group = group_signal.get(top_cause, {"active": 0.0, "max_severity": 0.0})
    top_active = int(_safe_float(top_group.get("active"), 0.0))
    top_group_sev = _clip01(_safe_float(top_group.get("max_severity"), 0.0))

    gate_hi = max(0.0, float(rule_score_gate))
    gate_soft = max(0.0, float(rule_score_soft_gate))
    if gate_soft > gate_hi:
        gate_soft = gate_hi

    blend_mode = str(rule_blend_mode or "three_stage").strip().lower()
    if blend_mode not in RULE_BLEND_MODES:
        blend_mode = "three_stage"

    if blend_mode == "hard_gate":
        root_cause = top_cause if top_score >= gate_hi else "unknown"
    else:
        if top_score >= gate_hi:
            root_cause = top_cause
        elif top_score >= gate_soft:
            # Soft zone: keep LLM prediction only with sufficient confidence; otherwise fallback to unknown.
            if root_cause == top_cause:
                root_cause = top_cause
            elif root_cause != "unknown" and confidence >= 0.80 and risk_hint >= 0.75:
                root_cause = root_cause
            elif confidence >= 0.62 and risk_hint >= 0.55:
                root_cause = top_cause
            else:
                root_cause = "unknown"
        else:
            root_cause = "unknown"

    est_noise = _clip01(0.4 if root_cause == "unknown" and risk_hint > 0.35 else 0.1)
    quality_base = _clip01(min(confidence, risk_hint) * (1.0 - est_noise))
    if events:
        avg_persistence = sum(_clip01(_safe_float(e.get("persistence"), 0.0)) for e in events) / float(len(events))
        trend_positive = sum(1 for e in events if _safe_float(e.get("trend_delta"), 0.0) > 0.0) / float(len(events))
    else:
        avg_persistence = 0.0
        trend_positive = 0.0
    quality_score = round(_clip01(0.75 * quality_base + 0.20 * avg_persistence + 0.05 * trend_positive), 4)

    if event_quality_gate > 0 and quality_score < float(event_quality_gate):
        events = []

    if event_require_rule_match and root_cause != top_cause:
        events = []

    if event_sev_sum_gate > 0:
        sev_sum = sum(_safe_float(e.get("severity"), 0.0) for e in events)
        if sev_sum < float(event_sev_sum_gate):
            events = []
    if event_min_count > 0 and len(events) < int(event_min_count):
        events = []

    if blend_mode == "three_stage" and root_cause == "unknown":
        # Relax in low-score zone only when event evidence is strong and aligned.
        relax_gate = max(0.0, gate_soft * 0.75)
        max_event_severity = max((_safe_float(e.get("severity"), 0.0) for e in events), default=0.0)
        if (
            top_score >= relax_gate
            and top_cause in ROOT_CAUSE_ENUM
            and top_cause != "unknown"
            and len(events) >= 1
            and max_event_severity >= 0.70
            and quality_score >= 0.35
        ):
            root_cause = top_cause
        elif (
            top_cause != "unknown"
            and top_active >= 1
            and top_group_sev >= 0.60
            and quality_score >= 0.25
            and top_score >= max(0.0, gate_soft * 0.55)
        ):
            # Secondary relaxation: allow rule-top cause when group-level signal is clearly active.
            root_cause = top_cause

    mapped_event_count = len(events)
    mapped_event_ratio = round(
        (mapped_event_count / float(raw_event_count)) if raw_event_count > 0 else 0.0,
        4,
    )

    normalized = {
        "root_cause": root_cause,
        "risk_hint": risk_hint,
        "hardness": hardness,
        "confidence": confidence,
        "events": events,
        "llm_q_score": quality_score,
        "llm_rule_match": bool(root_cause == top_cause),
        "llm_rule_top_cause": top_cause,
        "llm_rule_top_score": round(float(top_score), 4),
        "llm_mapped_event_ratio": mapped_event_ratio,
        "llm_event_count": int(raw_event_count),
        "llm_mapped_event_count": int(mapped_event_count),
    }
    return _derive_fields(normalized)


def compact_target_for_prompt(target: Dict) -> Dict:
    if not isinstance(target, dict):
        target = {}
    compact = {
        "root_cause": _normalize_root_cause(target.get("root_cause")),
        "risk_hint": round(_clip01(_safe_float(target.get("risk_hint"), 0.0)), 2),
        "hardness": round(_clip01(_safe_float(target.get("hardness"), 0.0)), 2),
        "confidence": round(_clip01(_safe_float(target.get("confidence"), 0.0)), 2),
        "events": [],
    }
    events = target.get("events")
    if isinstance(events, list):
        for event in events[:3]:
            if not isinstance(event, dict):
                continue
            feature = _normalize_event_feature(event.get("feature"))
            event_type = _normalize_event_type(event.get("type"))
            if not feature or not event_type:
                continue
            compact["events"].append({
                "feature": feature,
                "type": event_type,
                "severity": round(_clip01(_safe_float(event.get("severity"), 0.0)), 2),
            })
    return compact


def setup_logger(log_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("llm_offline_extract")
    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def build_messages(summary: str, references: List[Dict], prompt_profile: str = "legacy") -> List[Dict[str, str]]:
    system_prompt, user_template = _resolve_prompt_profile(prompt_profile)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    allowed_features = parse_allowed_event_features(summary)
    allowed_text = " ".join(allowed_features) if allowed_features else "none"

    for ref in references:
        ref_summary = ref.get("summary_text", "")
        ref_target = ref.get("target", {})
        if not ref_summary or not isinstance(ref_target, dict):
            continue
        ref_allowed = parse_allowed_event_features(ref_summary)
        ref_allowed_text = " ".join(ref_allowed) if ref_allowed else "none"
        messages.append({"role": "user", "content": user_template.format(summary=ref_summary, allowed_features=ref_allowed_text)})
        messages.append({"role": "assistant", "content": json.dumps(compact_target_for_prompt(ref_target), ensure_ascii=False)})

    messages.append({"role": "user", "content": user_template.format(summary=summary, allowed_features=allowed_text)})
    return messages


def extract_json(text: str) -> Dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    snippet = stripped[start : end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return {}


def default_json() -> Dict:
    base = {
        "events": [],
        "root_cause": "unknown",
        "risk_hint": 0.0,
        "hardness": 0.0,
        "confidence": 0.0,
    }
    return _derive_fields(base)


def log_info(logger, run_id: str, message: str, *args):
    logger.info("[run_id=%s] " + message, run_id, *args)


def build_repair_messages(raw_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
        {"role": "user", "content": REPAIR_USER_TEMPLATE.format(bad_output=raw_text[:4000])},
    ]


class TransformersBackend:
    def __init__(self, model_path: str, enable_thinking: bool, max_new_tokens: int, temperature: float, top_p: float):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
        self.enable_thinking = enable_thinking
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p

    def generate(self, batch_messages: List[List[Dict[str, str]]]) -> List[str]:
        prompts = []
        for messages in batch_messages:
            prompts.append(
                self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=self.enable_thinking,
                )
            )

        inputs = self.tokenizer(prompts, return_tensors="pt", padding=True).to(self.model.device)
        do_sample = self.temperature > 0
        gen_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": do_sample,
        }
        # Avoid passing sampling-only params when using greedy decoding.
        if do_sample:
            gen_kwargs["temperature"] = max(self.temperature, 1e-6)
            gen_kwargs["top_p"] = self.top_p

        outputs = self.model.generate(**inputs, **gen_kwargs)

        results = []
        for i in range(len(prompts)):
            out_ids = outputs[i][len(inputs.input_ids[i]):]
            results.append(self.tokenizer.decode(out_ids, skip_special_tokens=True))
        return results


class VLLMBackend:
    def __init__(
        self,
        model_path: str,
        enable_thinking: bool,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.9,
        max_model_len: int = None,
        enforce_eager: bool = False,
        max_num_batched_tokens: int = None,
    ):
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        llm_kwargs = {
            "model": model_path,
            "trust_remote_code": True,
            "tensor_parallel_size": max(1, int(tensor_parallel_size)),
            "gpu_memory_utilization": float(gpu_memory_utilization),
        }
        if max_model_len is not None and int(max_model_len) > 0:
            llm_kwargs["max_model_len"] = int(max_model_len)
        if max_num_batched_tokens is not None and int(max_num_batched_tokens) > 0:
            llm_kwargs["max_num_batched_tokens"] = int(max_num_batched_tokens)
        if enforce_eager:
            llm_kwargs["enforce_eager"] = True
        self.llm = LLM(**llm_kwargs)
        self.sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_new_tokens,
        )
        self.enable_thinking = enable_thinking

    def generate(self, batch_messages: List[List[Dict[str, str]]]) -> List[str]:
        prompts = []
        for messages in batch_messages:
            prompts.append(
                self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=self.enable_thinking,
                )
            )
        outputs = self.llm.generate(prompts, self.sampling_params)
        return [out.outputs[0].text for out in outputs]


def build_backend(
    backend: str,
    model_path: str,
    enable_thinking: bool,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    vllm_tensor_parallel_size: int,
    vllm_gpu_memory_utilization: float,
    vllm_max_model_len: int,
    vllm_enforce_eager: bool,
    vllm_max_num_batched_tokens: int,
):
    if backend == "vllm":
        try:
            import vllm  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "vLLM backend requested but vllm is not installed. "
                "Install with: pip install -U vllm"
            ) from exc
        return VLLMBackend(
            model_path,
            enable_thinking,
            max_new_tokens,
            temperature,
            top_p,
            tensor_parallel_size=vllm_tensor_parallel_size,
            gpu_memory_utilization=vllm_gpu_memory_utilization,
            max_model_len=vllm_max_model_len,
            enforce_eager=vllm_enforce_eager,
            max_num_batched_tokens=vllm_max_num_batched_tokens,
        )
    if backend == "transformers":
        return TransformersBackend(model_path, enable_thinking, max_new_tokens, temperature, top_p)
    raise ValueError(f"Unsupported backend: {backend}")


def load_existing_keys(out_path: str) -> set:
    if not out_path or not os.path.exists(out_path):
        return set()
    if out_path.endswith(".parquet"):
        df = pd.read_parquet(out_path)
    elif out_path.endswith(".jsonl"):
        df = pd.read_json(out_path, lines=True)
    else:
        return set()
    return set(zip(df["disk_id"].astype(str), df["window_end_time"].astype(str)))


def write_rows(out_path: str, rows: List[Dict]):
    if out_path.endswith(".jsonl"):
        with open(out_path, "a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return

    df_new = pd.DataFrame(rows)
    if os.path.exists(out_path):
        df_old = pd.read_parquet(out_path)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_parquet(out_path, index=False)


def iter_window_rows_from_text(path: str, max_windows: int = None) -> Iterable[Tuple[str, str, str]]:
    count = 0
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
        for _, row in df.iterrows():
            disk_id = str(row["disk_id"])
            window_end_time = str(row["window_end_time"])
            summary_text = str(row.get("summary_text", ""))
            yield disk_id, window_end_time, summary_text
            count += 1
            if max_windows is not None and count >= max_windows:
                return
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            disk_id = str(row["disk_id"])
            window_end_time = str(row["window_end_time"])
            summary_text = str(row.get("summary_text", ""))
            yield disk_id, window_end_time, summary_text
            count += 1
            if max_windows is not None and count >= max_windows:
                return


def estimate_total_windows(path: Optional[str], max_windows: Optional[int]) -> Optional[int]:
    if not path or not os.path.exists(path):
        return None
    total = 0
    if path.endswith(".parquet"):
        total = int(len(pd.read_parquet(path)))
    else:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    total += 1
    if max_windows is not None:
        total = min(total, int(max_windows))
    return total


def iter_window_rows_from_data(
    data_root: str,
    features_path: str,
    window_days: int,
    date_format: str,
    disk_model: str,
    max_windows: int,
) -> Iterable[Tuple[str, str, str]]:
    from window_to_text import load_features

    features = load_features(features_path, data_root)
    for disk_id, window_end_time, summary, _, _, _ in iter_window_records(
        data_root,
        features,
        window_days,
        date_format,
        disk_model,
        max_windows,
):
        yield disk_id, window_end_time, summary


def _normalize_model_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _reference_example_score(example: Dict) -> float:
    target = example.get("target", {})
    if not isinstance(target, dict):
        return 0.0
    confidence = _clip01(_safe_float(target.get("confidence"), 0.0))
    risk_hint = _clip01(_safe_float(target.get("risk_hint"), 0.0))
    events = target.get("events")
    events_bonus = 0.0
    if isinstance(events, list):
        events_bonus = min(len(events), 3) / 3.0
    return 0.55 * confidence + 0.35 * risk_hint + 0.10 * events_bonus


def select_reference_examples(
    reference_payload: Dict,
    max_examples: int,
    per_cause_cap: int = 2,
) -> List[Dict]:
    examples = reference_payload.get("examples", []) if isinstance(reference_payload, dict) else []
    if not isinstance(examples, list):
        examples = []
    if max_examples is None or int(max_examples) <= 0:
        max_examples = len(examples)
    max_examples = max(0, int(max_examples))
    if max_examples == 0 or not examples:
        return []

    per_cause_cap = max(1, int(per_cause_cap))
    by_cause: Dict[str, List[Dict]] = {cause: [] for cause in ROOT_CAUSE_ENUM}
    for example in examples:
        if not isinstance(example, dict):
            continue
        target = example.get("target", {})
        cause = _normalize_root_cause(target.get("root_cause")) if isinstance(target, dict) else "unknown"
        by_cause[cause].append(example)

    for cause in by_cause:
        by_cause[cause].sort(key=_reference_example_score, reverse=True)

    cause_order = ["media", "interface", "temperature", "power", "workload", "unknown"]
    selected: List[Dict] = []
    seen = set()

    # Round-robin first pass: keep cause coverage before filling the remainder.
    rounds = 0
    while len(selected) < max_examples and rounds < per_cause_cap:
        picked_this_round = False
        for cause in cause_order:
            bucket = by_cause.get(cause, [])
            if rounds >= len(bucket):
                continue
            example = bucket[rounds]
            summary_key = str(example.get("summary_text", ""))[:256]
            key = (
                str(example.get("disk_id", "")),
                str(example.get("window_end_time", "")),
                cause,
                summary_key,
            )
            if key in seen:
                continue
            seen.add(key)
            selected.append(example)
            picked_this_round = True
            if len(selected) >= max_examples:
                break
        if not picked_this_round:
            break
        rounds += 1

    if len(selected) >= max_examples:
        return selected[:max_examples]

    leftovers: List[Dict] = []
    for cause in cause_order:
        bucket = by_cause.get(cause, [])
        leftovers.extend(bucket[rounds:])
    leftovers.sort(key=_reference_example_score, reverse=True)
    for example in leftovers:
        if len(selected) >= max_examples:
            break
        summary_key = str(example.get("summary_text", ""))[:256]
        key = (
            str(example.get("disk_id", "")),
            str(example.get("window_end_time", "")),
            _normalize_root_cause(example.get("target", {}).get("root_cause"))
            if isinstance(example.get("target", {}), dict)
            else "unknown",
            summary_key,
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(example)

    return selected[:max_examples]


def load_reference_payload(path: str) -> Dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else {}


def load_window_text_profile_meta(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    try:
        if path.endswith(".parquet"):
            df = pd.read_parquet(path)
            if len(df) == 0:
                return {}
            row = df.iloc[0]
            return {
                "rule_model_key": str(row.get("rule_model_key", "")),
                "rule_medium": str(row.get("rule_medium", "")),
                "rule_vendor": str(row.get("rule_vendor", "")),
                "rule_profile_id": str(row.get("rule_profile_id", "")),
                "summary_schema": str(row.get("summary_schema", "")),
            }
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                return {
                    "rule_model_key": str(row.get("rule_model_key", "")),
                    "rule_medium": str(row.get("rule_medium", "")),
                    "rule_vendor": str(row.get("rule_vendor", "")),
                    "rule_profile_id": str(row.get("rule_profile_id", "")),
                    "summary_schema": str(row.get("summary_schema", "")),
                }
    except Exception:
        return {}
    return {}


def resolve_required_causes_arg(
    raw_cli: str,
    dataset_profile: str,
    reference_payload: Dict,
    explicit_cli: bool,
) -> Tuple[str, str]:
    if explicit_cli:
        return raw_cli, "cli"

    recommended = reference_payload.get("recommended_fewshot_required_causes")
    if not recommended and isinstance(reference_payload.get("profile_resolved"), dict):
        recommended = reference_payload.get("profile_resolved", {}).get("recommended_fewshot_required_causes")
    if isinstance(recommended, (list, tuple)) and recommended:
        raw = ",".join(str(x).strip().lower() for x in recommended if str(x).strip())
        if raw:
            return raw, "reference"
    if isinstance(recommended, str) and recommended.strip():
        return recommended.strip().lower(), "reference"

    profile_defaults = {
        "hi7": "media,interface,temperature,power,unknown",
        "hdd": "media,interface,temperature,power,unknown",
        "mc1": "media,interface,temperature,power,workload,unknown",
        "ssd": "media,interface,temperature,power,workload,unknown",
    }
    key = str(dataset_profile or "auto").strip().lower()
    if key in profile_defaults:
        return profile_defaults[key], f"dataset:{key}"
    return raw_cli, "default"


def parse_required_causes(raw: str) -> List[str]:
    if raw is None:
        return []
    seen = set()
    causes = []
    for token in str(raw).split(","):
        cause = token.strip().lower()
        if not cause:
            continue
        if cause not in ROOT_CAUSE_ENUM:
            raise ValueError(f"Invalid cause in --fewshot_required_causes: {cause}")
        if cause in seen:
            continue
        seen.add(cause)
        causes.append(cause)
    return causes


def count_reference_coverage(references: List[Dict]) -> Dict[str, int]:
    coverage = {cause: 0 for cause in sorted(ROOT_CAUSE_ENUM)}
    for ref in references:
        target = ref.get("target", {})
        if not isinstance(target, dict):
            continue
        cause = _normalize_root_cause(target.get("root_cause"))
        coverage[cause] += 1
    return coverage


def choose_references(
    references: List[Dict],
    fewshot_mode: str,
    required_causes: List[str],
    min_per_cause: int,
) -> Tuple[List[Dict], Dict[str, int], List[str]]:
    coverage = count_reference_coverage(references)
    missing = [cause for cause in required_causes if coverage.get(cause, 0) < min_per_cause]

    if fewshot_mode == "off":
        return [], coverage, missing
    if fewshot_mode == "auto" and missing:
        return [], coverage, missing
    return references, coverage, missing


def process_batch(
    summaries: List[str],
    keys: List[Tuple[str, str]],
    backend,
    logger,
    references: List[Dict],
    run_id: str,
    parse_repair_retries: int,
    write_root_cause_pred: bool,
    prompt_profile: str,
    rule_score_gate: float,
    rule_score_soft_gate: float,
    rule_blend_mode: str,
    event_type_policy: str,
    event_quality_gate: float,
    event_sev_sum_gate: float,
    event_require_rule_match: bool,
    enforce_event_feature_whitelist: bool,
    strict_allowed_event_features: bool,
    event_min_count: int,
    emit_quality_meta: bool,
    event_mapping: Dict,
) -> List[Dict]:
    batch_messages = [build_messages(summary, references, prompt_profile=prompt_profile) for summary in summaries]
    outputs = backend.generate(batch_messages)

    rows = []
    for (disk_id, window_end_time), summary, text in zip(keys, summaries, outputs):
        raw_data = extract_json(text)
        parse_source = "direct"
        if not raw_data and parse_repair_retries > 0:
            repair_text = text
            for _ in range(parse_repair_retries):
                repaired_outputs = backend.generate([build_repair_messages(repair_text)])
                if not repaired_outputs:
                    break
                repair_text = repaired_outputs[0]
                repaired = extract_json(repair_text)
                if repaired:
                    raw_data = repaired
                    parse_source = "repair"
                    log_info(logger, run_id, "Repaired invalid JSON for key=%s,%s", disk_id, window_end_time)
                    break
        if not raw_data:
            log_info(logger, run_id, "Failed to parse JSON for key=%s,%s", disk_id, window_end_time)
            raw_data = default_json()
            parse_source = "default"
        data = normalize_llm_json(
            raw_data,
            summary,
            rule_score_gate,
            rule_score_soft_gate=rule_score_soft_gate,
            rule_blend_mode=rule_blend_mode,
            event_type_policy=event_type_policy,
            event_quality_gate=event_quality_gate,
            event_sev_sum_gate=event_sev_sum_gate,
            event_require_rule_match=event_require_rule_match,
            enforce_event_feature_whitelist=enforce_event_feature_whitelist,
            strict_allowed_event_features=strict_allowed_event_features,
            event_min_count=event_min_count,
            event_mapping=event_mapping,
        )
        vec, meta = map_llm_json_to_vector(data, mapping=event_mapping)
        row = {
            "disk_id": disk_id,
            "window_end_time": window_end_time,
            "parse_source": parse_source,
        }
        for i, v in enumerate(vec):
            row[f"z_llm_{i}"] = float(v)
        row.update(meta)
        if write_root_cause_pred:
            root = str(data.get("root_cause", "unknown")).strip().lower()
            row["root_cause_pred"] = root if root in ROOT_CAUSE_ENUM else "unknown"
        if emit_quality_meta:
            row["llm_q_score"] = round(_clip01(_safe_float(data.get("llm_q_score"), 0.0)), 4)
            row["llm_rule_match"] = bool(data.get("llm_rule_match", False))
            row["llm_rule_top_cause"] = _normalize_root_cause(data.get("llm_rule_top_cause"))
            row["llm_rule_top_score"] = round(_clip01(_safe_float(data.get("llm_rule_top_score"), 0.0)), 4)
            row["llm_mapped_event_ratio"] = round(_clip01(_safe_float(data.get("llm_mapped_event_ratio"), 0.0)), 4)
            row["llm_event_count"] = int(_safe_float(data.get("llm_event_count"), 0.0))
            row["llm_mapped_event_count"] = int(_safe_float(data.get("llm_mapped_event_count"), 0.0))
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output cache path (.parquet or .jsonl)")
    parser.add_argument("--model", required=True, help="Local model path")
    parser.add_argument("--window_text_path", default=None, help="Path to window text (.jsonl or .parquet)")
    parser.add_argument("--reference_examples", default=None, help="Reference examples json produced by window_to_text.py")
    parser.add_argument("--reference_max_examples", type=int, default=10)
    parser.add_argument(
        "--fewshot_per_cause_cap",
        type=int,
        default=2,
        help="Max few-shot examples per root cause before filling the remaining slots",
    )
    parser.add_argument(
        "--fewshot_mode",
        default="auto",
        choices=["auto", "force", "off"],
        help="Few-shot selection mode: auto disables few-shot when coverage is insufficient",
    )
    parser.add_argument(
        "--fewshot_required_causes",
        default="media,interface,temperature,power,workload,unknown",
        help="Comma-separated root causes required for few-shot coverage check",
    )
    parser.add_argument(
        "--dataset_profile",
        default="auto",
        choices=["auto", "hi7", "mc1", "hdd", "ssd"],
        help="Dataset profile to set default few-shot required causes when CLI is not explicit",
    )
    parser.add_argument("--fewshot_min_per_cause", type=int, default=1, help="Required samples per cause in few-shot auto mode")
    parser.add_argument(
        "--event_mapping_config",
        default=None,
        help="Event mapping yaml/json to define EVENT_FEATURES/EVENT_TYPES for z_llm vectors",
    )

    # backward compatible fallback (not preferred)
    parser.add_argument("--data_root", default=None, help="Fallback: directory with daily CSV files")
    parser.add_argument("--features_path", default=None, help="Fallback: selected feature list")
    parser.add_argument("--window_days", type=int, default=30, help="Fallback sliding window size")
    parser.add_argument("--date_format", default="%Y-%m-%d", help="Date format for CSV filenames")
    parser.add_argument("--disk_model", default=None, help="Only extract windows for a specific disk model")

    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for LLM inference")
    parser.add_argument("--backend", default="auto", choices=["auto", "vllm", "transformers"], help="LLM backend")
    parser.add_argument("--max_new_tokens", type=int, default=180)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--enable_thinking", action="store_true")
    parser.add_argument("--vllm_tensor_parallel_size", type=int, default=1, help="vLLM tensor parallel size")
    parser.add_argument(
        "--vllm_gpu_memory_utilization",
        type=float,
        default=0.90,
        help="vLLM target GPU memory utilization (0~1)",
    )
    parser.add_argument("--vllm_max_model_len", type=int, default=None, help="Optional vLLM max model length")
    parser.add_argument("--vllm_enforce_eager", action="store_true", help="Enable vLLM eager mode for compatibility")
    parser.add_argument(
        "--vllm_max_num_batched_tokens",
        type=int,
        default=None,
        help="Optional vLLM scheduler max_num_batched_tokens (for higher effective throughput)",
    )
    parser.add_argument("--max_windows", type=int, default=None, help="Limit number of windows for testing")
    parser.add_argument("--flush_every", type=int, default=128, help="Write cache every N new rows (0 disables early flush)")
    parser.add_argument("--log_every_batches", type=int, default=10, help="Log progress every N processed batches")
    parser.add_argument("--parse_repair_retries", type=int, default=1, help="Retry times when JSON parsing fails (0 disables)")
    parser.add_argument("--write_root_cause_pred", action="store_true", help="Also persist normalized root_cause_pred")
    parser.add_argument(
        "--prompt_profile",
        default="legacy",
        choices=["legacy", "structured_v2"],
        help="Prompt template profile",
    )
    parser.add_argument("--rule_score_gate", type=float, default=0.80, help="High gate for RULE_SCORE top cause")
    parser.add_argument(
        "--rule_score_soft_gate",
        type=float,
        default=0.55,
        help="Soft gate for mixed rule+LLM decision zone; should be <= --rule_score_gate",
    )
    parser.add_argument(
        "--rule_blend_mode",
        default="three_stage",
        choices=["three_stage", "hard_gate"],
        help="Rule/LLM blending mode",
    )
    parser.add_argument(
        "--event_type_policy",
        default="legacy",
        choices=["legacy", "strict"],
        help="Event type assignment policy after normalization",
    )
    parser.add_argument("--event_quality_gate", type=float, default=0.0, help="Optional event gate on quality score q=min(confidence,risk_hint)*(1-noise)")
    parser.add_argument("--event_sev_sum_gate", type=float, default=0.0, help="Optional gate on sum of event severity after normalization")
    parser.add_argument("--event_require_rule_match", action="store_true", help="When enabled, keep events only if normalized root_cause matches RULE_SCORE top cause")
    parser.add_argument(
        "--enforce_event_feature_whitelist",
        action="store_true",
        help="Require event.feature to be in event_mapping feature whitelist before keeping the event",
    )
    parser.add_argument(
        "--strict_allowed_event_features",
        action="store_true",
        help="Strictly require event.feature to be in ALLOWED_EVENT_FEATURES from summary_text",
    )
    parser.add_argument(
        "--event_min_count",
        type=int,
        default=0,
        help="Drop events when kept event count is below this threshold after normalization",
    )
    parser.add_argument(
        "--emit_quality_meta",
        action="store_true",
        help="Persist quality diagnostics fields: llm_q_score/llm_rule_match/llm_mapped_event_ratio/llm_event_count",
    )
    parser.add_argument(
        "--show_progress",
        dest="show_progress",
        action="store_true",
        default=True,
        help="Print overall progress percentage to stdout (enabled by default)",
    )
    parser.add_argument(
        "--no_progress",
        dest="show_progress",
        action="store_false",
        help="Disable stdout progress logs",
    )
    args = parser.parse_args()

    if not args.window_text_path and not args.data_root:
        raise ValueError("Either --window_text_path or --data_root must be provided")

    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "llm_offline_extract.log")
    logger = setup_logger(log_path)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    log_info(logger, run_id, "Run started out=%s backend=%s model=%s", args.out, args.backend, args.model)
    log_info(
        logger,
        run_id,
        (
            "Prompt prompt_profile=%s rule_blend_mode=%s event_type_policy=%s "
            "Gates rule_score_gate=%.3f rule_score_soft_gate=%.3f "
            "event_quality_gate=%.3f event_sev_sum_gate=%.3f "
            "event_require_rule_match=%s enforce_event_feature_whitelist=%s "
            "strict_allowed_event_features=%s event_min_count=%d"
        ),
        str(args.prompt_profile),
        str(args.rule_blend_mode),
        str(args.event_type_policy),
        float(args.rule_score_gate),
        float(args.rule_score_soft_gate),
        float(args.event_quality_gate),
        float(args.event_sev_sum_gate),
        bool(args.event_require_rule_match),
        bool(args.enforce_event_feature_whitelist),
        bool(args.strict_allowed_event_features),
        int(args.event_min_count),
    )

    if args.out.endswith(".parquet"):
        try:
            import pyarrow  # noqa: F401
        except Exception:
            raise RuntimeError("pyarrow is required for .parquet output. Use --out llm_cache.jsonl instead.")

    event_mapping = load_event_mapping_config(args.event_mapping_config)
    log_info(
        logger,
        run_id,
        "Event mapping dim=%d features=%d types=%d",
        int(event_mapping.get("vector_dim", 0)),
        len(event_mapping.get("event_features", [])),
        len(event_mapping.get("event_types", [])),
    )

    reference_payload = load_reference_payload(args.reference_examples)
    references_pool = reference_payload.get("examples", []) if isinstance(reference_payload, dict) else []
    if not isinstance(references_pool, list):
        references_pool = []

    window_meta = load_window_text_profile_meta(args.window_text_path)
    if window_meta:
        log_info(
            logger,
            run_id,
            "Window profile model=%s medium=%s vendor=%s profile=%s summary_schema=%s",
            window_meta.get("rule_model_key", ""),
            window_meta.get("rule_medium", ""),
            window_meta.get("rule_vendor", ""),
            window_meta.get("rule_profile_id", ""),
            window_meta.get("summary_schema", ""),
        )
    reference_scope = reference_payload.get("reference_scope", {}) if isinstance(reference_payload, dict) else {}
    ref_model_key = ""
    if isinstance(reference_scope, dict):
        ref_model_key = str(reference_scope.get("rule_model_key", "") or reference_scope.get("disk_model_key", ""))
    if not ref_model_key and isinstance(reference_payload.get("profile_resolved"), dict):
        ref_model_key = str(reference_payload["profile_resolved"].get("rule_model_key", ""))
    win_model_key = str(window_meta.get("rule_model_key", ""))
    model_mismatch = bool(ref_model_key and win_model_key and _normalize_model_key(ref_model_key) != _normalize_model_key(win_model_key))
    if model_mismatch:
        log_info(
            logger,
            run_id,
            "Reference model mismatch: reference=%s window_text=%s",
            ref_model_key,
            win_model_key,
        )
    required_causes_raw, required_source = resolve_required_causes_arg(
        args.fewshot_required_causes,
        args.dataset_profile,
        reference_payload,
        explicit_cli=("--fewshot_required_causes" in sys.argv),
    )
    required_causes = parse_required_causes(required_causes_raw)
    references, coverage, missing = choose_references(
        references_pool,
        args.fewshot_mode,
        required_causes,
        max(1, int(args.fewshot_min_per_cause)),
    )
    if model_mismatch and args.fewshot_mode != "force":
        references = []
        log_info(logger, run_id, "Few-shot disabled due to reference/window_text model mismatch")
    else:
        references = select_reference_examples(
            {"examples": references},
            args.reference_max_examples,
            per_cause_cap=max(1, int(args.fewshot_per_cause_cap)),
        )
    log_info(
        logger,
        run_id,
        "Reference coverage media=%d interface=%d temperature=%d power=%d workload=%d unknown=%d (required=%s source=%s)",
        coverage.get("media", 0),
        coverage.get("interface", 0),
        coverage.get("temperature", 0),
        coverage.get("power", 0),
        coverage.get("workload", 0),
        coverage.get("unknown", 0),
        ",".join(required_causes),
        required_source,
    )
    if args.fewshot_mode == "off":
        log_info(logger, run_id, "Few-shot disabled by --fewshot_mode=off")
    elif args.fewshot_mode == "auto" and missing:
        log_info(
            logger,
            run_id,
            "Few-shot disabled by coverage check (missing causes=%s, min_per_cause=%d)",
            ",".join(missing),
            max(1, int(args.fewshot_min_per_cause)),
        )
    elif args.fewshot_mode == "force" and missing:
        log_info(
            logger,
            run_id,
            "Few-shot forced despite missing coverage (missing causes=%s, min_per_cause=%d)",
            ",".join(missing),
            max(1, int(args.fewshot_min_per_cause)),
        )
    log_info(
        logger,
        run_id,
        "Loaded %d reference examples (effective) from pool=%d max_examples=%d per_cause_cap=%d",
        len(references),
        len(references_pool),
        int(args.reference_max_examples),
        max(1, int(args.fewshot_per_cause_cap)),
    )

    existing_keys = load_existing_keys(args.out)
    log_info(logger, run_id, "Loaded %d existing cache keys", len(existing_keys))

    resolved_backend = args.backend
    if args.backend == "auto":
        try:
            import vllm  # noqa: F401

            resolved_backend = "vllm"
        except Exception:
            resolved_backend = "transformers"

    log_info(logger, run_id, "Resolved backend=%s", resolved_backend)

    backend = build_backend(
        resolved_backend,
        args.model,
        args.enable_thinking,
        args.max_new_tokens,
        args.temperature,
        args.top_p,
        args.vllm_tensor_parallel_size,
        args.vllm_gpu_memory_utilization,
        args.vllm_max_model_len,
        args.vllm_enforce_eager,
        args.vllm_max_num_batched_tokens,
    )

    if args.window_text_path:
        row_iter = iter_window_rows_from_text(args.window_text_path, args.max_windows)
        expected_total = estimate_total_windows(args.window_text_path, args.max_windows)
    else:
        if not args.features_path:
            raise ValueError("--features_path is required when using fallback --data_root mode")
        log_info(logger, run_id, "Using fallback direct csv mode. Recommend using window_to_text.py first.")
        row_iter = iter_window_rows_from_data(
            args.data_root,
            args.features_path,
            args.window_days,
            args.date_format,
            args.disk_model,
            args.max_windows,
        )
        expected_total = None

    if expected_total is not None:
        log_info(logger, run_id, "Estimated total windows=%d", expected_total)
        if args.show_progress:
            print(f"[{run_id}] total={expected_total} windows")

    batch_summaries: List[str] = []
    batch_keys: List[Tuple[str, str]] = []
    rows_to_write: List[Dict] = []
    batches_done = 0
    rows_new = 0
    rows_skipped = 0
    rows_seen = 0
    t0 = time.time()

    for disk_id, window_end_time, summary in row_iter:
        rows_seen += 1
        key = (disk_id, window_end_time)
        if key in existing_keys:
            rows_skipped += 1
            continue
        batch_summaries.append(summary)
        batch_keys.append(key)

        if len(batch_summaries) >= args.batch_size:
            batch_rows = process_batch(
                batch_summaries,
                batch_keys,
                backend,
                logger,
                references,
                run_id,
                parse_repair_retries=max(0, int(args.parse_repair_retries)),
                write_root_cause_pred=args.write_root_cause_pred,
                prompt_profile=str(args.prompt_profile),
                rule_score_gate=float(args.rule_score_gate),
                rule_score_soft_gate=float(args.rule_score_soft_gate),
                rule_blend_mode=str(args.rule_blend_mode),
                event_type_policy=str(args.event_type_policy),
                event_quality_gate=float(args.event_quality_gate),
                event_sev_sum_gate=float(args.event_sev_sum_gate),
                event_require_rule_match=bool(args.event_require_rule_match),
                enforce_event_feature_whitelist=bool(args.enforce_event_feature_whitelist),
                strict_allowed_event_features=bool(args.strict_allowed_event_features),
                event_min_count=max(0, int(args.event_min_count)),
                emit_quality_meta=bool(args.emit_quality_meta),
                event_mapping=event_mapping,
            )
            rows_to_write.extend(batch_rows)
            rows_new += len(batch_rows)
            batches_done += 1
            if args.log_every_batches > 0 and batches_done % args.log_every_batches == 0:
                elapsed = max(time.time() - t0, 1e-6)
                speed = rows_new / elapsed
                if expected_total is not None and expected_total > 0:
                    pct = 100.0 * rows_seen / float(expected_total)
                    progress_msg = (
                        "Progress batches=%d seen=%d/%d(%.2f%%) new_rows=%d skipped=%d "
                        "pending_flush=%d speed=%.2f rows/s"
                    )
                    log_info(
                        logger,
                        run_id,
                        progress_msg,
                        batches_done,
                        rows_seen,
                        expected_total,
                        pct,
                        rows_new,
                        rows_skipped,
                        len(rows_to_write),
                        speed,
                    )
                    if args.show_progress:
                        print(
                            f"[{run_id}] {rows_seen}/{expected_total} ({pct:.2f}%) "
                            f"new={rows_new} skip={rows_skipped} speed={speed:.2f} rows/s"
                        )
                else:
                    progress_msg = "Progress batches=%d new_rows=%d skipped=%d pending_flush=%d speed=%.2f rows/s"
                    log_info(
                        logger,
                        run_id,
                        progress_msg,
                        batches_done,
                        rows_new,
                        rows_skipped,
                        len(rows_to_write),
                        speed,
                    )
                    if args.show_progress:
                        print(
                            f"[{run_id}] rows_seen={rows_seen} new={rows_new} "
                            f"skip={rows_skipped} speed={speed:.2f} rows/s"
                        )
            if args.flush_every > 0 and len(rows_to_write) >= args.flush_every:
                write_rows(args.out, rows_to_write)
                log_info(logger, run_id, "Flushed %d rows to %s", len(rows_to_write), args.out)
                rows_to_write = []
            batch_summaries = []
            batch_keys = []

    if batch_summaries:
        batch_rows = process_batch(
            batch_summaries,
            batch_keys,
            backend,
            logger,
            references,
            run_id,
            parse_repair_retries=max(0, int(args.parse_repair_retries)),
            write_root_cause_pred=args.write_root_cause_pred,
            prompt_profile=str(args.prompt_profile),
            rule_score_gate=float(args.rule_score_gate),
            rule_score_soft_gate=float(args.rule_score_soft_gate),
            rule_blend_mode=str(args.rule_blend_mode),
            event_type_policy=str(args.event_type_policy),
            event_quality_gate=float(args.event_quality_gate),
            event_sev_sum_gate=float(args.event_sev_sum_gate),
            event_require_rule_match=bool(args.event_require_rule_match),
            enforce_event_feature_whitelist=bool(args.enforce_event_feature_whitelist),
            strict_allowed_event_features=bool(args.strict_allowed_event_features),
            event_min_count=max(0, int(args.event_min_count)),
            emit_quality_meta=bool(args.emit_quality_meta),
            event_mapping=event_mapping,
        )
        rows_to_write.extend(batch_rows)
        rows_new += len(batch_rows)
        batches_done += 1
    if rows_to_write:
        write_rows(args.out, rows_to_write)
        log_info(logger, run_id, "Final flush %d rows to %s", len(rows_to_write), args.out)

    elapsed = max(time.time() - t0, 1e-6)
    speed = rows_new / elapsed
    if expected_total is not None and expected_total > 0:
        pct = 100.0 * rows_seen / float(expected_total)
        log_info(
            logger,
            run_id,
            "Done batches=%d seen=%d/%d(%.2f%%) new_rows=%d skipped=%d speed=%.2f rows/s out=%s",
            batches_done,
            rows_seen,
            expected_total,
            pct,
            rows_new,
            rows_skipped,
            speed,
            args.out,
        )
        if args.show_progress:
            print(
                f"[{run_id}] done {rows_seen}/{expected_total} ({pct:.2f}%) "
                f"new={rows_new} skip={rows_skipped} speed={speed:.2f} rows/s"
            )
    else:
        log_info(
            logger,
            run_id,
            "Done batches=%d new_rows=%d skipped=%d speed=%.2f rows/s out=%s",
            batches_done,
            rows_new,
            rows_skipped,
            speed,
            args.out,
        )
        if args.show_progress:
            print(f"[{run_id}] done new={rows_new} skip={rows_skipped} speed={speed:.2f} rows/s")


if __name__ == "__main__":
    main()
