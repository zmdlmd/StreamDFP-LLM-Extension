import sys
import datetime
import getopt
import os
import json
import re
import time
import builtins
import pandas as pd
import pickle
from core_utils.abstract_predict import AbstractPredict
from utils.memory import Memory
from utils.arff import Arff

DEFAULT_POLICY = {
    "enabled": True,
    "min_q_score": 0.0,
    "min_rule_match": False,
    "min_mapped_event_ratio": 0.0,
    "drop_unknown_root": False,
    "allowed_root_causes": [],
    "keep_dims": "all",
    "llm_scale_alpha": 1.0,
    "gate_mode": "hard",
    "soft_min_weight": 0.0,
    "dense_meta_pack": False,
    "dense_meta_dims": "60,61,62,63,64,65,66,67,68,69",
    "dense_meta_scale": 1.0,
    "fallback": "nollm",
}

KEEP_DIMS_PRESETS = {
    "event_top3_plus_meta": [6, 7, 9, 11, 12, 13, 16, 34, 46],
    "event_top8_plus_meta": [6, 7, 9, 11, 12, 13, 46, 34, 16, 25, 31, 55, 28, 37],
}

_STDOUT_BROKEN = False


def _safe_print(*args, **kwargs):
    global _STDOUT_BROKEN
    if _STDOUT_BROKEN:
        return
    try:
        builtins.print(*args, **kwargs)
    except BrokenPipeError:
        _STDOUT_BROKEN = True


print = _safe_print


def _normalize_model_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        out = float(value)
        if out != out:
            return float(default)
        return out
    except Exception:
        return float(default)


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    token = str(value).strip().lower()
    if token in ("1", "true", "yes", "y", "on"):
        return True
    if token in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def _clip01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _format_duration(seconds):
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _print_progress(tag, index, total, start_ts, cur_date, every):
    if _STDOUT_BROKEN:
        return
    step = max(1, int(every))
    if total <= 0:
        return
    if index != 1 and index % step != 0 and index != total:
        return
    elapsed = time.time() - start_ts
    pct = 100.0 * float(index) / float(total)
    rate = float(index) / max(elapsed, 1e-6)
    remain = total - index
    eta = _format_duration(remain / rate) if rate > 0 else "--:--"
    print(
        f"[run.py] {tag} {index}/{total} ({pct:.2f}%) elapsed={_format_duration(elapsed)} eta={eta} date={cur_date}",
        flush=True,
    )


def _normalize_root_cause(value):
    token = str(value or "").strip().lower()
    allowed = {"media", "interface", "temperature", "power", "workload", "unknown"}
    return token if token in allowed else "unknown"


