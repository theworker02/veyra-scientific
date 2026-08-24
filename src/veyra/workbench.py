"""Assemble a laboratory session for the Workbench."""

from __future__ import annotations

import json
from pathlib import Path

from veyra.api import session_payload
from veyra.core import VeyraResult, json_default
from veyra.dsl import run_path
from veyra.physics import simulate_motion
from veyra.report import write_session
from veyra.reproduce import list_runs, store


def collect_results(target: Path | None = None, root: Path | None = None) -> list[VeyraResult]:
    workspace = root or Path.cwd()
    results: list[VeyraResult] = []
    if target and target.is_file() and target.suffix == ".veyra":
        results = run_path(target)
    elif target and target.is_dir():
        results = _reload_dir(target)
    elif (workspace / "examples").is_dir():
        results = _reload_dir(workspace / "examples")
    else:
        results = [simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.15, trials=64)]
    if not results:
        results = [simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.15, trials=64)]
    return results


def build_session(target: Path | None = None, root: Path | None = None) -> tuple[list[VeyraResult], Path]:
    workspace = root or Path.cwd()
    results = collect_results(target, workspace)
    for item in results:
        store(item, workspace)
    dest_dir = workspace / ".veyra"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "workbench.html"
    history = list_runs(workspace)
    write_session(results, dest, history=history)
    payload = session_payload(results, history)
    (dest_dir / "session.json").write_text(
        json.dumps(payload, indent=2, default=json_default),
        encoding="utf-8",
    )
    return results, dest


def _reload_dir(directory: Path) -> list[VeyraResult]:
    items: list[VeyraResult] = []
    for file in sorted(directory.glob("*.veyra")):
        items.extend(run_path(file))
    return items
