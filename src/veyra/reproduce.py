"""Run fingerprints, history, and experiment reproduction."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veyra.core import Check, Metric, VeyraResult, json_default

RUN_DIR = Path(".veyra") / "runs"
ARTIFACT_DIR = Path(".veyra") / "results"


def store(result: VeyraResult, root: str | Path = ".", model: str | None = None) -> Path:
    from veyra.catalog import guess_model

    directory = Path(root) / RUN_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.run_id}.json"
    payload = result.to_dict()
    payload["model"] = model or guess_model(result.kind, result.title)
    payload["stored_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2, default=json_default), encoding="utf-8")
    artifact_dir = Path(root) / ARTIFACT_DIR
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"{result.run_id}.veyr"
    artifact_payload = {
        "format": "veyr/1",
        "run": payload,
        "experiment": payload.get("details", {}).get("experiment"),
        "graph": payload.get("details", {}).get("experiment_graph"),
        "reproducibility": payload.get("details", {}).get("reproducibility"),
    }
    artifact.write_text(json.dumps(artifact_payload, indent=2, default=json_default), encoding="utf-8")
    latest = directory / "latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def load(run_id: str, root: str | Path = ".") -> dict[str, Any]:
    directory = Path(root) / RUN_DIR
    if run_id in {"latest", ""}:
        path = directory / "latest.json"
    else:
        matches = list(directory.glob(f"{run_id}*.json"))
        path = matches[0] if matches else directory / f"{run_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def prefs_path(root: str | Path = ".") -> Path:
    return Path(root) / ".veyra" / "prefs.json"


def load_prefs(root: str | Path = ".") -> dict[str, Any]:
    path = prefs_path(root)
    if not path.is_file():
        return {"pinned": [], "titles": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"pinned": [], "titles": {}}
    payload.setdefault("pinned", [])
    payload.setdefault("titles", {})
    return payload


def save_prefs(root: str | Path, prefs: dict[str, Any]) -> None:
    path = prefs_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def delete_run(run_id: str, root: str | Path = ".") -> bool:
    directory = Path(root) / RUN_DIR
    removed = False
    if not directory.exists() or not run_id:
        return False
    for path in directory.glob(f"{run_id}*.json"):
        if path.name == "latest.json":
            continue
        path.unlink(missing_ok=True)
        removed = True
    artifact_dir = Path(root) / ARTIFACT_DIR
    for path in artifact_dir.glob(f"{run_id}*.veyr") if artifact_dir.exists() else []:
        path.unlink(missing_ok=True)
        removed = True
    latest = directory / "latest.json"
    if latest.is_file():
        try:
            current = json.loads(latest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = {}
        if str(current.get("run_id", "")).startswith(run_id):
            remaining = list_runs(root, limit=1)
            if remaining:
                latest.write_text(json.dumps(remaining[0], indent=2, default=json_default), encoding="utf-8")
            else:
                latest.unlink(missing_ok=True)
    return removed


def list_runs(root: str | Path = ".", limit: int = 48) -> list[dict[str, Any]]:
    directory = Path(root) / RUN_DIR
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    paths = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        if path.name == "latest.json":
            continue
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
        if len(records) >= limit:
            break
    return records


def history_result(root: str | Path = ".") -> VeyraResult:
    records = list_runs(root)
    checks = [
        Check(
            f"{item.get('run_id', '?')}  {item.get('title', '')}",
            bool(item.get("ok", False)),
            item.get("kind", ""),
        )
        for item in records
    ]
    return VeyraResult(
        ok=True,
        kind="laboratory notebook",
        title="Run history",
        checks=checks or [Check("runs recorded", True, "none yet")],
        metrics=[Metric("runs", len(records))],
        details={"records": records},
        inputs={"root": str(root)},
        solver="veyra notebook",
    )


def compare_records(a: dict[str, Any], b: dict[str, Any]) -> VeyraResult:
    metrics_a = {item["name"]: item for item in a.get("metrics", [])}
    metrics_b = {item["name"]: item for item in b.get("metrics", [])}
    names = sorted(set(metrics_a) | set(metrics_b))
    checks: list[Check] = []
    metrics: list[Metric] = []
    for name in names:
        left, right = metrics_a.get(name), metrics_b.get(name)
        if left is None or right is None:
            checks.append(Check(name, False, "missing in one run"))
            continue
        try:
            delta = float(right["value"]) - float(left["value"])
            scale = max(abs(float(left["value"])), 1e-15)
            rel = abs(delta) / scale
            checks.append(Check(name, rel < 1e-6, f"Δ={delta:.4g}"))
            metrics.append(Metric(name, delta, left.get("unit", "")))
        except (TypeError, ValueError):
            same = str(left["value"]) == str(right["value"])
            checks.append(Check(name, same, "non-numeric"))
    return VeyraResult(
        ok=all(item.passed for item in checks) if checks else True,
        kind="run comparison",
        title="Veyra Diff",
        checks=checks,
        metrics=metrics,
        inputs={"a": a.get("run_id"), "b": b.get("run_id")},
        solver="metric delta",
    )


def reproduce(run_id: str, root: str | Path = ".") -> VeyraResult:
    from veyra.catalog import bind_model_kwargs, guess_model, numeric_inputs
    from veyra.dsl import run_path
    from veyra.physics import run_named

    record = load(run_id, root)
    kind = record.get("kind", "")
    inputs = record.get("inputs") or {}
    source = inputs.get("source") or record.get("details", {}).get("source")
    replay: VeyraResult | None = None
    if source and str(source).endswith(".veyra"):
        results = run_path(source)
        replay = results[0] if results else None
    model = record.get("model") or guess_model(str(kind), str(record.get("title") or ""))
    if replay is None and model:
        try:
            kwargs = bind_model_kwargs(str(model), numeric_inputs(inputs))
            replay = run_named(str(model), **kwargs)
        except Exception:  # noqa: BLE001
            replay = None
    if replay is None:
        return VeyraResult(
            ok=False,
            kind="reproduce",
            title="Replay record",
            checks=[Check("reproduced", False, "no executable source")],
            details={"original": record},
            run_id=record.get("run_id", run_id),
            inputs=inputs,
            solver="record replay",
        )
    compared = compare_records(record, replay.to_dict())
    original_platform = record.get("platform") or {}
    current_platform = replay.to_dict().get("platform") or {}
    environment_identical = not original_platform or original_platform == current_platform
    environment_detail = "identical" if environment_identical else "platform or Python version changed"
    replay.checks = [
        Check("reproduced from fingerprint", True, run_id),
        Check("environment matches original", environment_identical, environment_detail),
    ] + compared.checks + replay.checks
    replay.ok = replay.ok and compared.ok
    replay.title = f"Reproduce {record.get('title', run_id)}"
    return replay
