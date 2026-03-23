#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
REPO_PARENT = ROOT.parent
UI_DIR = ROOT / "ui"
STATIC_DIR = UI_DIR / "static"
REGISTRY_PATH = UI_DIR / "workflows.json"
LOG_DIR = ROOT / "logs" / "ui_runs"

MODEL_PRESETS = [
    {
        "id": "qwen3instruct2507",
        "name": "Qwen3-4B-Instruct-2507",
        "family": "Qwen3",
        "kind": "local",
        "role": "默认本地 base model",
        "recommended": True,
        "description": "当前仓库默认的本地基线模型。MC1 修正输入上 Phase2 最强，Phase3 最优结果与另外两个模型一致。",
        "model_path": "../models/Qwen/Qwen3-4B-Instruct-2507",
    },
    {
        "id": "qwen35plusapi",
        "name": "Qwen3.5-Plus",
        "family": "Qwen3.5",
        "kind": "api",
        "role": "API 对照模型",
        "recommended": False,
        "description": "API 侧稳定对照方案。HDD 和 MC1 都有完整结果，工程上最省本地 GPU。",
        "model_path": "qwen3.5-plus",
        "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
    },
    {
        "id": "qwen35tp2eager",
        "name": "Qwen3.5-4B",
        "family": "Qwen3.5",
        "kind": "local",
        "role": "双卡实验模型",
        "recommended": False,
        "description": "在 MC1 长提示词场景下需要 TP=2 + eager 才能稳定跑通，本地工程成本最高。",
        "model_path": "../models/Qwen/Qwen3.5-4B",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def shell_preview(command: List[str]) -> str:
    return shlex.join(command)


def safe_rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def human_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit = units[0]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.2f} {unit}"


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_hdd_results() -> Dict[str, Any]:
    path = ROOT / "docs" / "tables" / "qwen3_instruct_vs_qwen35_4b_vs_qwen35_plus_comparison_20260315.csv"
    rows = read_csv_rows(path)
    specs = [
        {
            "id": "qwen3_instruct",
            "label": "Qwen3-4B-Instruct-2507",
            "action_field": "action_qwen3_instruct",
            "delta_field": "delta_recall_qwen3_instruct",
        },
        {
            "id": "qwen35_4b",
            "label": "Qwen3.5-4B",
            "action_field": "action_qwen35_4b",
            "delta_field": "delta_recall_qwen35_4b",
        },
        {
            "id": "qwen35_plus",
            "label": "Qwen3.5-Plus",
            "action_field": "action_qwen35_plus",
            "delta_field": "delta_recall_qwen35_plus",
        },
    ]
    model_summaries = []
    for spec in specs:
        enabled = [row for row in rows if row.get(spec["action_field"]) not in {"", "nollm"}]
        deltas = [parse_float(row.get(spec["delta_field"])) for row in enabled]
        best_row = max(rows, key=lambda row: parse_float(row.get(spec["delta_field"])), default=None)
        worst_row = min(rows, key=lambda row: parse_float(row.get(spec["delta_field"])), default=None)
        model_summaries.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "enabled_count": len(enabled),
                "avg_enabled_delta_recall": round(sum(deltas) / len(deltas), 4) if deltas else None,
                "best_model_key": best_row.get("model_key") if best_row else None,
                "best_delta_recall": parse_float(best_row.get(spec["delta_field"])) if best_row else None,
                "worst_model_key": worst_row.get("model_key") if worst_row else None,
                "worst_delta_recall": parse_float(worst_row.get(spec["delta_field"])) if worst_row else None,
            }
        )
    return {
        "path": safe_rel_path(path, ROOT),
        "rows": rows,
        "models": model_summaries,
    }


def summarize_mc1_phase2() -> Dict[str, Any]:
    path = ROOT / "docs" / "tables" / "mc1_phase2_quality_comparison_stratified_v2_20260319.csv"
    rows = read_csv_rows(path)
    return {"path": safe_rel_path(path, ROOT), "rows": rows}


def summarize_mc1_phase3() -> Dict[str, Any]:
    path = ROOT / "docs" / "tables" / "mc1_phase3_comparison_stratified_v2_20260323.csv"
    rows = read_csv_rows(path)
    return {"path": safe_rel_path(path, ROOT), "rows": rows}


