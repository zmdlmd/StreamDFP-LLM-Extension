#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_STATIC = ROOT / "ui" / "static"
OUTPUT = ROOT / "docs" / "demo" / "streamdfp_workbench_static_snapshot_20260402.html"


def load_server_module():
    server_path = ROOT / "ui" / "server.py"
    spec = importlib.util.spec_from_file_location("streamdfp_workbench_server", server_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def script_safe_json(data) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def main() -> None:
    server = load_server_module()

    index_html = (UI_STATIC / "index.html").read_text(encoding="utf-8")
    styles = (UI_STATIC / "styles.css").read_text(encoding="utf-8")
    app_js = (UI_STATIC / "app.js").read_text(encoding="utf-8").replace("</script>", "<\\/script>")

    payload = {
        "workflows": {
            "title": server.REGISTRY.get("title", "StreamDFP Workbench"),
            "workflows": server.workflow_payload(),
        },
        "results": server.results_summary(),
        "preflight": server.preflight_summary(),
        "storage": server.storage_summary(),
        "jobs": {"jobs": []},
        "cleanup_preview": {
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
    }

    banner_html = """
      <section class="static-banner">
        <strong>静态演示版</strong>
        <span>这个 HTML 已经内联样式、脚本和结果快照，可在其他电脑直接打开。</span>
        <span>启动作业、停止作业和清理产物等操作在静态版中已禁用。</span>
      </section>
    """

    extra_css = """
      .static-banner {
        margin-bottom: 1rem;
        padding: 0.95rem 1rem;
        border-radius: 1rem;
        border: 1px solid rgba(24, 76, 71, 0.18);
        background: linear-gradient(180deg, rgba(215, 235, 230, 0.72) 0%, rgba(255, 253, 248, 0.92) 100%);
        display: grid;
        gap: 0.25rem;
        box-shadow: 0 18px 40px rgba(32, 30, 20, 0.08);
      }
      .static-banner strong {
        font-size: 1rem;
      }
      .static-banner span {
        color: #6a6d62;
      }
    """

    bootstrap = f"""
<script>
window.__STREAMDFP_STATIC_DEMO__ = {script_safe_json(payload)};
(function() {{
  const data = window.__STREAMDFP_STATIC_DEMO__;
  function jsonResponse(payload, status) {{
    return Promise.resolve(new Response(JSON.stringify(payload), {{
      status: status || 200,
      headers: {{ "Content-Type": "application/json; charset=utf-8" }}
    }}));
  }}
  const originalFetch = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function(url, options) {{
    const requestUrl = typeof url === "string" ? url : String(url);
    const method = ((options && options.method) || "GET").toUpperCase();
    if (requestUrl === "/api/workflows" && method === "GET") return jsonResponse(data.workflows);
    if (requestUrl === "/api/results/summary" && method === "GET") return jsonResponse(data.results);
    if (requestUrl === "/api/preflight" && method === "GET") return jsonResponse(data.preflight);
    if (requestUrl === "/api/storage" && method === "GET") return jsonResponse(data.storage);
    if (requestUrl === "/api/cleanup-preview" && method === "GET") return jsonResponse(data.cleanup_preview);
    if (requestUrl === "/api/jobs" && method === "GET") return jsonResponse(data.jobs);
    if (requestUrl.startsWith("/api/jobs/") && requestUrl.endsWith("/log") && method === "GET") {{
      return jsonResponse({{ job_id: "static-demo", log: "静态演示版不包含实时作业日志。" }});
    }}
    if (requestUrl.startsWith("/api/jobs/") && method === "GET") {{
      return jsonResponse({{ error: "静态演示版不包含实时作业状态。" }}, 404);
    }}
    if (
      requestUrl === "/api/run" ||
      requestUrl === "/api/run_custom" ||
      requestUrl === "/api/cleanup/experiment-artifacts" ||
      requestUrl.endsWith("/stop")
    ) {{
      return jsonResponse({{ error: "这是静态演示版，不能执行写操作。" }}, 409);
    }}
    if (originalFetch) return originalFetch(url, options);
    return Promise.reject(new Error("fetch unavailable"));
  }};
}})();
</script>
<script>
{app_js}
</script>
"""

    html = index_html.replace(
        '<link rel="stylesheet" href="/static/styles.css" />',
        f"<style>\n{styles}\n{extra_css}\n</style>",
    )
    html = html.replace('<script src="/static/app.js"></script>', bootstrap)
    html = html.replace('<main class="tab-shell">', f"{banner_html}\n      <main class=\"tab-shell\">", 1)
    html = html.replace("<title>StreamDFP 实验工作台</title>", "<title>StreamDFP 实验工作台（静态演示版）</title>")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
