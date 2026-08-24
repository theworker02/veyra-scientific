"""Veyra CLI — the internal execution interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import typer
from rich.console import Console

from veyra import __version__
from veyra.catalog import catalog_payload
from veyra.core import Check, VeyraResult, json_default, render_instrument
from veyra.dsl import run_path, run_suite
from veyra.geometry import (
    geometry_construct,
    geometry_intersect,
    geometry_measure,
    geometry_mesh_analysis,
    geometry_nearest,
    geometry_sample,
    geometry_transform,
    geometry_validate,
)
from veyra.lens import inspect_expression, inspect_file_result
from veyra.mathematics import math_console
from veyra.physics import run_named, simulate_motion
from veyra.protocol import methods_from_record, methods_paragraph
from veyra.reproduce import compare_records, history_result, load, reproduce, store
from veyra.runtime import build_graph, load_experiment_spec, validate_source
from veyra.units import convert_quantity, validate_units
from veyra.verify import verify_model
from veyra.workbench import build_session

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Veyra Scientific — don't guess the science. Run it.",
)
console = Console(highlight=False)
err = Console(stderr=True)


def emit(result: VeyraResult, as_json: bool = False, persist: bool = True) -> None:
    if persist:
        store(result)
    if as_json:
        # Results may contain NumPy scalar diagnostics. Serialize through the
        # shared encoder so machine output is as robust as stored artifacts.
        console.print_json(json=json.dumps(result.to_dict(), default=json_default))
    else:
        console.print(render_instrument(result))
    raise typer.Exit(0 if result.all_checks_passed() else 1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        console.print(f"veyra {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def test(
    path: Path = typer.Argument(Path("."), help="Directory or file of .veyra experiments."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run every Veyra experiment in a repository."""
    if path.is_file():
        results = run_path(path)
        from veyra.core import Metric

        passed = sum(1 for item in results if item.all_checks_passed())
        result = VeyraResult(
            ok=passed == len(results),
            kind="scientific test suite",
            title="Veyra Scientific Test Suite",
            checks=[Check(item.title, item.all_checks_passed()) for item in results],
            metrics=[Metric("experiments", len(results)), Metric("passed", passed)],
        )
        emit(result, json_out)
    emit(run_suite(path), json_out)