def results_summary() -> Dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "model_presets": MODEL_PRESETS,
        "hdd": summarize_hdd_results(),
        "mc1_phase2": summarize_mc1_phase2(),
        "mc1_phase3": summarize_mc1_phase3(),
    }


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    if path.is_file():
        return path.stat().st_size
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def storage_summary() -> Dict[str, Any]:
    total, used, free = shutil.disk_usage(ROOT)
    targets = [
        ("repo_root", ROOT),
        ("save_model", ROOT / "save_model"),
        ("pyloader", ROOT / "pyloader"),
        ("logs", ROOT / "logs"),
        ("llm_framework_v1", ROOT / "llm" / "framework_v1"),
        ("llm_framework_v1_mc1", ROOT / "llm" / "framework_v1_mc1"),
        ("mc1_mlp", ROOT / "mc1_mlp"),
        ("hi7_example", ROOT / "hi7_example"),
        ("data", ROOT / "data"),
        ("models_qwen", REPO_PARENT / "models" / "Qwen"),
    ]
    directories = []
    for label, path in targets:
        if not path.exists():
            continue
        size = directory_size(path)
        directories.append(
            {
                "label": label,
                "path": str(path),
                "size_bytes": size,
                "size_human": human_bytes(size),
            }
        )
    directories.sort(key=lambda item: item["size_bytes"], reverse=True)

    top_files: List[Dict[str, Any]] = []
    scan_roots = [ROOT / "logs", ROOT / "pyloader", ROOT / "mc1_mlp", ROOT / "hi7_example", ROOT / "llm", REPO_PARENT / "models" / "Qwen"]
    for base in scan_roots:
        if not base.exists():
            continue
        for file_path in base.rglob("*"):
            try:
                if not file_path.is_file():
                    continue
                size = file_path.stat().st_size
            except OSError:
                continue
            if size < 200 * 1024 * 1024:
                continue
            top_files.append(
                {
                    "path": str(file_path),
                    "size_bytes": size,
                    "size_human": human_bytes(size),
                }
            )
    top_files.sort(key=lambda item: item["size_bytes"], reverse=True)
    top_files = top_files[:20]

    return {
        "generated_at": utc_now(),
        "disk": {
            "path": str(ROOT),
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "total_human": human_bytes(total),
            "used_human": human_bytes(used),
            "free_human": human_bytes(free),
        },
        "directories": directories,
        "top_files": top_files,
    }


def preflight_summary() -> Dict[str, Any]:
    checks = []

    def add_check(scope: str, label: str, ok: bool, detail: str) -> None:
        checks.append({"scope": scope, "label": label, "ok": ok, "detail": detail})

    simulate_jar = ROOT / "simulate" / "target" / "simulate-2019.01.0-SNAPSHOT.jar"
    moa_jar = ROOT / "moa" / "target" / "moa-2019.01.0-SNAPSHOT.jar"
    add_check("global", "Java simulate jar", simulate_jar.exists(), str(simulate_jar))
    add_check("global", "MOA jar", moa_jar.exists(), str(moa_jar))

    disk_total, disk_used, disk_free = shutil.disk_usage(ROOT)
    add_check("global", "可用磁盘空间 > 50GB", disk_free > 50 * 1024**3, human_bytes(disk_free))

    for preset in MODEL_PRESETS:
      if preset["kind"] == "local":
        model_path = (REPO_PARENT / preset["model_path"].replace("../", "", 1)) if preset["model_path"].startswith("../") else Path(preset["model_path"])
        add_check("models", f"{preset['name']} 本地模型目录", model_path.exists(), str(model_path))
      else:
        add_check("models", f"{preset['name']} API 配置", True, preset.get("api_base_url", ""))

    mc1_window = ROOT / "llm" / "framework_v1_mc1" / "window_text_mc1_pilot20k_stratified_v2.jsonl"
    mc1_ref = ROOT / "llm" / "framework_v1_mc1" / "reference_mc1_pilot20k_stratified_v2.json"
    mc1_baseline = ROOT / "mc1_mlp" / "example_mc1_nollm_20180103_20180313_compare_aligned_i10.csv"
    add_check("mc1", "MC1 stratified_v2 window_text", mc1_window.exists(), str(mc1_window))
    add_check("mc1", "MC1 stratified_v2 reference", mc1_ref.exists(), str(mc1_ref))
    add_check("mc1", "MC1 baseline CSV", mc1_baseline.exists(), str(mc1_baseline))

    hdd_window_dir = ROOT / "llm" / "framework_v1"
    add_check("hdd", "HDD framework_v1 目录", hdd_window_dir.exists(), str(hdd_window_dir))

    return {"generated_at": utc_now(), "checks": checks}


