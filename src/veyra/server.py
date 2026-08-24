"""Local laboratory HTTP server — JSON API + React Workbench."""

from __future__ import annotations

import json
import threading
import urllib.request
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from veyra.api import experiment_card, session_payload
from veyra.catalog import bind_model_kwargs, catalog_payload, sweep_model
from veyra.core import VERSION, json_default
from veyra.dsl import run_path, run_suite
from veyra.geometry import geometry_measure
from veyra.lens import inspect_expression, inspect_file_result
from veyra.mathematics import fourier_transform, math_console
from veyra.physics import run_named
from veyra.measure import analyze_measurement, list_lab_csv
from veyra.protocol import methods_from_record, methods_page, methods_paragraph
from veyra.report import render_session
from veyra.reproduce import compare_records, delete_run, list_runs, load, load_prefs, reproduce, save_prefs, store
from veyra.stats import fit_model, propagate_uncertainty, sensitivity_analysis
from veyra.units import convert_quantity
from veyra.verify import verify_model
from veyra.workbench import collect_results


def workbench_dist() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "workbench" / "dist",
        Path.cwd() / "workbench" / "dist",
        here.parent / "static" / "workbench",
    ]
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    return None


def lab_health() -> dict[str, Any]:
    catalog = catalog_payload()
    return {
        "ok": True,
        "veyra": VERSION,
        "laboratory": "http://127.0.0.1:8765/",
        "models": catalog["count"],
        "workbench": bool(workbench_dist()),
        "tagline": "Don't guess the science. Run it.",
    }


@dataclass
class LabState:
    workspace: Path
    target: Path | None
    results: list[Any] = field(default_factory=list)

    def ensure(self) -> list[Any]:
        if not self.results:
            self.results = collect_results(self.target, self.workspace)
            for item in self.results:
                store(item, self.workspace)
            self.persist()
        return self.results

    def prepend(self, result: Any, model: str | None = None) -> dict[str, Any]:
        store(result, self.workspace, model=model)
        self.results.insert(0, result)
        self.persist()
        return experiment_card(result, model)

    def persist(self) -> None:
        dest = self.workspace / ".veyra"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "session.json").write_text(
            json.dumps(self.session(), indent=2, default=json_default),
            encoding="utf-8",
        )

    def session(self) -> dict[str, Any]:
        self.ensure()
        prefs = load_prefs(self.workspace)
        return session_payload(
            self.results,
            list_runs(self.workspace, limit=48),
            pinned=list(prefs.get("pinned") or []),
            titles=dict(prefs.get("titles") or {}),
        )

    def organize(self, action: str, run_id: str, title: str = "") -> dict[str, Any]:
        self.ensure()
        prefs = load_prefs(self.workspace)
        pinned = [str(item) for item in prefs.get("pinned") or []]
        titles = {str(key): str(value) for key, value in (prefs.get("titles") or {}).items()}
        if action == "pin":
            if run_id not in pinned:
                pinned.insert(0, run_id)
        elif action == "unpin":
            pinned = [item for item in pinned if item != run_id]
        elif action == "rename" and title.strip():
            titles[run_id] = title.strip()
        elif action == "delete":
            self.results = [item for item in self.results if item.run_id != run_id]
            delete_run(run_id, self.workspace)
            pinned = [item for item in pinned if item != run_id]
            titles.pop(run_id, None)
        else:
            return {"ok": False, "error": "unknown action"}
        save_prefs(self.workspace, {"pinned": pinned, "titles": titles})
        self.persist()
        return self.session()