@app.command("run")
def run_cmd(
    target: Path = typer.Argument(..., help="Path to a .veyra experiment."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run a single .veyra experiment."""
    results = run_path(target)
    if not results:
        raise typer.BadParameter("no experiments found")
    emit(results[0], json_out)


@app.command()
def validate(
    target: Path = typer.Argument(..., help="Path to a declarative .veyra experiment."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Validate an experiment schema, units, engine, and solver tolerances."""
    emit(validate_source(target.read_text(encoding="utf-8"), str(target)), json_out, persist=False)


@app.command()
def graph(
    target: Path = typer.Argument(..., help="Path to a declarative .veyra experiment."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect the real execution graph before running an experiment."""
    try:
        experiment = load_experiment_spec(target)
        payload = build_graph(experiment).to_dict()
        result = VeyraResult(
            ok=True,
            kind="experiment graph",
            title=experiment.name,
            checks=[Check("graph constructed", True, f"{len(payload['nodes'])} nodes")],
            details={"graph": payload},
            inputs={"source": str(target)},
            solver="veyra runtime",
        )
    except Exception as error:  # show the schema diagnostic rather than a traceback
        result = VeyraResult(
            ok=False,
            kind="experiment graph",
            title=target.stem,
            checks=[Check("graph constructed", False, str(error))],
            inputs={"source": str(target)},
            solver="veyra runtime",
        )
    emit(result, json_out, persist=False)


@app.command()
def math(
    expression: str = typer.Argument(..., help="Equation or expression."),
    action: str = typer.Option(
        "auto",
        "--action",
        help="auto|simplify|solve|differentiate|integrate|roots|optimize",
    ),
    variable: str = typer.Option("x"),
    lower: Optional[float] = typer.Option(None),
    upper: Optional[float] = typer.Option(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Symbolic and numerical mathematics."""
    emit(
        math_console(expression, action, variable, lower, upper),
        json_out,
    )


@app.command()
def verify(
    target: Path = typer.Argument(..., help="Source file to verify."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run the Veyra Proof pipeline on a model file."""
    emit(verify_model(path=str(target)), json_out)


@app.command()
def physics(
    model: str = typer.Argument("projectile", help="Physics model name."),
    velocity: float = typer.Option(38.0),
    angle: float = typer.Option(47.0),
    trials: int = typer.Option(1),
    drag: float = typer.Option(0.0),
    params: Optional[str] = typer.Option(None, "--params", help="JSON object of model kwargs."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run a named physics model."""
    extra = json.loads(params) if params else {}
    if model in {"projectile", "motion"} and not extra:
        emit(
            simulate_motion(velocity=velocity, angle_deg=angle, trials=trials, drag_coefficient=drag),
            json_out,
        )
    from veyra.catalog import bind_model_kwargs

    kwargs = bind_model_kwargs(model, extra)
    if model in {"projectile", "motion"}:
        kwargs.setdefault("velocity", velocity)
        kwargs.setdefault("angle_deg", angle)
        kwargs.setdefault("trials", trials)
        kwargs.setdefault("drag_coefficient", drag)
    emit(run_named(model, **kwargs), json_out)


@app.command()
def geometry(
    action: str = typer.Argument("measure"),
    kind: str = typer.Option("distance"),
    json_payload: Optional[str] = typer.Option(None, "--data"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect or measure geometry."""
    data = json.loads(json_payload) if json_payload else {}
    if action == "intersect":
        emit(geometry_intersect(data["a"], data["b"]), json_out)
    if action == "transform":
        emit(geometry_transform(**data), json_out)
    if action == "validate":
        emit(geometry_validate(**data), json_out)
    if action == "nearest":
        emit(geometry_nearest(**data), json_out)
    if action == "construct":
        emit(geometry_construct(kind, **data), json_out)
    if action == "sample":
        emit(geometry_sample(kind, **data), json_out)
    if action == "mesh":
        emit(geometry_mesh_analysis(**data), json_out)
    emit(geometry_measure(kind, **data), json_out)


@app.command()
def lens(
    expression: Optional[str] = typer.Argument(None),
    file: Optional[Path] = typer.Option(None, "--file", help="Inspect a source file."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Recognize scientific meaning in an expression or file."""
    if file:
        emit(inspect_file_result(file.read_text(encoding="utf-8"), str(file)), json_out)
    if not expression:
        raise typer.BadParameter("provide an expression or --file")
    emit(inspect_expression(expression), json_out)


@app.command()
def inspect(
    target: Path = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect every scientific expression in a source file."""
    emit(inspect_file_result(target.read_text(encoding="utf-8"), str(target)), json_out)


@app.command()
def units(
    assignments: list[str] = typer.Argument(..., help="name=value unit pairs."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Validate units and dimensions."""
    parsed = {}
    for item in assignments:
        name, value = item.split("=", 1)
        parsed[name] = value
    emit(validate_units(parsed), json_out)


@app.command("reproduce")
def reproduce_cmd(
    run_id: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Recreate a previous run from its fingerprint."""
    emit(reproduce(run_id), json_out)


@app.command()
def workbench(
    target: Optional[Path] = typer.Argument(None),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765),
) -> None:
    """Open the laboratory Workbench for an experiment or a suite."""
    results, dest = build_session(target)
    console.print(render_instrument(results[0]))
    if len(results) > 1:
        console.print(f"\n{len(results)} experiments in session")
    console.print(f"Workbench  {dest.resolve()}")
    if not open_browser:
        return
    from veyra.server import serve_forever, workbench_dist

    url = f"http://{host}:{port}/"
    console.print(f"Laboratory {url}")
    if workbench_dist():
        console.print("Serving React Workbench")
    else:
        console.print("React dist missing — serving journal HTML fallback")
    typer.launch(url)
    serve_forever(host, port, Path.cwd(), target)


@app.command()
def serve(
    target: Optional[Path] = typer.Argument(None),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765),
    open_browser: bool = typer.Option(False, "--open/--no-open"),
) -> None:
    """Start the local laboratory HTTP API and Workbench."""
    results, dest = build_session(target)
    from veyra.server import serve_forever, workbench_dist

    url = f"http://{host}:{port}/"
    console.print(render_instrument(results[0]))
    console.print(f"\nSession     {dest.parent / 'session.json'}")
    console.print(f"Laboratory  {url}")
    console.print(f"Surface     {'React Workbench' if workbench_dist() else 'HTML fallback'}")
    if open_browser:
        typer.launch(url)
    serve_forever(host, port, Path.cwd(), target)


@app.command()
def history(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show the laboratory notebook of fingerprinted runs."""
    emit(history_result(), json_out, persist=False)


@app.command()
def catalog(json_out: bool = typer.Option(False, "--json")) -> None:
    """List installed scientific models."""
    payload = catalog_payload()
    if json_out:
        console.print_json(data=payload)
        return
    console.print(f"Veyra {payload['veyra']}  {payload['count']} models\n")
    current = ""
    for entry in payload["entries"]:
        if entry["group"] != current:
            current = entry["group"]
            console.print(f"{current}")
        console.print(f"  {entry['id']:<14} {entry['title']}")
        console.print(f"                 {entry['summary']}")


@app.command("init")
def init_cmd(
    model: str = typer.Argument("projectile", help="Catalog model id."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Destination .veyra path."),
) -> None:
    """Write a runnable .veyra experiment from a catalog model."""
    from veyra.catalog import lookup_entry, scaffold_experiment

    entry = lookup_entry(model)
    if entry is None:
        raise typer.BadParameter(f"unknown model '{model}'")
    dest = out or Path(f"{entry['id']}.veyra")
    dest.write_text(scaffold_experiment(model), encoding="utf-8")
    console.print(f"Wrote {dest}")


@app.command()
def sweep(
    model: str = typer.Argument("projectile"),
    param: str = typer.Option("velocity", "--param"),
    start: float = typer.Option(10.0, "--start"),
    stop: float = typer.Option(50.0, "--stop"),
    steps: int = typer.Option(9, "--steps"),
    params: Optional[str] = typer.Option(None, "--params"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Sweep one catalog parameter and plot the first numeric metric."""
    from veyra.catalog import sweep_model

    extra = json.loads(params) if params else {}
    emit(sweep_model(model, param, start, stop, steps, extra), json_out)


@app.command()
def protocol(
    run_id: Optional[str] = typer.Argument(None),
    html: bool = typer.Option(False, "--html", help="Write a one-page methods HTML artifact."),
    out: Optional[Path] = typer.Option(None, "--out", "-o"),
) -> None:
    """Print a methods paragraph for a fingerprinted run, or a one-page HTML artifact."""
    from veyra.protocol import methods_page

    if run_id:
        record = load(run_id)
        if html:
            page = methods_page(record)
            dest = out or Path(f"veyra-methods-{run_id}.html")
            dest.write_text(page, encoding="utf-8")
            console.print(f"Wrote {dest}")
            return
        console.print(methods_from_record(record))
        return
    from veyra.workbench import collect_results

    results = collect_results()
    if html:
        page = methods_page(results[0].to_dict())
        dest = out or Path(f"veyra-methods-{results[0].run_id}.html")
        dest.write_text(page, encoding="utf-8")
        console.print(f"Wrote {dest}")
        return
    console.print(methods_paragraph(results[0]))


@app.command()
def measure(
    path: Path = typer.Argument(..., help="CSV of measured x, y columns."),
    x: str = typer.Option("", "--x", help="Independent column name."),
    y: str = typer.Option("", "--y", help="Dependent column name."),
    x_unit: str = typer.Option("", "--x-unit"),
    y_unit: str = typer.Option("", "--y-unit"),
    fit: str = typer.Option("linear", "--fit", help="linear, quadratic, exponential, or none."),
    overlay: str = typer.Option("", "--overlay", help="Catalog model to overlay."),
    params: Optional[str] = typer.Option(None, "--params"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Load a CSV, fit and/or overlay a catalog model, report residual and units."""
    from veyra.measure import analyze_measurement

    extra = json.loads(params) if params else {}
    emit(
        analyze_measurement(
            path=path,
            x=x,
            y=y,
            x_unit=x_unit,
            y_unit=y_unit,
            fit=fit,
            overlay=overlay,
            overlay_params=extra,
        ),
        json_out,
    )


@app.command("install")
def install_cmd(
    dev: bool = typer.Option(True, "--dev/--no-dev", help="Include pytest and ruff."),
) -> None:
    """Install the laboratory kernel and the Veyra Workbench extension from this folder."""
    import importlib.util

    root = _workspace_root()
    console.print("Installing the Veyra laboratory kernel…")
    extra = ".[dev]" if dev else "."
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", extra],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    spec = importlib.util.spec_from_file_location(
        "veyra_hooks_bootstrap",
        root / "hooks" / "bootstrap.py",
    )
    if spec is None or spec.loader is None:
        console.print("Installed kernel. Workbench extension installer missing.")
        raise typer.Exit(0)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    status = module.install_extension()
    console.print(f"Workbench extension  {status}")
    console.print("MCP start_laboratory or Command Palette → Veyra: Open Laboratory")
    raise typer.Exit(0)


def _workspace_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file() and "veyra-scientific" in pyproject.read_text(encoding="utf-8"):
            return candidate
    raise typer.BadParameter("Open the Veyra Scientific folder first.")


@app.command("convert")
def convert_cmd(
    value: str = typer.Argument(..., help="Magnitude, or a measured string like '38 m/s'."),
    to_unit: str = typer.Option(..., "--to", help="Target unit."),
    from_unit: str = typer.Option("", "--from", help="Source unit if value is bare."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Convert a quantity into another unit of the same dimension."""
    emit(convert_quantity(value, to_unit, from_unit), json_out, persist=False)


@app.command("diff")
def diff_cmd(
    first: str = typer.Argument(...),
    second: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Compare two fingerprinted runs."""
    emit(compare_records(load(first), load(second)), json_out, persist=False)


@app.command()
def doctor() -> None:
    """Check the local scientific runtime and Cursor laboratory."""
    import importlib
    import platform
    import shutil
    import urllib.request

    from veyra.catalog import catalog_payload
    from veyra.server import workbench_dist

    packages = ["numpy", "scipy", "sympy", "pint", "mpmath", "matplotlib"]
    missing = []
    for name in packages:
        try:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", "")
            console.print(f"[+] {name:<12} {version}")
        except ImportError:
            missing.append(name)
            console.print(f"[x] {name}")
    console.print(f"\nveyra          {__version__}")
    console.print(f"models         {catalog_payload()['count']}")
    console.print(f"python         {platform.python_version()}")
    on_path = shutil.which("veyra")
    console.print(f"executable     {on_path or 'python -m veyra'}")
    dist = workbench_dist()
    console.print(f"workbench      {dist if dist else 'missing — npm run build in workbench/'}")
    up = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=0.6) as response:
            up = 200 <= response.status < 300
    except Exception:  # noqa: BLE001
        up = False
    console.print(f"laboratory     {'up  http://127.0.0.1:8765/' if up else 'down  MCP start_laboratory or python -m veyra serve examples'}")
    console.print("cursor         Command Palette → Veyra: Open Laboratory")
    console.print("first run      python hooks/bootstrap.py")
    if missing:
        console.print("\nThe laboratory kernel is incomplete.")
        console.print("Cursor: Command Palette → Veyra: Doctor")
        console.print("Terminal: python hooks/bootstrap.py --dev")
    raise typer.Exit(1 if missing else 0)


@app.command()
def bench(
    n: int = typer.Option(200_000, help="Monte Carlo samples."),
) -> None:
    """Benchmark the numerical kernel."""
    import time

    import numpy as np

    start = time.perf_counter()
    rng = np.random.default_rng(0)
    x = rng.normal(size=n)
    _ = float(x.mean())
    elapsed = time.perf_counter() - start
    console.print(f"numpy mean  {n} samples  {elapsed * 1000:.2f} ms")
    start = time.perf_counter()
    simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.1, trials=min(n, 4000))
    elapsed = time.perf_counter() - start
    console.print(f"projectile  {min(n, 4000)} trials   {elapsed * 1000:.2f} ms")


@app.command()
def mcp() -> None:
    """Start the Veyra MCP server on stdio."""
    from veyra.mcp_server import run

    run()