def add_artifact(items: List[Dict[str, Any]], label: str, path: Path) -> None:
    items.append(
        {
            "label": label,
            "path": safe_rel_path(path, ROOT),
            "exists": path.exists(),
        }
    )


def infer_job_artifacts(workflow_id: str, env: Dict[str, str], log_path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    add_artifact(items, "作业日志", log_path)

    if workflow_id in {"llm.mc1.phase2", "llm.mc1.full-stratified-v2"}:
        run_tag = env.get("RUN_TAG") or env.get("PHASE2_RUN_TAG")
        if run_tag:
            add_artifact(
                items,
                "MC1 cache",
                ROOT / "llm" / "framework_v1_mc1" / f"cache_mc1_zs_structured_v2_{run_tag}.jsonl",
            )
            add_artifact(
                items,
                "MC1 抽取质量",
                ROOT / "docs" / f"extract_quality_mc1_{run_tag}_v1.csv",
            )

    if workflow_id in {"llm.mc1.phase3-grid", "llm.mc1.full-stratified-v2"}:
        run_tag = env.get("RUN_TAG") or env.get("PHASE3_RUN_TAG")
        tag_suffix = env.get("TAG_SUFFIX") or env.get("PHASE3_TAG_SUFFIX")
        if run_tag and tag_suffix:
            add_artifact(
                items,
                "MC1 Phase3 CSV",
                ROOT / "docs" / f"prearff_grid_mc1_{run_tag}_{tag_suffix}_v1.csv",
            )
            add_artifact(
                items,
                "MC1 Phase3 Markdown",
                ROOT / "docs" / f"prearff_grid_mc1_{run_tag}_{tag_suffix}_v1.md",
            )
            add_artifact(
                items,
                "MC1 组合记录",
                ROOT / "logs" / "framework_v1_phase3_mc1" / f"phase3_mc1_combo_records_{run_tag}_{tag_suffix}.tsv",
            )

    if workflow_id in {"llm.pilot20k.phase2-all12", "llm.pilot20k.full-all12"}:
        run_tag = env.get("RUN_TAG")
        if run_tag:
            add_artifact(items, "HDD Phase2 日志目录", ROOT / "logs" / "framework_v1")
            add_artifact(items, "HDD cache 目录", ROOT / "llm" / "framework_v1")
            add_artifact(items, "HDD 质量结果目录", ROOT / "docs")

    if workflow_id in {"llm.pilot20k.phase3-all12", "llm.pilot20k.full-all12"}:
        run_tag = env.get("PHASE3_RUN_TAG")
        if run_tag:
            add_artifact(
                items,
                "HDD core 汇总 CSV",
                ROOT / "docs" / f"prearff_grid_2models_{run_tag}_v1.csv",
            )
            add_artifact(
                items,
                "HDD batch7 汇总 CSV",
                ROOT / "docs" / f"prearff_grid_batch7_zs_{run_tag}_v1.csv",
            )
            add_artifact(
                items,
                "HDD Phase3 记录目录",
                ROOT / "logs" / "framework_v1_phase3",
            )
    return items


def cleanup_experiment_artifacts() -> Dict[str, Any]:
    with JOBS_LOCK:
        running = [job.to_dict() for job in JOBS.values() if job.status == "running"]
    if running:
        raise RuntimeError("存在运行中的作业，无法清理实验中间产物。")

    targets: List[Path] = []
    targets.extend((ROOT / "save_model").glob("*.pickle"))
    targets.extend((ROOT / "pyloader").glob("phase3_train_*"))
    targets.extend((ROOT / "pyloader").glob("phase3_test_*"))
    targets.extend((ROOT / "pyloader").glob("phase3b7_train_*"))
    targets.extend((ROOT / "pyloader").glob("phase3b7_test_*"))
    targets.extend((ROOT / "llm" / "framework_v1" / "phase3_variants").glob("*.jsonl"))
    targets.extend((ROOT / "llm" / "framework_v1" / "phase3_variants_batch7").glob("*.jsonl"))
    targets.extend((ROOT / "llm" / "framework_v1_mc1" / "phase3_variants").glob("*.jsonl"))

    removed = []
    reclaimed = 0
    for path in targets:
        if not path.exists():
            continue
        size = directory_size(path)
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError:
            continue
        reclaimed += size
        removed.append(
            {
                "path": safe_rel_path(path, ROOT),
                "size_bytes": size,
                "size_human": human_bytes(size),
            }
        )
    return {
        "removed_count": len(removed),
        "reclaimed_bytes": reclaimed,
        "reclaimed_human": human_bytes(reclaimed),
        "removed": removed[:30],
    }


def load_registry(path: Path) -> Dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    workflows = data.get("workflows", [])
    seen = set()
    for wf in workflows:
        workflow_id = wf["id"]
        if workflow_id in seen:
            raise ValueError(f"duplicate workflow id: {workflow_id}")
        seen.add(workflow_id)
        if "display_name" not in wf or "command" not in wf:
            raise ValueError(f"workflow missing required fields: {workflow_id}")
        wf.setdefault("cwd", ".")
        wf.setdefault("category", "Uncategorized")
        wf.setdefault("description", "")
        wf.setdefault("notes", [])
        wf.setdefault("tags", [])
        wf.setdefault("env", [])
        wf["command_preview"] = shell_preview(wf["command"])
    return data


@dataclass
class Job:
    job_id: str
    workflow_id: str
    workflow_name: str
    command: List[str]
    cwd: Path
    env: Dict[str, str]
    log_path: Path
    started_at: str
    process: subprocess.Popen
    returncode: Optional[int] = None
    finished_at: Optional[str] = None
    log_handle: Optional[object] = field(default=None, repr=False)

    def refresh(self) -> None:
        if self.returncode is not None:
            return
        code = self.process.poll()
        if code is None:
            return
        self.returncode = code
        self.finished_at = utc_now()
        if self.log_handle is not None and not self.log_handle.closed:
            self.log_handle.close()

    @property
    def status(self) -> str:
        self.refresh()
        if self.returncode is None:
            return "running"
        if self.returncode == 0:
            return "success"
        return "failed"

    def to_dict(self) -> Dict:
        self.refresh()
        return {
            "job_id": self.job_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "returncode": self.returncode,
            "cwd": safe_rel_path(self.cwd, ROOT),
            "log_path": safe_rel_path(self.log_path, ROOT),
            "command_preview": shell_preview(self.command),
            "env": self.env,
            "artifacts": infer_job_artifacts(self.workflow_id, self.env, self.log_path),
        }


REGISTRY = load_registry(REGISTRY_PATH)
WORKFLOWS = {wf["id"]: wf for wf in REGISTRY["workflows"]}
JOBS: Dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def workflow_payload() -> List[Dict]:
    result = []
    for wf in REGISTRY["workflows"]:
        item = dict(wf)
        item["cwd"] = safe_rel_path((ROOT / wf["cwd"]).resolve(), ROOT)
        result.append(item)
    return result


def read_json(handler: BaseHTTPRequestHandler) -> Dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def serve_static(handler: BaseHTTPRequestHandler, rel_path: str) -> None:
    rel = rel_path.lstrip("/")
    if rel == "":
        rel = "index.html"
    file_path = (STATIC_DIR / rel).resolve()
    if not file_path.is_file() or STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
        handler.send_error(HTTPStatus.NOT_FOUND)
        return
    content_type = "text/plain"
    if file_path.suffix == ".html":
        content_type = "text/html"
    elif file_path.suffix == ".css":
        content_type = "text/css"
    elif file_path.suffix == ".js":
        content_type = "application/javascript"
    text_response(handler, HTTPStatus.OK, file_path.read_text(encoding="utf-8"), content_type)


def allowed_env(workflow: Dict, requested: Dict[str, str], allow_extra: bool = False) -> Dict[str, str]:
    allowed = {}
    declared = {item["name"]: item for item in workflow.get("env", [])}
    for name, meta in declared.items():
        value = requested.get(name, meta.get("default", ""))
        allowed[name] = str(value).strip()
    if allow_extra:
        for name, value in requested.items():
            if name in declared:
                continue
            name = str(name).strip()
            if not name:
                continue
            allowed[name] = str(value).strip()
    return allowed


def launch_job(workflow: Dict, requested_env: Dict[str, str], allow_extra_env: bool = False) -> Job:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env_values = allowed_env(workflow, requested_env, allow_extra=allow_extra_env)
    runtime_env = os.environ.copy()
    runtime_env["ROOT"] = str(ROOT)
    for key, value in env_values.items():
        if value:
            runtime_env[key] = value
        else:
            runtime_env.pop(key, None)

    cwd = (ROOT / workflow["cwd"]).resolve()
    job_id = uuid.uuid4().hex[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"{stamp}_{job_id}_{workflow['id'].replace('.', '_')}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        workflow["command"],
        cwd=str(cwd),
        env=runtime_env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    job = Job(
        job_id=job_id,
        workflow_id=workflow["id"],
        workflow_name=workflow["display_name"],
        command=workflow["command"],
        cwd=cwd,
        env=env_values,
        log_path=log_path,
        started_at=utc_now(),
        process=process,
        log_handle=log_handle,
    )

    def watcher() -> None:
        process.wait()
        job.refresh()

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    return job


def tail_log(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return ""
    data = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(data[-lines:])


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "StreamDFPWorkbench/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            serve_static(self, "index.html")
            return
        if parsed.path.startswith("/static/"):
            serve_static(self, parsed.path[len("/static/"):])
            return
        if parsed.path == "/api/workflows":
            json_response(self, HTTPStatus.OK, {"title": REGISTRY.get("title", "Workbench"), "workflows": workflow_payload()})
            return
        if parsed.path == "/api/results/summary":
            json_response(self, HTTPStatus.OK, results_summary())
            return
        if parsed.path == "/api/preflight":
            json_response(self, HTTPStatus.OK, preflight_summary())
            return
        if parsed.path == "/api/storage":
            json_response(self, HTTPStatus.OK, storage_summary())
            return
        if parsed.path == "/api/cleanup-preview":
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "targets": [
                        "save_model/*.pickle",
                        "pyloader/phase3_train_*",
                        "pyloader/phase3_test_*",
                        "pyloader/phase3b7_train_*",
                        "pyloader/phase3b7_test_*",
                        "llm/framework_v1/phase3_variants/*.jsonl",
                        "llm/framework_v1/phase3_variants_batch7/*.jsonl",
                        "llm/framework_v1_mc1/phase3_variants/*.jsonl",
                    ]
                },
            )
            return
        if parsed.path == "/api/jobs":
            with JOBS_LOCK:
                jobs = [job.to_dict() for job in sorted(JOBS.values(), key=lambda item: item.started_at, reverse=True)]
            json_response(self, HTTPStatus.OK, {"jobs": jobs})
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/log"):
            job_id = parsed.path.split("/")[3]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            params = parse_qs(parsed.query)
            line_count = int(params.get("lines", ["120"])[0])
            json_response(self, HTTPStatus.OK, {"job_id": job_id, "log": tail_log(job.log_path, lines=line_count)})
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/")[3]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            json_response(self, HTTPStatus.OK, job.to_dict())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            payload = read_json(self)
            workflow_id = payload.get("workflow_id", "")
            workflow = WORKFLOWS.get(workflow_id)
            if workflow is None:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": f"unknown workflow: {workflow_id}"})
                return
            requested_env = payload.get("env", {})
            if not isinstance(requested_env, dict):
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "env must be a JSON object"})
                return
            job = launch_job(workflow, requested_env)
            with JOBS_LOCK:
                JOBS[job.job_id] = job
            json_response(self, HTTPStatus.OK, {"job": job.to_dict()})
            return
        if parsed.path == "/api/run_custom":
            payload = read_json(self)
            workflow_id = payload.get("workflow_id", "")
            workflow = WORKFLOWS.get(workflow_id)
            if workflow is None:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": f"unknown workflow: {workflow_id}"})
                return
            requested_env = payload.get("env", {})
            if not isinstance(requested_env, dict):
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "env must be a JSON object"})
                return
            job = launch_job(workflow, requested_env, allow_extra_env=True)
            with JOBS_LOCK:
                JOBS[job.job_id] = job
            json_response(self, HTTPStatus.OK, {"job": job.to_dict()})
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/stop"):
            job_id = parsed.path.split("/")[3]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            if job.status != "running":
                json_response(self, HTTPStatus.OK, {"job": job.to_dict(), "message": "job already stopped"})
                return
            job.process.terminate()
            json_response(self, HTTPStatus.OK, {"job": job.to_dict(), "message": "termination requested"})
            return
        if parsed.path == "/api/cleanup/experiment-artifacts":
            try:
                payload = cleanup_experiment_artifacts()
            except RuntimeError as exc:
                json_response(self, HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            json_response(self, HTTPStatus.OK, payload)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        return


def validate_registry() -> None:
    print(f"Loaded {len(REGISTRY['workflows'])} workflows from {REGISTRY_PATH}")
    for workflow in REGISTRY["workflows"]:
        cwd = (ROOT / workflow["cwd"]).resolve()
        if not cwd.exists():
            raise SystemExit(f"missing cwd for {workflow['id']}: {cwd}")
        print(f"- {workflow['id']}: {workflow['display_name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the StreamDFP local workbench UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--check", action="store_true", help="Validate the workflow registry and exit.")
    args = parser.parse_args()

    if args.check:
        validate_registry()
        return

    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"StreamDFP Workbench listening on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