class LabHandler(SimpleHTTPRequestHandler):
    state: LabState

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _text(self, body: str, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in {"/api/health", "/api/version"}:
            self._json(lab_health())
            return
        if path == "/api/session":
            self._json(self.state.session())
            return
        if path == "/api/catalog":
            self._json(catalog_payload())
            return
        if path == "/api/data-files":
            self._json({"files": list_lab_csv(self.state.workspace)})
            return
        if path == "/api/history":
            self._json({"history": list_runs(self.state.workspace, limit=48)})
            return
        if path == "/api/export":
            run_id = (query.get("run") or [""])[0]
            if run_id:
                record = load(run_id, self.state.workspace)
                self._json(record)
                return
            self._json(self.state.session())
            return
        if path == "/api/reproduce":
            run_id = (query.get("run") or [""])[0]
            if not run_id:
                self._json({"ok": False, "error": "run required"}, 400)
                return
            result = reproduce(run_id, self.state.workspace)
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if path == "/api/protocol":
            run_id = (query.get("run") or [""])[0]
            if run_id:
                record = load(run_id, self.state.workspace)
                self._json({"methods": methods_from_record(record), "run_id": run_id})
                return
            self.state.ensure()
            if not self.state.results:
                self._json({"ok": False, "error": "no run"}, 404)
                return
            current = self.state.results[0]
            self._json({"methods": methods_paragraph(current), "run_id": current.run_id})
            return
        if path in {"/api/methods.html", "/methods.html"}:
            run_id = (query.get("run") or [""])[0]
            if run_id:
                record = load(run_id, self.state.workspace)
                self._text(methods_page(record))
                return
            self.state.ensure()
            if not self.state.results:
                self._json({"ok": False, "error": "no run"}, 404)
                return
            self._text(methods_page(self.state.results[0].to_dict()))
            return
        if path == "/api/compare":
            a, b = (query.get("a") or [""])[0], (query.get("b") or [""])[0]
            if not a or not b:
                self._json({"ok": False, "error": "a and b required"}, 400)
                return
            result = compare_records(load(a, self.state.workspace), load(b, self.state.workspace))
            self._json(experiment_card(result))
            return
        if path == "/" or path == "/index.html":
            dist = workbench_dist()
            if dist:
                self._text((dist / "index.html").read_text(encoding="utf-8"))
                return
            results = self.state.ensure()
            self._text(render_session(results, list_runs(self.state.workspace)))
            return
        dist = workbench_dist()
        if dist:
            return SimpleHTTPRequestHandler.do_GET(self)
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._read_json()
        if parsed.path == "/api/run":
            model = str(body.get("model") or "projectile")
            if model == "fit":
                result = fit_model(
                    body.get("x") or [0, 1, 2, 3, 4],
                    body.get("y") or [0.1, 2.0, 3.9, 6.2, 8.1],
                    str(body.get("fit_model") or "linear"),
                )
            else:
                kwargs = bind_model_kwargs(model, {k: v for k, v in body.items() if k != "model"})
                try:
                    result = run_named(model, **kwargs)
                except TypeError:
                    result = run_named(model)
            self.state.ensure()
            self._json(self.state.prepend(result, model))
            return
        if parsed.path == "/api/experiment":
            target = Path(body.get("path") or "")
            if not target.is_file():
                self._json({"ok": False, "error": "experiment not found"}, 404)
                return
            self.state.ensure()
            results = run_path(target)
            for item in results:
                self.state.prepend(item)
            self._json(self.state.session())
            return
        if parsed.path == "/api/suite":
            root = Path(body.get("path") or self.state.workspace / "examples")
            if not root.exists():
                root = self.state.workspace
            suite = run_suite(root)
            self.state.ensure()
            self.state.prepend(suite)
            self._json(experiment_card(suite))
            return
        if parsed.path == "/api/measure":
            overlay_params = {
                key: value
                for key, value in body.items()
                if key not in {"csv", "path", "x", "y", "x_unit", "y_unit", "fit", "overlay", "overlay_params"}
                and isinstance(value, (int, float))
            }
            extra = body.get("overlay_params") or {}
            if isinstance(extra, dict):
                overlay_params.update(extra)
            result = analyze_measurement(
                csv_text=str(body.get("csv") or ""),
                path=body.get("path") or None,
                x=str(body.get("x") or ""),
                y=str(body.get("y") or ""),
                x_unit=str(body.get("x_unit") or ""),
                y_unit=str(body.get("y_unit") or ""),
                fit=str(body.get("fit") or "linear"),
                overlay=str(body.get("overlay") or ""),
                overlay_params=overlay_params,
                workspace=self.state.workspace,
            )
            self.state.ensure()
            self._json(self.state.prepend(result, "measure"))
            return
        if parsed.path == "/api/math":
            result = math_console(
                str(body.get("expression") or body.get("equation") or "x"),
                str(body.get("action") or "auto"),
                str(body.get("variable") or "x"),
                body.get("lower"),
                body.get("upper"),
            )
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/lens":
            source = str(body.get("source") or "")
            path = str(body.get("path") or "")
            expression = str(body.get("expression") or "")
            if path and Path(path).is_file():
                result = inspect_file_result(Path(path).read_text(encoding="utf-8"), path)
            elif source:
                result = inspect_file_result(source, path or "<console>")
            elif expression:
                result = inspect_expression(expression)
            else:
                self._json({"ok": False, "error": "expression, source, or path required"}, 400)
                return
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/verify":
            path = str(body.get("path") or "")
            source = body.get("source")
            result = verify_model(source=source, path=path or None)
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/convert":
            result = convert_quantity(
                body.get("value") if body.get("value") is not None else "1",
                str(body.get("to") or body.get("to_unit") or "m"),
                str(body.get("from") or body.get("from_unit") or ""),
            )
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/uncertainty":
            variables = body.get("variables") or {"x": [1.0, 0.1]}
            cleaned = {
                str(name): (float(pair[0]), float(pair[1]))
                for name, pair in variables.items()
            }
            result = propagate_uncertainty(str(body.get("expression") or "x"), cleaned)
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/sensitivity":
            variables = {str(k): float(v) for k, v in (body.get("variables") or {"x": 1.0}).items()}
            result = sensitivity_analysis(str(body.get("expression") or "x"), variables)
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/sweep":
            model = str(body.get("model") or "projectile")
            result = sweep_model(
                model,
                str(body.get("param") or "velocity"),
                float(body.get("start") or 0),
                float(body.get("stop") or 1),
                int(body.get("steps") or 12),
                {k: v for k, v in body.items() if k not in {"model", "param", "start", "stop", "steps"}},
            )
            self.state.ensure()
            self._json(self.state.prepend(result, model))
            return
        if parsed.path == "/api/geometry":
            result = geometry_measure(
                str(body.get("kind") or "area_circle"),
                points=body.get("points"),
                radius=body.get("radius"),
                dimensions=body.get("dimensions"),
            )
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/fourier":
            values = body.get("values") or [0, 1, 0, -1]
            if isinstance(values, str):
                values = [float(part) for part in values.replace(",", " ").split() if part]
            result = fourier_transform(list(values), float(body.get("sample_rate") or 1.0))
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/reproduce":
            run_id = str(body.get("run") or body.get("run_id") or "")
            if not run_id:
                self._json({"ok": False, "error": "run required"}, 400)
                return
            result = reproduce(run_id, self.state.workspace)
            self.state.ensure()
            self._json(self.state.prepend(result))
            return
        if parsed.path == "/api/organize":
            action = str(body.get("action") or "")
            run_id = str(body.get("run_id") or "")
            if not action or not run_id:
                self._json({"ok": False, "error": "action and run_id required"}, 400)
                return
            payload = self.state.organize(action, run_id, str(body.get("title") or ""))
            if payload.get("ok") is False:
                self._json(payload, 400)
                return
            self._json(payload)
            return
        self._json({"error": "not found", "path": parsed.path}, 404)


def make_server(host: str, port: int, workspace: Path, target: Path | None) -> ThreadingHTTPServer:
    dist = workbench_dist()
    directory = str(dist) if dist else str(workspace)
    state = LabState(workspace=workspace, target=target)

    class BoundHandler(LabHandler):
        pass

    BoundHandler.state = state
    handler = partial(BoundHandler, directory=directory)
    return ThreadingHTTPServer((host, port), handler)


def serve_forever(host: str, port: int, workspace: Path, target: Path | None) -> None:
    httpd = make_server(host, port, workspace, target)
    httpd.serve_forever()


def serve_background(host: str, port: int, workspace: Path, target: Path | None) -> ThreadingHTTPServer:
    httpd = make_server(host, port, workspace, target)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


_LAB_SERVER: ThreadingHTTPServer | None = None


def ensure_running(workspace: Path | None = None, port: int = 8765) -> dict[str, Any]:
    """Start the HTTP laboratory on localhost if it is down. Safe to call from MCP."""
    import time

    payload = lab_health()
    payload["laboratory"] = f"http://127.0.0.1:{port}/"
    payload["start"] = "python -m veyra serve examples"
    payload["cursor"] = "Command Palette → Veyra: Open Laboratory"
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
            remote = json.loads(response.read().decode("utf-8"))
            payload["running"] = True
            payload["started"] = False
            if remote.get("veyra"):
                payload["served"] = remote["veyra"]
            return payload
    except Exception:  # noqa: BLE001
        payload["running"] = False
    global _LAB_SERVER
    ws = (workspace or Path.cwd()).resolve()
    target = ws / "examples" if (ws / "examples").is_dir() else None
    try:
        _LAB_SERVER = serve_background("127.0.0.1", port, ws, target)
    except OSError as error:
        payload["started"] = False
        payload["error"] = str(error)
        return payload
    for _ in range(25):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.3):
                payload["running"] = True
                payload["started"] = True
                return payload
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    payload["started"] = True
    payload["error"] = "server started but health not ready"
    return payload
