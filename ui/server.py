#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"
STATIC_DIR = UI_DIR / "static"
REGISTRY_PATH = UI_DIR / "workflows.json"
LOG_DIR = ROOT / "logs" / "ui_runs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def shell_preview(command: List[str]) -> str:
    return shlex.join(command)


def safe_rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


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


def allowed_env(workflow: Dict, requested: Dict[str, str]) -> Dict[str, str]:
    allowed = {}
    declared = {item["name"]: item for item in workflow.get("env", [])}
    for name, meta in declared.items():
        value = requested.get(name, meta.get("default", ""))
        allowed[name] = str(value).strip()
    return allowed


def launch_job(workflow: Dict, requested_env: Dict[str, str]) -> Job:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env_values = allowed_env(workflow, requested_env)
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
