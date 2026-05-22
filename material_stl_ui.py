"""Local browser UI that generates STL files.

This UI has a small Python backend because STL generation requires local
Python code and filesystem writes. It opens in the browser, but the Python
process must remain running while the page is used.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from config_to_stl import generate_from_config_data
from examples.random_material_edge_list_demo import generate_demo as generate_edge_list_demo
from examples.voronoi_random_material_demo import generate_demo as generate_voronoi_demo


DEFAULT_CONFIG_PATH = Path("sample_configs/multimaterial_test.json")


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Material STL Generator</title>
  <style>
    :root {
      --bg: #f4f6f8;
      --panel: #ffffff;
      --border: #d4dae3;
      --text: #1f2937;
      --muted: #5b6472;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --danger: #b91c1c;
      --code: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.4;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
    }
    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: minmax(440px, 1fr) minmax(420px, 0.95fr);
      gap: 14px;
      padding: 14px;
      min-height: calc(100vh - 56px);
    }
    section {
      min-width: 0;
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .bar {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      background: #fbfcfd;
    }
    .bar label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    input, textarea {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
    }
    input {
      height: 34px;
      padding: 0 9px;
    }
    textarea {
      flex: 1;
      min-height: 560px;
      resize: none;
      padding: 12px;
      color: var(--code);
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      outline: none;
      tab-size: 2;
    }
    button {
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 12px;
      background: white;
      color: var(--text);
      font: inherit;
      font-weight: 650;
      cursor: pointer;
      white-space: nowrap;
    }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }
    button.primary:hover { background: var(--accent-dark); }
    button:disabled { opacity: 0.58; cursor: wait; }
    .result {
      flex: 1;
      overflow: auto;
      padding: 12px;
    }
    .status {
      min-height: 34px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      border-bottom: 1px solid var(--border);
      background: #fbfcfd;
      color: var(--muted);
    }
    .status.error { color: var(--danger); }
    table {
      width: 100%;
      table-layout: fixed;
      border-collapse: collapse;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 12px;
    }
    th, td {
      padding: 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      background: #fbfcfd;
      font-size: 12px;
      font-weight: 700;
    }
    tr:last-child td { border-bottom: 0; }
    a {
      color: var(--accent-dark);
      font-weight: 650;
      text-decoration: none;
    }
    a:hover { text-decoration: underline; }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--danger);
      background: #fff;
    }
    @media (max-width: 920px) {
      main { grid-template-columns: 1fr; }
      textarea { min-height: 420px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Material STL Generator</h1>
    <div>
      <button id="demo">Create Edge-List Demo</button>
      <button id="voronoiDemo">Load Voronoi Demo</button>
      <button id="generate" class="primary">Generate STLs</button>
    </div>
  </header>
  <main>
    <section>
      <div class="bar">
        <label for="configPath">Config path</label>
        <input id="configPath" value="sample_configs/multimaterial_test.json">
        <button id="load">Load</button>
        <button id="save">Save</button>
      </div>
      <textarea id="config" spellcheck="false"></textarea>
    </section>
    <section>
      <div id="status" class="status">Loading sample config...</div>
      <div id="result" class="result"></div>
    </section>
  </main>
  <script>
    const configPath = document.getElementById("configPath");
    const config = document.getElementById("config");
    const statusEl = document.getElementById("status");
    const resultEl = document.getElementById("result");
    const buttons = [...document.querySelectorAll("button")];

    function setBusy(busy) {
      buttons.forEach(button => button.disabled = busy);
    }

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", isError);
    }

    function fileLink(path, label) {
      return `<a target="_blank" rel="noreferrer" href="/file?path=${encodeURIComponent(path)}">${label}</a>`;
    }

    async function post(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body || {})
      });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function renderResult(result) {
      if (!result || !result.jobs) {
        resultEl.innerHTML = "";
        return;
      }
      resultEl.innerHTML = result.jobs.map(job => {
        const rows = (job.outputs || []).map(output => `
          <tr>
            <td>${output.material}</td>
            <td>${output.faces}</td>
            <td>${output.watertight ? "yes" : "no"}</td>
            <td>${fileLink(output.path, output.path)}</td>
          </tr>
        `).join("");
        const preview = job.preview && job.preview.path
          ? `<p>${fileLink(job.preview.path, "Open material preview")}</p>`
          : "";
        return `
          <h2>${job.name}</h2>
          <p>${job.edge_count} edges, ${job.material_count} STL files</p>
          <table>
            <thead><tr><th>Material</th><th>Faces</th><th>Watertight</th><th>File</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          ${preview}
        `;
      }).join("");
    }

    async function loadConfig(path) {
      const payload = await post("/load", {path});
      config.value = payload.text;
      configPath.value = payload.path;
      setStatus("Config loaded");
    }

    document.getElementById("load").addEventListener("click", async () => {
      setBusy(true);
      try {
        await loadConfig(configPath.value);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("save").addEventListener("click", async () => {
      setBusy(true);
      try {
        const payload = await post("/save", {path: configPath.value, text: config.value});
        configPath.value = payload.path;
        setStatus("Config saved");
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("generate").addEventListener("click", async () => {
      setBusy(true);
      resultEl.innerHTML = "";
      setStatus("Generating STL files...");
      try {
        const payload = await post("/generate", {
          config_path: configPath.value,
          config_text: config.value
        });
        renderResult(payload.result);
        setStatus("STL generation complete");
      } catch (error) {
        resultEl.innerHTML = `<pre>${error.message}</pre>`;
        setStatus("Generation failed", true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("demo").addEventListener("click", async () => {
      setBusy(true);
      setStatus("Creating random-material edge-list demo...");
      try {
        const payload = await post("/demo", {});
        await loadConfig(payload.config_path);
        setStatus(`Demo config created from ${payload.source}`);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setBusy(false);
      }
    });

    document.getElementById("voronoiDemo").addEventListener("click", async () => {
      setBusy(true);
      setStatus("Creating Voronoi random-material demo...");
      try {
        const payload = await post("/voronoi-demo", {});
        await loadConfig(payload.config_path);
        setStatus(`Voronoi demo loaded: ${payload.node_count} nodes, ${payload.edge_count} edges`);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setBusy(false);
      }
    });

    loadConfig("sample_configs/multimaterial_test.json").catch(error => {
      setStatus(error.message, true);
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "MaterialSTLGenerator/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/file":
            params = parse_qs(parsed.query)
            self._send_file(params.get("path", [""])[0])
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/load":
                self._load(payload)
            elif parsed.path == "/save":
                self._save(payload)
            elif parsed.path == "/generate":
                self._generate(payload)
            elif parsed.path == "/demo":
                self._demo()
            elif parsed.path == "/voronoi-demo":
                self._voronoi_demo()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json(
                {"error": f"{exc}\n\n{traceback.format_exc()}"},
                status=HTTPStatus.BAD_REQUEST,
            )

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _load(self, payload: Dict[str, Any]) -> None:
        path = _resolve_path(payload.get("path") or DEFAULT_CONFIG_PATH)
        self._send_json({"path": str(path), "text": path.read_text(encoding="utf-8")})

    def _save(self, payload: Dict[str, Any]) -> None:
        path = _resolve_path(payload.get("path") or DEFAULT_CONFIG_PATH)
        text = str(payload.get("text", ""))
        json.loads(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        self._send_json({"path": str(path)})

    def _generate(self, payload: Dict[str, Any]) -> None:
        config_text = str(payload.get("config_text", "")).strip()
        if not config_text:
            raise ValueError("Config text is required.")
        config = json.loads(config_text)
        path = _resolve_path(payload.get("config_path") or DEFAULT_CONFIG_PATH)
        result = generate_from_config_data(config, base_dir=path.parent)
        self._send_json({"result": result})

    def _demo(self) -> None:
        result = generate_edge_list_demo()
        self._send_json(result)

    def _voronoi_demo(self) -> None:
        result = generate_voronoi_demo()
        self._send_json(result)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status=status)

    def _send_file(self, value: str) -> None:
        path = _resolve_path(value)
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self._send_bytes(path.read_bytes(), content_type)

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _resolve_path(value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local material STL browser UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Material STL Generator running at {url}", flush=True)
    print("Keep this process running while using the browser UI. Press Ctrl+C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
