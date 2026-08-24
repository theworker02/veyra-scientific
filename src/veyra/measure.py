"""Measured data: load a CSV, fit and/or overlay a catalog model, report residual and units."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import numpy as np

from veyra.core import Check, Metric, VeyraResult
from veyra.plots import make_plot, series
from veyra.stats import fit_model
from veyra.units import UREG, dimensional_formula, normalize_unit


def parse_csv(text: str) -> tuple[list[str], dict[str, list[float]]]:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("CSV is empty")
    reader = csv.reader(io.StringIO("\n".join(lines)))
    rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV is empty")
    header = rows[0]
    body = rows[1:]
    numeric_header = True
    try:
        [float(cell) for cell in header if cell]
    except ValueError:
        numeric_header = False
    if numeric_header:
        columns = [f"col{i + 1}" for i in range(len(header))]
        if len(columns) == 2:
            columns = ["x", "y"]
        body = [header, *body]
    else:
        columns = [name or f"col{i + 1}" for i, name in enumerate(header)]
    data: dict[str, list[float]] = {name: [] for name in columns}
    for row in body:
        if len(row) < len(columns):
            continue
        try:
            values = [float(row[i]) for i in range(len(columns))]
        except ValueError:
            continue
        for name, value in zip(columns, values):
            data[name].append(value)
    return columns, data


def _unit_check(name: str, unit: str) -> Check:
    if not unit:
        return Check(f"{name} unit omitted", True, "dimensionless")
    try:
        qty = UREG.Quantity(1, normalize_unit(unit))
        formula = dimensional_formula(qty)
        return Check(f"{name} unit recognized", True, f"{unit} → {formula}")
    except Exception as error:  # noqa: BLE001
        return Check(f"{name} unit recognized", False, str(error))


def resolve_lab_csv(path: str | Path, workspace: Path | None = None) -> Path | None:
    candidate = Path(path)
    if workspace is None:
        return candidate if candidate.is_file() else None
    root = workspace.resolve()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file() or resolved.suffix.lower() != ".csv":
        return None
    return resolved


def list_lab_csv(workspace: Path) -> list[dict[str, str]]:
    root = workspace.resolve()
    found: list[Path] = []
    for folder in (root / "examples" / "data", root):
        if folder.is_dir():
            found.extend(sorted(folder.glob("*.csv")))
    files: list[dict[str, str]] = []
    seen: set[Path] = set()
    for item in found:
        resolved = item.resolve()
        if resolved in seen:
            continue
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        seen.add(resolved)
        files.append(
            {"name": resolved.name, "relative": relative.as_posix(), "path": str(resolved)}
        )
    return files


def _overlay_series(result: VeyraResult) -> tuple[np.ndarray, np.ndarray] | None:
    plot = result.details.get("plot") or {}
    traces = plot.get("series") or []
    if not traces:
        return None
    preferred = next(
        (item for item in traces if str(item.get("id") or "").lower() in {"analytic", "exact", "numeric"}),
        traces[0],
    )
    src_x = preferred.get("x_src") or preferred.get("x") or []
    src_y = preferred.get("y_src") or preferred.get("y") or []
    mx = np.asarray(src_x, dtype=float)
    my = np.asarray(src_y, dtype=float)
    if mx.size < 2 or mx.size != my.size:
        return None
    order = np.argsort(mx)
    return mx[order], my[order]


def analyze_measurement(
    csv_text: str = "",
    path: str | Path | None = None,
    x: str = "",
    y: str = "",
    x_unit: str = "",
    y_unit: str = "",
    fit: str = "linear",
    overlay: str = "",
    overlay_params: dict[str, Any] | None = None,
    workspace: str | Path | None = None,
) -> VeyraResult:
    """Load tabulated measurements, optionally fit them, optionally overlay a catalog model."""
    root = Path(workspace) if workspace else None
    source = resolve_lab_csv(path, root) if path else None
    if path and source is None:
        return VeyraResult(
            ok=False,
            kind="measurement",
            title="Measurement",
            checks=[Check("CSV loaded", False, "path must be a CSV in the laboratory workspace")],
        )
    if not csv_text:
        if source is None or not source.is_file():
            return VeyraResult(
                ok=False,
                kind="measurement",
                title="Measurement",
                checks=[Check("CSV loaded", False, "path or csv text required")],
            )
        csv_text = source.read_text(encoding="utf-8")
    try:
        columns, data = parse_csv(csv_text)
    except ValueError as error:
        return VeyraResult(
            ok=False,
            kind="measurement",
            title="Measurement",
            checks=[Check("CSV loaded", False, str(error))],
        )
    x_name = x.strip() or (columns[0] if columns else "")
    y_name = y.strip() or (columns[1] if len(columns) > 1 else "")
    if x_name not in data or y_name not in data:
        return VeyraResult(
            ok=False,
            kind="measurement",
            title="Measurement",
            checks=[Check("columns found", False, f"have {columns}; asked {x_name!r}, {y_name!r}")],
        )
    xv = np.asarray(data[x_name], dtype=float)
    yv = np.asarray(data[y_name], dtype=float)
    n = int(xv.size)
    checks = [
        Check("CSV loaded", True, source.name if source else f"{n} rows"),
        Check("n ≥ 3", n >= 3, f"n={n}"),
        _unit_check("x", x_unit),
        _unit_check("y", y_unit),
    ]
    metrics: list[Metric] = [
        Metric("n", n),
        Metric("x column", x_name),
        Metric("y column", y_name),
    ]
    if x_unit:
        metrics.append(Metric("x unit", x_unit))
    if y_unit:
        try:
            y_dim = dimensional_formula(UREG.Quantity(1, normalize_unit(y_unit)))
        except Exception:  # noqa: BLE001
            y_dim = ""
        metrics.append(Metric("y unit", y_unit, notes=y_dim))
    traces = [series("observations", xv, yv)]
    residual = None
    fit_name = (fit or "none").strip().lower()
    if fit_name and fit_name not in {"none", "off", "false"}:
        fitted = fit_model(xv.tolist(), yv.tolist(), fit_name)
        checks.extend(fitted.checks)
        for item in fitted.metrics:
            if item.name == "rmse":
                metrics.append(Metric("fit RMSE", item.value, y_unit, item.uncertainty))
            elif item.name == "r_squared":
                metrics.append(Metric("R²", item.value))
            else:
                metrics.append(item)
        pred = np.asarray(fitted.details.get("y_hat") or [], dtype=float)
        if pred.size == yv.size:
            residual = yv - pred
            traces.append(series("fit", xv, pred))
    overlay_name = (overlay or "").strip()
    overlay_rms = None
    if overlay_name:
        from veyra.catalog import bind_model_kwargs
        from veyra.physics import run_named

        kwargs = bind_model_kwargs(overlay_name, overlay_params or {})
        try:
            model = run_named(overlay_name, **kwargs)
        except TypeError:
            model = run_named(overlay_name)
        extracted = _overlay_series(model)
        if extracted is None:
            checks.append(
                Check("overlay evaluated at measured x", False, f"{overlay_name} has no plot series")
            )
        else:
            mx, my = extracted
            in_range = float(xv.min()) >= float(mx.min()) - 1e-9 and float(xv.max()) <= float(mx.max()) + 1e-9
            y_over = np.interp(xv, mx, my)
            overlay_rms = float(np.sqrt(np.mean((yv - y_over) ** 2)))
            if residual is None:
                residual = yv - y_over
            traces.append(series(overlay_name, mx, my))
            traces.append(series("overlay at x", xv, y_over))
            checks.append(
                Check(
                    "overlay evaluated at measured x",
                    True,
                    f"{overlay_name} source n={int(mx.size)} (not the downsampled plot)",
                )
            )
            checks.append(
                Check(
                    "measured x inside model range",
                    in_range,
                    f"x∈[{float(xv.min()):.4g}, {float(xv.max()):.4g}]",
                )
            )
            metrics.append(Metric("overlay RMSE", overlay_rms, y_unit))
            scale = max(float(np.ptp(yv)), 1e-12)
            metrics.append(Metric("overlay residual / span", overlay_rms / scale))
    if residual is not None:
        traces_resid = [series("residual", xv, residual)]
        metrics.append(Metric("residual RMS", float(np.sqrt(np.mean(residual**2))), y_unit))
        metrics.append(Metric("residual max", float(np.max(np.abs(residual))), y_unit))
    else:
        traces_resid = []
        metrics.append(Metric("y mean", float(yv.mean()), y_unit))
        metrics.append(Metric("y std", float(yv.std(ddof=1) if n > 1 else 0.0), y_unit))
    x_label = f"{x_name}" + (f" ({x_unit})" if x_unit else "")
    y_label = f"{y_name}" + (f" ({y_unit})" if y_unit else "")
    solver = "measurement"
    if fit_name and fit_name not in {"none", "off", "false"}:
        solver += f" + {fit_name} least squares"
    if overlay_name:
        solver += f" + overlay {overlay_name}"
    ok = all(check.passed for check in checks)
    return VeyraResult(
        ok=ok,
        kind="measurement",
        title="Measurement",
        checks=checks,
        metrics=metrics,
        inputs={
            "path": str(source) if source else "",
            "x": x_name,
            "y": y_name,
            "x_unit": x_unit,
            "y_unit": y_unit,
            "fit": fit_name,
            "overlay": overlay_name,
            **(overlay_params or {}),
        },
        details={
            "columns": columns,
            "n": n,
            "residuals": residual.tolist() if residual is not None else [],
            "plot": make_plot(
                "residuals" if traces_resid else "series",
                x_label,
                y_label,
                traces,
                secondary=make_plot("series", x_label, f"residual ({y_unit})" if y_unit else "residual", traces_resid)
                if traces_resid
                else None,
            ),
        },
        solver=solver,
    )