def _parse_root_cause_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        tokens = [t.strip() for t in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        tokens = [str(t).strip() for t in value]
    else:
        return []
    out = []
    seen = set()
    for token in tokens:
        cause = _normalize_root_cause(token)
        if cause in seen:
            continue
        seen.add(cause)
        out.append(cause)
    return out


def _load_yaml_or_json(path):
    _, ext = os.path.splitext(path)
    with open(path, "r", encoding="utf-8") as f:
        if ext.lower() in (".yaml", ".yml"):
            import yaml
            payload = yaml.safe_load(f)
        else:
            payload = json.load(f)
    return payload if isinstance(payload, dict) else {}


def _merge_dict(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_keep_dims(keep_dims, llm_dim):
    if keep_dims is None:
        return None
    if isinstance(keep_dims, str):
        key = keep_dims.strip().lower()
        if key in ("", "all"):
            return None
        if key in KEEP_DIMS_PRESETS:
            return [idx for idx in KEEP_DIMS_PRESETS[key] if 0 <= idx < llm_dim]
        if "," in keep_dims:
            out = []
            for token in keep_dims.split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    idx = int(token)
                except Exception:
                    continue
                if 0 <= idx < llm_dim:
                    out.append(idx)
            return sorted(set(out))
        try:
            idx = int(keep_dims)
            if 0 <= idx < llm_dim:
                return [idx]
        except Exception:
            return None
        return None
    if isinstance(keep_dims, (list, tuple)):
        out = []
        for item in keep_dims:
            try:
                idx = int(item)
            except Exception:
                continue
            if 0 <= idx < llm_dim:
                out.append(idx)
        return sorted(set(out))
    return None


def load_llm_policy(config_path, model_key, llm_dim):
    if not config_path:
        return None
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"LLM policy config not found: {config_path}")

    root_cfg = _load_yaml_or_json(config_path)
    policy = dict(DEFAULT_POLICY)
    policy = _merge_dict(policy, root_cfg.get("default", {}))

    model_key_norm = _normalize_model_key(model_key)
    model_overrides = {}
    models_inline = root_cfg.get("models", {})
    if isinstance(models_inline, dict):
        # match both raw and normalized keys
        for key, val in models_inline.items():
            if _normalize_model_key(key) == model_key_norm and isinstance(val, dict):
                model_overrides = val
                break

    config_dir = os.path.dirname(os.path.abspath(config_path))
    model_file_candidates = [
        os.path.join(config_dir, "models", f"{model_key_norm}.yaml"),
        os.path.join(config_dir, "models", f"{model_key_norm}.yml"),
        os.path.join(config_dir, "models", f"{model_key_norm}.json"),
    ]
    for candidate in model_file_candidates:
        if not os.path.exists(candidate):
            continue
        file_payload = _load_yaml_or_json(candidate)
        if isinstance(file_payload, dict):
            model_overrides = _merge_dict(model_overrides, file_payload)
        break

    policy = _merge_dict(policy, model_overrides)
    policy["enabled"] = bool(policy.get("enabled", True))
    policy["min_q_score"] = _clip01(_safe_float(policy.get("min_q_score", 0.0)))
    policy["min_rule_match"] = bool(policy.get("min_rule_match", False))
    policy["min_mapped_event_ratio"] = _clip01(_safe_float(policy.get("min_mapped_event_ratio", 0.0)))
    policy["drop_unknown_root"] = bool(policy.get("drop_unknown_root", False))
    policy["allowed_root_causes"] = _parse_root_cause_list(policy.get("allowed_root_causes", []))
    policy["llm_scale_alpha"] = _clip01(_safe_float(policy.get("llm_scale_alpha", 1.0), 1.0))
    gate_mode = str(policy.get("gate_mode", "hard")).strip().lower()
    policy["gate_mode"] = gate_mode if gate_mode in ("hard", "soft") else "hard"
    policy["soft_min_weight"] = _clip01(_safe_float(policy.get("soft_min_weight", 0.0), 0.0))
    policy["dense_meta_pack"] = _to_bool(policy.get("dense_meta_pack", False), False)
    policy["dense_meta_scale"] = _clip01(_safe_float(policy.get("dense_meta_scale", 1.0), 1.0))
    policy["dense_meta_dims_resolved"] = _resolve_keep_dims(policy.get("dense_meta_dims", "60,61,62,63,64,65,66,67,68,69"), llm_dim)
    fallback = str(policy.get("fallback", "nollm")).strip().lower()
    policy["fallback"] = fallback if fallback in ("nollm", "zero") else "nollm"
    policy["keep_dims_resolved"] = _resolve_keep_dims(policy.get("keep_dims", "all"), llm_dim)
    policy["model_key"] = model_key_norm
    return policy


def _inject_dense_meta(arr, llm_cols, dense_dims, dense_scale, values):
    if not dense_dims:
        return arr
    if dense_scale <= 0.0:
        return arr
    seq = [
        values.get("q_score"),
        values.get("mapped_ratio"),
        values.get("rule_match"),
        values.get("confidence"),
        values.get("risk_hint"),
        values.get("hardness"),
        values.get("event_count"),
        values.get("mapped_event_count"),
        values.get("root_known"),
        values.get("rule_top_score"),
    ]
    usable = [s for s in seq if s is not None]
    if not usable:
        return arr
    for i, dim in enumerate(dense_dims):
        if dim < 0 or dim >= len(llm_cols):
            continue
        src = usable[i % len(usable)]
        arr[:, dim] = (src.to_numpy(dtype=float, copy=False) * dense_scale)
    return arr


def apply_llm_policy_gate(llm_block, llm_cols, policy, fallback_mode):
    numeric_block = llm_block[llm_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    arr = numeric_block.to_numpy(dtype=float, copy=True)
    total = len(numeric_block)
    if total == 0:
        return numeric_block, {
            "total": 0,
            "kept": 0,
            "dropped": 0,
            "dropped_q": 0,
            "dropped_rule": 0,
            "dropped_map": 0,
            "dropped_root_unknown": 0,
            "dropped_root_cause": 0,
            "disabled": not bool(policy.get("enabled", True)),
            "alpha": float(policy.get("llm_scale_alpha", 1.0)),
        }

    min_q = float(policy.get("min_q_score", 0.0))
    min_map = float(policy.get("min_mapped_event_ratio", 0.0))
    require_rule_match = bool(policy.get("min_rule_match", False))
    drop_unknown_root = bool(policy.get("drop_unknown_root", False))
    allowed_root_causes = set(policy.get("allowed_root_causes") or [])
    alpha = float(policy.get("llm_scale_alpha", 1.0))
    enabled = bool(policy.get("enabled", True))
    gate_mode = str(policy.get("gate_mode", "hard")).strip().lower()
    soft_min_weight = float(policy.get("soft_min_weight", 0.0))
    dense_meta_pack = bool(policy.get("dense_meta_pack", False))
    dense_meta_dims = policy.get("dense_meta_dims_resolved")
    dense_meta_scale = float(policy.get("dense_meta_scale", 1.0))

    confidence_series = pd.to_numeric(llm_block.get("confidence", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    risk_hint_series = pd.to_numeric(llm_block.get("risk_hint", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    hardness_series = pd.to_numeric(llm_block.get("hardness", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    noise_series = pd.to_numeric(llm_block.get("label_noise_risk", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)

    if "llm_q_score" in llm_block.columns:
        q_series = pd.to_numeric(llm_block["llm_q_score"], errors="coerce").fillna(0.0)
    else:
        q_series = confidence_series.combine(risk_hint_series, min) * (1.0 - noise_series)
    q_series = q_series.clip(lower=0.0, upper=1.0)

    if "llm_rule_match" in llm_block.columns:
        raw_rule = llm_block["llm_rule_match"]
        if raw_rule.dtype == bool:
            rule_series = raw_rule
        else:
            rule_series = raw_rule.astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y"])
    else:
        rule_series = pd.Series(False, index=llm_block.index)

    if "llm_mapped_event_ratio" in llm_block.columns:
        mapped_series = pd.to_numeric(llm_block["llm_mapped_event_ratio"], errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    elif "llm_mapped_event_count" in llm_block.columns and "llm_event_count" in llm_block.columns:
        mapped_count = pd.to_numeric(llm_block["llm_mapped_event_count"], errors="coerce").fillna(0.0)
        event_count = pd.to_numeric(llm_block["llm_event_count"], errors="coerce").fillna(0.0)
        denom = event_count.where(event_count > 0, 1.0)
        mapped_series = (mapped_count / denom).clip(lower=0.0, upper=1.0)
    else:
        mapped_series = pd.Series(0.0, index=llm_block.index)
    mapped_series = mapped_series.clip(lower=0.0, upper=1.0)

    keep_mask = pd.Series(True, index=llm_block.index)
    dropped_q_mask = pd.Series(False, index=llm_block.index)
    dropped_rule_mask = pd.Series(False, index=llm_block.index)
    dropped_map_mask = pd.Series(False, index=llm_block.index)
    dropped_root_unknown_mask = pd.Series(False, index=llm_block.index)
    dropped_root_cause_mask = pd.Series(False, index=llm_block.index)

    if "root_cause_pred" in llm_block.columns:
        root_series = llm_block["root_cause_pred"].map(_normalize_root_cause)
    else:
        root_series = llm_block.get("root_cause", pd.Series("unknown", index=llm_block.index)).map(_normalize_root_cause)

    if not enabled:
        keep_mask[:] = False
    else:
        if drop_unknown_root:
            dropped_root_unknown_mask = root_series == "unknown"
            keep_mask &= ~dropped_root_unknown_mask
        if allowed_root_causes:
            dropped_root_cause_mask = ~root_series.isin(allowed_root_causes)
            keep_mask &= ~dropped_root_cause_mask

        if min_q > 0.0:
            dropped_q_mask = q_series < min_q
            keep_mask &= ~dropped_q_mask
        if require_rule_match:
            dropped_rule_mask = ~rule_series
            keep_mask &= ~dropped_rule_mask
        if min_map > 0.0:
            dropped_map_mask = mapped_series < min_map
            keep_mask &= ~dropped_map_mask

    keep_idx = keep_mask.to_numpy(dtype=bool)
    soft_weights = None
    if enabled and gate_mode == "soft":
        soft_weights = pd.Series(1.0, index=llm_block.index)

        if min_q > 0.0:
            denom_q = max(1.0 - min_q, 1e-6)
            q_w = ((q_series - min_q) / denom_q).clip(lower=0.0, upper=1.0)
        else:
            q_w = q_series
        soft_weights *= q_w

        if min_map > 0.0:
            denom_map = max(1.0 - min_map, 1e-6)
            map_w = ((mapped_series - min_map) / denom_map).clip(lower=0.0, upper=1.0)
            soft_weights *= map_w

        if require_rule_match:
            soft_weights *= rule_series.astype(float)

        if drop_unknown_root:
            soft_weights *= (~dropped_root_unknown_mask).astype(float)
        if allowed_root_causes:
            soft_weights *= (~dropped_root_cause_mask).astype(float)

        soft_weights = (soft_weights * alpha).clip(lower=0.0, upper=1.0)
        if soft_min_weight > 0.0:
            soft_weights = soft_weights.where(soft_weights <= 0.0, soft_weights.clip(lower=soft_min_weight))

        arr *= soft_weights.to_numpy(dtype=float).reshape(-1, 1)
        keep_idx = (soft_weights > 0.0).to_numpy(dtype=bool)
    elif alpha < 1.0 and keep_idx.any():
        arr[keep_idx, :] *= alpha

    keep_dims = policy.get("keep_dims_resolved")
    if keep_dims is not None:
        keep_dim_mask = [False] * len(llm_cols)
        for idx in keep_dims:
            if 0 <= idx < len(llm_cols):
                keep_dim_mask[idx] = True
        drop_cols = [idx for idx, keep in enumerate(keep_dim_mask) if not keep]
        if drop_cols:
            arr[:, drop_cols] = 0.0

    rule_top_score = pd.to_numeric(llm_block.get("llm_rule_top_score", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
    event_count_raw = pd.to_numeric(llm_block.get("llm_event_count", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    mapped_count_raw = pd.to_numeric(llm_block.get("llm_mapped_event_count", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    event_count_norm = (event_count_raw / 3.0).clip(lower=0.0, upper=1.0)
    mapped_count_norm = (mapped_count_raw / 3.0).clip(lower=0.0, upper=1.0)
    root_known = (root_series != "unknown").astype(float)
    if dense_meta_pack:
        arr = _inject_dense_meta(
            arr,
            llm_cols,
            dense_meta_dims,
            dense_meta_scale,
            {
                "q_score": q_series,
                "mapped_ratio": mapped_series,
                "rule_match": rule_series.astype(float),
                "confidence": confidence_series,
                "risk_hint": risk_hint_series,
                "hardness": hardness_series,
                "event_count": event_count_norm,
                "mapped_event_count": mapped_count_norm,
                "root_known": root_known,
                "rule_top_score": rule_top_score,
            },
        )

    if (~keep_idx).any() and fallback_mode in ("nollm", "zero"):
        arr[~keep_idx, :] = 0.0

    out = pd.DataFrame(arr, index=llm_block.index, columns=llm_cols)
    stats = {
        "total": int(total),
        "kept": int(keep_idx.sum()),
        "dropped": int((~keep_idx).sum()),
        "dropped_q": int(dropped_q_mask.sum()) if enabled else 0,
        "dropped_rule": int(dropped_rule_mask.sum()) if enabled else 0,
        "dropped_map": int(dropped_map_mask.sum()) if enabled else 0,
        "dropped_root_unknown": int(dropped_root_unknown_mask.sum()) if enabled else 0,
        "dropped_root_cause": int(dropped_root_cause_mask.sum()) if enabled else 0,
        "disabled": not enabled,
        "alpha": alpha,
        "soft_mode": gate_mode == "soft",
        "mean_weight": float(soft_weights.mean()) if soft_weights is not None else 1.0,
        "dense_meta_pack": dense_meta_pack,
    }
    return out, stats


def load_llm_cache(path, llm_dim):
    if path is None:
        raise ValueError("--llm_cache is required when --use_llm_features is enabled.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"LLM cache not found: {path}")
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    elif path.endswith(".jsonl"):
        df = pd.read_json(path, lines=True)
    else:
        raise ValueError("Unsupported llm cache format. Use .parquet or .jsonl")

    if "z_llm" in df.columns and not any(col.startswith("z_llm_") for col in df.columns):
        z_cols = [f"z_llm_{i}" for i in range(llm_dim)]
        z_llm = pd.DataFrame(df["z_llm"].tolist(), columns=z_cols)
        df = pd.concat([df.drop(columns=["z_llm"]), z_llm], axis=1)

    for i in range(llm_dim):
        col = f"z_llm_{i}"
        if col not in df.columns:
            df[col] = 0.0

    df["disk_id"] = df["disk_id"].astype(str)
    df["window_end_time"] = pd.to_datetime(df["window_end_time"]).dt.strftime("%Y-%m-%d")
    keep_cols = ["disk_id", "window_end_time"] + [f"z_llm_{i}" for i in range(llm_dim)]
    for extra_col in [
        "hardness",
        "near_positive",
        "label_noise_risk",
        "risk_hint",
        "confidence",
        "root_cause",
        "root_cause_pred",
        "parse_source",
        "llm_q_score",
        "llm_rule_match",
        "llm_rule_top_cause",
        "llm_rule_top_score",
        "llm_mapped_event_ratio",
        "llm_event_count",
        "llm_mapped_event_count",
    ]:
        if extra_col in df.columns:
            keep_cols.append(extra_col)
    return df[keep_cols]


class Simulate(AbstractPredict):
    def __init__(self, path, date_format, start_date, positive_window_size, #manufacturer, \
            disk_model, columns, features, label, forget_type, bl_delay=False, \
            dropna=False, negative_window_size=6, validation_window=6, \
            bl_regression=False, label_days=None, bl_transfer=False, bl_ssd=False, \
            use_llm_features=False, llm_cache=None, llm_dim=64, llm_policy=None, llm_fallback_mode="nollm"):
        super().__init__()
        self.memory = Memory(path, start_date, positive_window_size,  #manufacturer,\
            disk_model, columns, features, label, forget_type, dropna, bl_delay, \
            negative_window_size, bl_regression, label_days, bl_transfer, date_format, bl_ssd)
        self.use_llm_features = use_llm_features
        self.llm_cache = llm_cache
        self.llm_dim = llm_dim
        self.llm_policy = llm_policy
        self.llm_fallback_mode = str(llm_fallback_mode or "nollm").strip().lower()
        if self.llm_fallback_mode not in ("nollm", "zero"):
            self.llm_fallback_mode = "nollm"
        self.llm_policy_stats = {
            "total": 0,
            "kept": 0,
            "dropped": 0,
            "dropped_q": 0,
            "dropped_rule": 0,
            "dropped_map": 0,
            "dropped_root_unknown": 0,
            "dropped_root_cause": 0,
            "calls": 0,
        }
        if not bl_transfer:
            self.memory.buffering()
            self.data = self.memory.ret_df.drop(['model', 'date'], axis=1)
        else:
            self.data = self.memory.ret_df.drop(['model', 'date'], axis=1)
        self.data = self.data.reset_index(drop=True)
        self._append_llm_features()
        self.class_name = label[0]
        self.num_classes = 2
        self.bl_delay = bl_delay
        self.validation_window = validation_window

    def load(self):
        # Load Data from Memory class and backtracking delayed instances
        self.memory.data_management(self.keep_delay, self.bl_delay)

        self.data = self.memory.ret_df.drop(['model', 'date'], axis=1)
        self.data = self.data.reset_index(drop=True)
        self._append_llm_features()

    def _append_llm_features(self):
        if not self.use_llm_features:
            return

        llm_cols = [f"z_llm_{i}" for i in range(self.llm_dim)]
        if all(col in self.data.columns for col in llm_cols):
            return

        keys = pd.DataFrame({
            "disk_id": self.memory.ret_df["serial_number"].astype(str).values,
            "window_end_time": self.memory.ret_df["date"].dt.strftime("%Y-%m-%d").values
        })

        if self.llm_cache is None:
            llm_block = pd.DataFrame(index=keys.index, columns=llm_cols)
        else:
            llm_block = keys.merge(self.llm_cache, on=["disk_id", "window_end_time"], how="left")
            llm_block = llm_block.drop(columns=["disk_id", "window_end_time"])

        for col in llm_cols:
            if col not in llm_block.columns:
                llm_block[col] = pd.NA

        miss_mask = llm_block[llm_cols[0]].isna() if len(llm_cols) > 0 else pd.Series(False, index=llm_block.index)
        if miss_mask.any():
            self._log_llm_cache_miss(keys[miss_mask])
            llm_block.loc[miss_mask, llm_cols] = 0.0

        if self.llm_policy is not None:
            gated_block, stats = apply_llm_policy_gate(
                llm_block,
                llm_cols,
                self.llm_policy,
                self.llm_fallback_mode,
            )
            self._log_llm_policy_stats(stats)
            llm_block = gated_block
        else:
            llm_block = llm_block[llm_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        self.data = pd.concat([self.data, llm_block], axis=1)

    def _log_llm_cache_miss(self, miss_keys):
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "llm_cache_miss.log")
        with open(log_path, "a", encoding="utf-8") as f:
            for _, row in miss_keys.iterrows():
                f.write(f"{row['disk_id']},{row['window_end_time']}\n")

    def _log_llm_policy_stats(self, stats):
        if self.llm_policy is None or not isinstance(stats, dict):
            return
        for key in (
            "total",
            "kept",
            "dropped",
            "dropped_q",
            "dropped_rule",
            "dropped_map",
            "dropped_root_unknown",
            "dropped_root_cause",
        ):
            self.llm_policy_stats[key] += int(stats.get(key, 0))
        self.llm_policy_stats["calls"] += 1

        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "llm_policy_gate.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                (
                    "model_key={model} call={call} total={total} kept={kept} dropped={dropped} "
                    "drop_q={drop_q} drop_rule={drop_rule} drop_map={drop_map} "
                    "drop_root_unknown={drop_root_unknown} drop_root_cause={drop_root_cause} "
                    "enabled={enabled} alpha={alpha}\n"
                ).format(
                    model=self.llm_policy.get("model_key", "unknown"),
                    call=self.llm_policy_stats["calls"],
                    total=self.llm_policy_stats["total"],
                    kept=self.llm_policy_stats["kept"],
                    dropped=self.llm_policy_stats["dropped"],
                    drop_q=self.llm_policy_stats["dropped_q"],
                    drop_rule=self.llm_policy_stats["dropped_rule"],
                    drop_map=self.llm_policy_stats["dropped_map"],
                    drop_root_unknown=self.llm_policy_stats["dropped_root_unknown"],
                    drop_root_cause=self.llm_policy_stats["dropped_root_cause"],
                    enabled=not bool(stats.get("disabled", False)),
                    alpha=float(stats.get("alpha", 1.0)),
                )
            )

    def delay_evaluate(self):
        pop_sn = []
        i = 0
        for sn, instances in self.keep_delay.items():
            instances.dequeue()
            if len(instances.queue) == 0:
                pop_sn.append(sn)
            i += 1
        for sn in pop_sn:
            self.keep_delay.pop(sn)

    def run(self):
        self.inspect(self.data, self.class_name, self.num_classes,
                     self.memory.new_inst_start_index, self.validation_window)


def run_simulating(start_date, path, path_load, path_save, train_path,
                   test_path, file_format, iter_days, model, features, label,
                   columns, forget_type, positive_window_size, bl_delay,
                   bl_load, bl_save, negative_window_size, validation_window,
                   bl_regression, label_days, bl_transfer, bl_ssd, date_format,
                   use_llm_features, llm_cache_path, llm_dim,
                   llm_policy_config, llm_policy_model_key, llm_fallback_mode,
                   progress_every):
    if file_format == "arff":
        arff = Arff(bl_regression=bl_regression)
    llm_cache = None
    llm_policy = None
    if use_llm_features:
        llm_cache = load_llm_cache(llm_cache_path, llm_dim)
        policy_model_key = llm_policy_model_key
        if not policy_model_key and model:
            policy_model_key = model[0]
        llm_policy = load_llm_policy(llm_policy_config, policy_model_key, llm_dim) if llm_policy_config else None
        if llm_policy is not None:
            print("Loaded LLM policy:", llm_policy)
    print(
        (
            f"[run.py] start iter_days={iter_days} delay={bl_delay} load={bl_load} "
            f"transfer={bl_transfer} progress_every={max(1, int(progress_every))}"
        ),
        flush=True,
    )
    if bl_load:
        with open(path_load, 'rb') as f:
            sim = pickle.load(f)
        print(sim.memory.cur_date)
        date = sim.memory.cur_date
        #sim.load()
    else:
        print(start_date)
        sim = Simulate(path, date_format, start_date, positive_window_size, model, columns,
                       features, label, forget_type, bl_delay, True,
                       negative_window_size, validation_window, bl_regression,
                       label_days, bl_transfer, bl_ssd, use_llm_features=use_llm_features,
                       llm_cache=llm_cache, llm_dim=llm_dim,
                       llm_policy=llm_policy, llm_fallback_mode=llm_fallback_mode)
        if not bl_transfer:
            fname = (sim.memory.cur_date -
                     datetime.timedelta(days=1)).isoformat()[0:10]

            if file_format == "arff":
                if not bl_regression:
                    sim.data['failure'] = sim.data['failure'].map({
                        0: 'c0',
                        1: 'c1'
                    })
                arff.dump(fname, sim.data, train_path + fname + ".arff")
            elif file_format == "csv":
                sim.data.to_csv(train_path + fname + ".csv", index=False)
            if test_path is not None and sim.memory.new_inst_start_index > 0:
                if file_format == "arff":
                    arff.dump(fname,
                              sim.data[sim.memory.new_inst_start_index:],
                              test_path + fname + ".arff")
                elif file_format == "csv":
                    sim.data[sim.memory.new_inst_start_index:].to_csv(
                        test_path + fname + ".csv", index=False)
            sim.run()
        else:
            print(sim.memory.cur_date)
            fname = (sim.memory.cur_date -
                     datetime.timedelta(days=1)).isoformat()[0:10]
            if test_path is not None:
                if file_format == "arff":
                    if not bl_regression:
                        sim.data['failure'] = sim.data['failure'].map({
                            0: 'c0',
                            1: 'c1'
                        })
                    arff.dump(fname,
                              sim.data[sim.memory.new_inst_start_index:],
                              test_path + fname + ".arff")
                elif file_format == "csv":
                    sim.data[sim.memory.new_inst_start_index:].to_csv(
                        test_path + fname + ".csv", index=False)
            transfer_start_ts = time.time()
            for i in range(1, positive_window_size):
                sim.load()
                print(sim.memory.cur_date)
                _print_progress(
                    "transfer_warmup",
                    i,
                    max(1, positive_window_size - 1),
                    transfer_start_ts,
                    sim.memory.cur_date,
                    progress_every,
                )
                fname = (sim.memory.cur_date -
                         datetime.timedelta(days=1)).isoformat()[0:10]
                if test_path is not None:
                    if file_format == "arff":
                        if not bl_regression:
                            sim.data['failure'] = sim.data['failure'].map({
                                0:
                                'c0',
                                1:
                                'c1'
                            })
                        arff.dump(fname,
                                  sim.data[sim.memory.new_inst_start_index:],
                                  test_path + fname + ".arff")
                    elif file_format == "csv":
                        sim.data[sim.memory.new_inst_start_index:].to_csv(
                            test_path + fname + ".csv", index=False)
            if file_format == "arff":
                arff.dump(fname, sim.data, train_path + fname + ".arff")
            elif file_format == "csv":
                sim.data.to_csv(train_path + fname + ".csv", index=False)
            sim.run()

    if bl_load is False and bl_delay:
        delay_start_ts = time.time()
        for i in range(validation_window):
            sim.load()
            print(sim.memory.cur_date)
            _print_progress(
                "delay_warmup",
                i + 1,
                validation_window,
                delay_start_ts,
                sim.memory.cur_date,
                progress_every,
            )
            fname = (sim.memory.cur_date -
                     datetime.timedelta(days=1)).isoformat()[0:10]

            if file_format == "arff":
                if not bl_regression:
                    sim.data['failure'] = sim.data['failure'].map({
                        0: 'c0',
                        1: 'c1'
                    })
                arff.dump(fname, sim.data, train_path + fname + ".arff")
            elif file_format == "csv":
                sim.data.to_csv(train_path + fname + ".csv", index=False)
            if test_path is not None and sim.memory.new_inst_start_index > 0:
                if file_format == "arff":
                    arff.dump(fname,
                              sim.data[sim.memory.new_inst_start_index:],
                              test_path + fname + ".arff")
                elif file_format == "csv":
                    sim.data[sim.memory.new_inst_start_index:].to_csv(
                        test_path + fname + ".csv", index=False)
            sim.run()

    iter_start_ts = time.time()
    for ite in range(0, iter_days):
        print(sim.memory.cur_date)
        date = sim.memory.cur_date
        _print_progress(
            "main_iter",
            ite + 1,
            iter_days,
            iter_start_ts,
            date,
            progress_every,
        )
        if bl_delay:
            sim.load()
            sim.delay_evaluate()
            fname = (sim.memory.cur_date -
                     datetime.timedelta(days=1)).isoformat()[0:10]

            if file_format == "arff":
                if not bl_regression:
                    sim.data['failure'] = sim.data['failure'].map({
                        0: 'c0',
                        1: 'c1'
                    })
                arff.dump(fname, sim.data, train_path + fname + ".arff")
            elif file_format == "csv":
                sim.data.to_csv(train_path + fname + ".csv", index=False)
            if test_path is not None and sim.memory.new_inst_start_index > 0:
                if file_format == "arff":
                    arff.dump(fname,
                              sim.data[sim.memory.new_inst_start_index:],
                              test_path + fname + ".arff")
                elif file_format == "csv":
                    sim.data[sim.memory.new_inst_start_index:].to_csv(
                        test_path + fname + ".csv", index=False)
            sim.run()
        else:
            sim.load()
            fname = (sim.memory.cur_date -
                     datetime.timedelta(days=1)).isoformat()[0:10]

            if file_format == "arff":
                if not bl_regression:
                    sim.data['failure'] = sim.data['failure'].map({
                        0: 'c0',
                        1: 'c1'
                    })
                arff.dump(fname, sim.data, train_path + fname + ".arff")
            elif file_format == "csv":
                sim.data.to_csv(train_path + fname + ".csv", index=False)
            if test_path is not None and sim.memory.new_inst_start_index > 0:
                if file_format == "arff":
                    arff.dump(fname,
                              sim.data[sim.memory.new_inst_start_index:],
                              test_path + fname + ".arff")
                elif file_format == "csv":
                    sim.data[sim.memory.new_inst_start_index:].to_csv(
                        test_path + fname + ".csv", index=False)
            sim.run()
    print("[run.py] finished data generation loop", flush=True)
    if bl_save:
        with open(path_save, 'wb') as f:
            pickle.dump(sim, f)


def usage(arg):
    print(arg, ":h [--help]")
    print("-s <start_date> [--start_date <start_date>]")
    print("-p <path_dataset> [--path <path_dataset>]")
    print("-l <path_load> [--path_load <path_load>]")
    print("-v <path_save> [--path_save <path_save>]")
    print("-c <path_features> [--path_features <path_features>]")
    print("-r <train_data_path> [--train_path <train_data_path>]")
    print("-e <test_data_path> [--test_path <test_data_path>]")
    print("-f <file_format> [--format <file_format>]")
    print("-o <option> [--option <option>]")
    print("-i <iter_days> [--iter_days <iter_days>]")
    print("-d <disk_model> [--disk_model <disk_model>]")
    print("-t <forget_type> [--forget_type <forget_type>]")
    print(
        "-w <positive_window_size> [--positive_window_size <positive_window_size>]"
    )
    print(
        "-L <negative_window_size> [--negative_window_size <negative_window_size>]"
    )
    print("-V <validation_window> [--validation_window <validation_window>]")
    print("-a <label_days> [--label_days <label_days>]")
    print("-F <date_format> [--date_format <date_format>]")
    print("-U <use_llm_features> [--use_llm_features <0|1>]")
    print("-C <llm_cache> [--llm_cache <path>]")
    print("-M <llm_dim> [--llm_dim <int>]")
    print("--llm_policy_config <path>")
    print("--llm_policy_model_key <model_key>")
    print("--llm_fallback_mode <nollm|zero>")
    print("--progress_every <int>")
    print()
    print("Details:")
    print("path_load = load the Simulate class for continuing to process data")
    print(
        "path_save = save the Simulate class for continuing to process data next"
    )
    print(
        "file_format = file format of saving the processed data, arff by default"
    )
    print(
        "option = 1: enable regression (classification by default); 2: enable loading the Simulate class; 3: enable saving the Simulate class; 4: enable labeling; 5: enable transfer learning"
    )
    print(
        "forget_type = \"no\" (keep all historical data) or \"sliding\" (sliding window), \"sliding\" by default"
    )
    print(
        "positive_window_size = size of the sliding time window, 30 days by default"
    )
    print(
        "negative_window_size = size of the window for negative samples in 1-phase downsampling, 7 days by default"
    )
    print(
        "validation_window = size of window for evaluation, 30 days by default"
    )
    print("label_days = number of extra labeled days")


def get_parms():
    str_start_date = "2015-01-01"
    date_format = "%Y-%m-%d"
    path = "~/trace/smart/all/"
    train_path = "./train/"
    test_path = None
    path_load = None
    path_save = None
    bl_delay = False
    bl_load = False
    bl_save = False
    bl_regression = False
    bl_transfer = False
    bl_ssd = False
    use_llm_features = False
    llm_cache_path = None
    llm_dim = 64
    llm_policy_config = None
    llm_policy_model_key = None
    llm_fallback_mode = "nollm"
    progress_every = 1
    option = {
        1: "bl_regression",
        2: "bl_load",
        3: "bl_save",
        4: "bl_delay",
        5: "bl_transfer",
        6: "bl_ssd"
    }

    file_format = "arff"
    iter_days = 5
    #manufacturer = None  #'ST'
    #model = 'ST4000DM000'
    model = []
    features = [
        'smart_1_normalized', 'smart_5_raw', 'smart_5_normalized',
        'smart_9_raw', 'smart_187_raw', 'smart_197_raw', 'smart_197_normalized'
    ]
    corr_attrs = []
    path_features = None
    label = ['failure']
    forget_type = "sliding"
    label_days = None
    positive_window_size = 30
    negative_window_size = 7
    validation_window = 30

    try:
        (opt, args) = getopt.getopt(
            sys.argv[1:], "hs:p:l:v:c:r:e:f:o:i:d:t:w:L:V:a:F:U:C:M:", [
                "help", "start_date", "path", "path_load", "path_save",
                "path_features", "train_path", "test_path", "file_format",
                "option", "iter_days", "disk_model", "forget_type",
                "positive_window_size", "negative_window_size",
                "validation_window", "label_days", "date_format",
                "use_llm_features", "llm_cache", "llm_dim",
                "llm_policy_config=", "llm_policy_model_key=", "llm_fallback_mode=",
                "progress_every="
            ])
    except:
        usage(sys.argv[0])
        print("getopts exception")
        sys.exit(1)

    for o, a in opt:
        if o in ("-h", "--help"):
            usage(sys.argv[0])
            sys.exit(0)
        elif o in ("-s", "--start_date"):
            str_start_date = a
        elif o in ("-p", "--path"):
            path = a
        elif o in ("-l", "--path_load"):
            path_load = a
        elif o in ("-v", "--path_save"):
            path_save = a
        elif o in ("-c", "--path_features"):
            path_features = a
        elif o in ("-f", "--file_format"):
            file_format = a
        elif o in ("-r", "--train_path"):
            train_path = a
        elif o in ("-e", "--test_path"):
            test_path = a
        elif o in ("-o", "--option"):
            ops = a.split(",")
            for op in ops:
                if int(op) == 1:
                    bl_regression = True
                elif int(op) == 2:
                    bl_load = True
                elif int(op) == 3:
                    bl_save = True
                elif int(op) == 4:
                    bl_delay = True
                elif int(op) == 5:
                    bl_transfer = True
                elif int(op) == 6:
                    bl_ssd = True
        elif o in ("-i", "--iter_days"):
            iter_days = int(a)
        elif o in ("-d", "--disk_model"):
            model = a.split(",")
        elif o in ("-t", "--forget_type"):
            forget_type = a
        elif o in ("-w", "--positive_window_size"):
            positive_window_size = int(a)
        elif o in ("-L", "--negative_window_size"):
            negative_window_size = int(a)
        elif o in ("-V", "--validation_window"):
            validation_window = int(a)
        elif o in ("-a", "--label_days"):
            label_days = int(a)
        elif o in ("-F", "--date_format"):
            date_format = a
        elif o in ("-U", "--use_llm_features"):
            use_llm_features = bool(int(a))
        elif o in ("-C", "--llm_cache"):
            llm_cache_path = a
        elif o in ("-M", "--llm_dim"):
            llm_dim = int(a)
        elif o == "--llm_policy_config":
            llm_policy_config = a
        elif o == "--llm_policy_model_key":
            llm_policy_model_key = a
        elif o == "--llm_fallback_mode":
            llm_fallback_mode = str(a).strip().lower()
            if llm_fallback_mode not in ("nollm", "zero"):
                llm_fallback_mode = "nollm"
        elif o == "--progress_every":
            progress_every = max(1, int(a))

    if str_start_date.find("-") != -1:
        start_date = datetime.datetime.strptime(str_start_date, "%Y-%m-%d")
    else:
        start_date = datetime.datetime.strptime(str_start_date, "%Y%m%d")
    if path_features is not None:
        features = []
        with open(path_features, "r") as f:
            for line in f.readlines():
                features.append(line.strip())
        print(features)

    if bl_ssd:
        columns = ['ds', 'model', 'disk_id'] + features
    else:
        columns = ['date', 'model', 'serial_number'] + label + features
    return (start_date, path, path_load, path_save, train_path, test_path,
            file_format, bl_delay, bl_load, bl_save, iter_days, model,
            features, label, columns, forget_type, positive_window_size,
            negative_window_size, validation_window, bl_regression, label_days,
            bl_transfer, bl_ssd, date_format, use_llm_features,
            llm_cache_path, llm_dim, llm_policy_config, llm_policy_model_key,
            llm_fallback_mode, progress_every)


if __name__ == "__main__":
    (start_date, path, path_load, path_save, train_path, test_path,
     file_format, bl_delay, bl_load, bl_save, iter_days, disk_model, features,
     label, columns, forget_type, positive_window_size, negative_window_size,
     validation_window, bl_regression, label_days, bl_transfer, bl_ssd,
     date_format, use_llm_features, llm_cache_path, llm_dim,
     llm_policy_config, llm_policy_model_key, llm_fallback_mode,
     progress_every) = get_parms()

    run_simulating(start_date, path, path_load, path_save, train_path,
                   test_path, file_format, iter_days, disk_model, features,
                   label, columns, forget_type, positive_window_size, bl_delay,
                   bl_load, bl_save, negative_window_size, validation_window,
                   bl_regression, label_days, bl_transfer, bl_ssd, date_format,
                   use_llm_features, llm_cache_path, llm_dim,
                   llm_policy_config, llm_policy_model_key, llm_fallback_mode,
                   progress_every)
