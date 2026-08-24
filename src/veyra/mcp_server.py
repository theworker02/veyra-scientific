"""Veyra MCP server — deterministic scientific tools for Cursor Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from veyra.agent import run_agent_experiment
from veyra.core import Check, VeyraResult, render_instrument
from veyra.dsl import parse_veyra, run_experiment, run_path, run_suite
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
from veyra.mathematics import (
    differentiate,
    find_roots,
    fourier_transform,
    integrate_expression,
    math_console,
    matrix_analyze,
    optimize_function,
    simplify_expression,
    solve_equation,
    solve_linear_system,
    solve_ode,
)
from veyra.measure import analyze_measurement
from veyra.physics import (
    analyze_force_system,
    analyze_mechanics,
    calculate_field,
    simulate_atwood,
    simulate_bernoulli,
    simulate_circular,
    simulate_collision,
    simulate_cooling,
    simulate_decay,
    simulate_doppler,
    simulate_escape,
    simulate_freefall,
    simulate_heat,
    simulate_kepler,
    simulate_lc,
    simulate_lens,
    simulate_motion,
    simulate_optics,
    simulate_orbit,
    simulate_oscillator,
    simulate_pendulum,
    simulate_range_table,
    simulate_rc,
    simulate_rl,
    simulate_shm,
    simulate_thermodynamics,
    simulate_wave,
    solve_circuit,
)
from veyra.reproduce import history_result, store
from veyra.runtime import (
    build_graph,
    is_declarative_experiment,
    parse_experiment_spec,
    run_spec,
    validate_source,
)
from veyra.stats import (
    compare_results,
    fit_model,
    monte_carlo,
    numerical_stability,
    probability_check,
    propagate_uncertainty,
    sensitivity_analysis,
)
from veyra.units import analyze_expression_dimensions, convert_quantity, validate_units
from veyra.verify import verify_model

mcp = FastMCP("veyra-scientific")


def _out(result: VeyraResult) -> str:
    store(result)
    return render_instrument(result) + "\n\n" + json.dumps(result.to_dict(), default=str)


@mcp.tool(name="solve_equation")
def solve_equation_tool(equation: str, variable: str = "x") -> str:
    """Solve an algebraic equation. Pass equations like x^3 - 6x^2 + 11x - 6 = 0."""
    return _out(solve_equation(equation, variable))


@mcp.tool()
def simplify_expression_tool(expression: str) -> str:
    """Symbolically simplify, expand, and factor a mathematical expression."""
    return _out(simplify_expression(expression))


@mcp.tool()
def differentiate_tool(expression: str, variable: str = "x", order: int = 1) -> str:
    """Compute a symbolic derivative."""
    return _out(differentiate(expression, variable, order))


@mcp.tool()
def integrate_tool(
    expression: str,
    variable: str = "x",
    lower: float | None = None,
    upper: float | None = None,
) -> str:
    """Compute a symbolic or definite integral."""
    return _out(integrate_expression(expression, variable, lower, upper))


@mcp.tool()
def find_roots_tool(expression: str, variable: str = "x", guess: float = 0.0) -> str:
    """Find symbolic and numeric roots of an expression."""
    return _out(find_roots(expression, variable, guess))


@mcp.tool()
def solve_linear_system_tool(matrix: list[list[float]], rhs: list[float]) -> str:
    """Solve Ax = b and report residual plus condition number."""
    return _out(solve_linear_system(matrix, rhs))


@mcp.tool()
def matrix_analyze_tool(matrix: list[list[float]]) -> str:
    """Analyze a matrix: rank, determinant, eigenvalues, positive-definiteness."""
    return _out(matrix_analyze(matrix))


@mcp.tool()
def optimize_function_tool(
    expression: str,
    variable: str = "x",
    lower: float = -10.0,
    upper: float = 10.0,
) -> str:
    """Numerically minimize a scalar function on a bounded interval."""
    return _out(optimize_function(expression, variable, lower=lower, upper=upper))


@mcp.tool()
def solve_ode_tool(
    expressions: list[str],
    variables: list[str],
    t0: float = 0.0,
    t1: float = 1.0,
    y0: list[float] | None = None,
    params: dict[str, float] | None = None,
) -> str:
    """Integrate a first-order ODE system with RK45."""
    return _out(solve_ode(expressions, variables, (t0, t1), y0, params))


@mcp.tool()
def fourier_tool(values: list[float], sample_rate: float = 1.0) -> str:
    """Compute an FFT and the peak frequency."""
    return _out(fourier_transform(values, sample_rate))


@mcp.tool()
def simulate_motion_tool(
    velocity: float = 38.0,
    angle_deg: float = 47.0,
    trials: int = 1,
    velocity_uncertainty: float = 0.0,
    drag_coefficient: float = 0.0,
    mass: float = 1.0,
    area: float = 0.01,
    seed: int = 0,
) -> str:
    """Simulate a 2D projectile, optionally with quadratic drag and Monte Carlo trials."""
    return _out(
        simulate_motion(
            velocity=velocity,
            angle_deg=angle_deg,
            trials=trials,
            velocity_uncertainty=velocity_uncertainty,
            drag_coefficient=drag_coefficient,
            mass=mass,
            area=area,
            seed=seed,
        )
    )


@mcp.tool()
def simulate_orbit_tool(
    altitude_m: float = 400000.0,
    duration_s: float = 259200.0,
    eccentricity: float = 0.0,
) -> str:
    """Propagate a two-body Earth orbit and test stability / conservation."""
    return _out(simulate_orbit(altitude_m=altitude_m, duration_s=duration_s, eccentricity=eccentricity))


@mcp.tool()
def simulate_collision_tool(
    m1: float = 2.0,
    m2: float = 1.0,
    u1: float = 3.0,
    u2: float = -1.0,
    restitution: float = 1.0,
) -> str:
    """Solve a 1D collision and check momentum / energy."""
    return _out(simulate_collision(m1, m2, u1, u2, restitution))


@mcp.tool()
def analyze_force_system_tool(forces: list[list[float]], torques: list[float] | None = None) -> str:
    """Sum a force system and test static equilibrium."""
    return _out(analyze_force_system(forces, torques))


@mcp.tool()
def simulate_thermodynamics_tool(
    process: str = "ideal_gas",
    pressure: float = 101325.0,
    volume: float = 0.001,
    temperature: float = 298.15,
    moles: float = 0.0403,
    heat: float = 0.0,
    work: float = 0.0,
) -> str:
    """Evaluate ideal-gas or first-law thermodynamics."""
    return _out(
        simulate_thermodynamics(process, pressure, volume, temperature, moles, heat, work)
    )


@mcp.tool()
def simulate_wave_tool(
    amplitude: float = 1.0,
    wavelength: float = 2.0,
    frequency: float = 4.0,
    x: float = 0.25,
    t: float = 0.1,
) -> str:
    """Evaluate a traveling wave y = A sin(kx − ωt)."""
    return _out(simulate_wave(amplitude, wavelength, frequency, x, t))


@mcp.tool()
def calculate_field_tool(
    kind: str = "gravity",
    source: float = 1.0,
    point: list[float] | None = None,
) -> str:
    """Point-source gravitational or electric field."""
    return _out(calculate_field(kind, source, point))


@mcp.tool()
def solve_circuit_tool(resistances: list[float], voltages: list[float]) -> str:
    """Solve a DC series circuit with KVL and Ohm's law."""
    return _out(solve_circuit(resistances, voltages))


@mcp.tool()
def simulate_optics_tool(n1: float = 1.0, n2: float = 1.5, angle_deg: float = 30.0) -> str:
    """Apply Snell's law and optional thin-lens imaging."""
    return _out(simulate_optics(n1, n2, angle_deg))


@mcp.tool()
def analyze_mechanics_tool(
    mass: float = 1.0,
    velocity: float = 0.0,
    height: float = 0.0,
) -> str:
    """Account kinetic, gravitational, and spring energy."""
    return _out(analyze_mechanics(mass, velocity, height))


@mcp.tool()
def validate_units_tool(assignments: dict[str, str], expected: dict[str, str] | None = None) -> str:
    """Parse measured values and validate units / dimensions."""
    return _out(validate_units(assignments, expected))


@mcp.tool()
def dimension_analysis_tool(expression: str, symbol_units: dict[str, str]) -> str:
    """Determine the dimension of an expression from symbol units."""
    return _out(analyze_expression_dimensions(symbol_units, expression))


@mcp.tool()
def propagate_uncertainty_tool(
    expression: str,
    variables: dict[str, list[float]],
    trials: int = 20000,
    seed: int = 0,
) -> str:
    """Monte Carlo uncertainty propagation. variables maps name -> [mean, std]."""
    parsed = {name: (vals[0], vals[1]) for name, vals in variables.items()}
    return _out(propagate_uncertainty(expression, parsed, trials, seed))


@mcp.tool(name="run_experiment")
def run_experiment_tool(source: str) -> str:
    """Parse and run a .veyra experiment from source text."""
    if is_declarative_experiment(source):
        try:
            return _out(run_spec(parse_experiment_spec(source)))
        except Exception as error:
            return _out(
                VeyraResult(
                    ok=False,
                    kind="experiment validation",
                    title="Veyra experiment",
                    checks=[Check("schema validated", False, str(error))],
                )
            )
    experiments = parse_veyra(source)
    if not experiments:
        return _out(VeyraResult(ok=False, kind="dsl", title="No experiment"))
    return _out(run_experiment(experiments[0]))


@mcp.tool(name="agent_run_experiment")
def agent_run_experiment_tool(
    request: str,
    model: str,
    parameters: dict[str, Any] | None = None,
    assertions: list[str] | None = None,
) -> str:
    """Run a user-requested catalog experiment for Cursor Agent with validated numeric inputs.

    Use only after the user asks for a calculation or experiment. Parameters use
    the catalog's documented units; results include the user request, bound
    inputs, explicit assertions, diagnostics, and a reproducible run id.
    """
    return _out(run_agent_experiment(request, model, parameters, assertions))


@mcp.tool(name="validate_experiment")
def validate_experiment_tool(source: str) -> str:
    """Validate a declarative Veyra experiment before it consumes compute."""
    return _out(validate_source(source))


@mcp.tool(name="experiment_graph")
def experiment_graph_tool(source: str) -> str:
    """Return the dependency graph for a declarative Veyra experiment."""
    try:
        experiment = parse_experiment_spec(source)
        graph = build_graph(experiment).to_dict()
        return _out(
            VeyraResult(
                ok=True,
                kind="experiment graph",
                title=experiment.name,
                checks=[Check("graph constructed", True, f"{len(graph['nodes'])} nodes")],
                details={"graph": graph},
                solver="veyra runtime",
            )
        )
    except Exception as error:
        return _out(
            VeyraResult(
                ok=False,
                kind="experiment graph",
                title="Veyra experiment",
                checks=[Check("graph constructed", False, str(error))],
                solver="veyra runtime",
            )
        )


@mcp.tool(name="run_experiment_file")
def run_experiment_file_tool(path: str) -> str:
    """Run a .veyra file from disk."""
    results = run_path(path)
    if not results:
        return _out(VeyraResult(ok=False, kind="dsl", title="No experiment"))
    return _out(results[0])


@mcp.tool(name="run_all_experiments")
def run_all_experiments_tool(root: str = ".") -> str:
    """Run every .veyra scientific test in a directory tree."""
    return _out(run_suite(root))


@mcp.tool()
def compare_results_tool(a: float, b: float, tolerance: float = 1e-6) -> str:
    """Compare two numeric results within a relative tolerance."""
    return _out(compare_results(a, b, tolerance))


@mcp.tool()
def numerical_stability_tool(
    matrix: list[list[float]] | None = None,
    values: list[float] | None = None,
) -> str:
    """Check condition numbers and finiteness."""
    return _out(numerical_stability(matrix, values))


@mcp.tool()
def fit_model_tool(x: list[float], y: list[float], model: str = "linear") -> str:
    """Fit linear, quadratic, or exponential models."""
    return _out(fit_model(x, y, model))


@mcp.tool()
def monte_carlo_tool(sampler: str = "normal", n: int = 10000, seed: int = 0) -> str:
    """Draw Monte Carlo samples, or estimate π with sampler='pi'."""
    return _out(monte_carlo(sampler, n, seed))


@mcp.tool()
def sensitivity_analysis_tool(expression: str, variables: dict[str, float]) -> str:
    """Finite-difference sensitivity and elasticity of an expression."""
    return _out(sensitivity_analysis(expression, variables))


@mcp.tool()
def generate_report_tool(title: str, notes: str = "") -> str:
    """Create a structured scientific report stub from the latest computed facts only."""
    result = VeyraResult(
        ok=True,
        kind="report",
        title=title,
        checks=[],
        details={"notes": notes},
        solver="veyra report",
    )
    return _out(result)


@mcp.tool()
def geometry_measure_tool(kind: str, points: list[list[float]] | None = None, radius: float | None = None) -> str:
    """Measure distance, polygon area, circle area, sphere volume, or a triangle."""
    return _out(geometry_measure(kind, points, radius))


@mcp.tool()
def geometry_intersect_tool(shape_a: dict[str, Any], shape_b: dict[str, Any]) -> str:
    """Intersect AABBs, spheres, or 2D segments."""
    return _out(geometry_intersect(shape_a, shape_b))


@mcp.tool()
def geometry_transform_tool(
    points: list[list[float]],
    translate: list[float] | None = None,
    scale: float = 1.0,
    rotate_deg: float = 0.0,
) -> str:
    """Translate, scale, and rotate point sets."""
    return _out(geometry_transform(points, translate, scale, rotate_deg))


@mcp.tool()
def geometry_validate_tool(points: list[list[float]], kind: str = "polygon") -> str:
    """Validate polygon or mesh topology at a basic level."""
    return _out(geometry_validate(points, kind))


@mcp.tool()
def geometry_mesh_analysis_tool(vertices: list[list[float]], faces: list[list[int]]) -> str:
    """Compute mesh Euler characteristic."""
    return _out(geometry_mesh_analysis(vertices, faces))


@mcp.tool()
def geometry_nearest_tool(origin: list[float], points: list[list[float]]) -> str:
    """Nearest neighbor in Euclidean space."""
    return _out(geometry_nearest(origin, points))


@mcp.tool()
def geometry_construct_tool(kind: str = "regular_polygon", sides: int = 6, radius: float = 1.0) -> str:
    """Construct primitive geometry such as a regular polygon."""
    return _out(geometry_construct(kind, sides=sides, radius=radius))


@mcp.tool()
def geometry_sample_tool(kind: str = "disk", count: int = 16, radius: float = 1.0, seed: int = 0) -> str:
    """Sample points on a disk or sphere."""
    return _out(geometry_sample(kind, count, radius, seed))


@mcp.tool()
def probability_check_tool(values: list[float]) -> str:
    """Assert a discrete distribution is non-negative and sums to 1."""
    return _out(probability_check(values))


@mcp.tool(name="verify_model")
def verify_model_tool(path: str | None = None, source: str | None = None) -> str:
    """Run the Veyra Proof pipeline: syntax, dimensions, stability, conservation."""
    return _out(verify_model(source=source, path=path))


@mcp.tool(name="inspect_expression")
def inspect_expression_tool(expression: str) -> str:
    """Veyra Lens: recognize a scientific law and flag inconsistent forms."""
    return _out(inspect_expression(expression))


@mcp.tool(name="inspect_file")
def inspect_file_tool(path: str) -> str:
    """Scan a source file for scientifically inconsistent equations."""
    from pathlib import Path

    return _out(inspect_file_result(Path(path).read_text(encoding="utf-8"), path))


@mcp.tool(name="simulate_pendulum")
def simulate_pendulum_tool(length: float = 1.0, theta0: float = 0.2, duration: float = 8.0) -> str:
    """Integrate a nonlinear pendulum and test energy conservation."""
    return _out(simulate_pendulum(length=length, theta0=theta0, duration=duration))


@mcp.tool(name="catalog_models")
def catalog_models_tool() -> str:
    """List physics models installed in the Veyra engine, with parameter schemas."""
    from veyra.catalog import catalog_payload

    payload = catalog_payload()
    result = VeyraResult(
        ok=True,
        kind="catalog",
        title="Veyra model catalog",
        checks=[],
        metrics=[],
        details=payload,
        solver="veyra catalog",
    )
    return _out(result)


@mcp.tool(name="run_history")
def run_history_tool() -> str:
    """Return the laboratory notebook of fingerprinted runs."""
    return _out(history_result())


@mcp.tool(name="simulate_heat")
def simulate_heat_tool(
    length: float = 0.2,
    alpha: float = 1e-4,
    t_left: float = 373.15,
    t_right: float = 273.15,
    t_init: float = 293.15,
    duration: float = 30.0,
) -> str:
    """Integrate the 1D heat equation on a rod with Dirichlet boundaries."""
    return _out(
        simulate_heat(
            length=length,
            alpha=alpha,
            t_left=t_left,
            t_right=t_right,
            t_init=t_init,
            duration=duration,
        )
    )


@mcp.tool(name="simulate_rc")
def simulate_rc_tool(
    resistance: float = 1000.0,
    capacitance: float = 1e-6,
    v_source: float = 5.0,
    duration: float = 0.008,
) -> str:
    """Charge an RC circuit and compare RK45 against the closed-form exponential."""
    return _out(
        simulate_rc(
            resistance=resistance,
            capacitance=capacitance,
            v_source=v_source,
            duration=duration,
        )
    )


@mcp.tool(name="simulate_oscillator")
def simulate_oscillator_tool(
    mass: float = 1.0,
    stiffness: float = 16.0,
    damping: float = 0.4,
    duration: float = 12.0,
) -> str:
    """Integrate a viscously damped harmonic oscillator."""
    return _out(simulate_oscillator(mass=mass, stiffness=stiffness, damping=damping, duration=duration))


@mcp.tool(name="simulate_bernoulli")
def simulate_bernoulli_tool(
    density: float = 1000.0,
    v1: float = 2.0,
    v2: float = 4.0,
    h1: float = 3.0,
    h2: float = 1.0,
    p1: float = 101325.0,
) -> str:
    """Steady incompressible Bernoulli along a streamline."""
    return _out(simulate_bernoulli(density=density, v1=v1, v2=v2, h1=h1, h2=h2, p1=p1))


@mcp.tool(name="simulate_range_table")
def simulate_range_table_tool(velocity: float = 38.0, drag_coefficient: float = 0.0) -> str:
    """Sweep launch angle and report the ballistic range table."""
    return _out(simulate_range_table(velocity=velocity, drag_coefficient=drag_coefficient))


@mcp.tool(name="simulate_cooling")
def simulate_cooling_tool(t0: float = 363.15, t_env: float = 293.15, k: float = 0.05, duration: float = 120.0) -> str:
    """Newton's law of cooling, RK45 versus the closed-form exponential."""
    return _out(simulate_cooling(t0=t0, t_env=t_env, k=k, duration=duration))


@mcp.tool(name="simulate_decay")
def simulate_decay_tool(n0: float = 1000.0, half_life: float = 10.0, duration: float = 40.0) -> str:
    """Radioactive decay with a half-life identity check."""
    return _out(simulate_decay(n0=n0, half_life=half_life, duration=duration))


@mcp.tool(name="simulate_atwood")
def simulate_atwood_tool(m1: float = 1.2, m2: float = 1.0) -> str:
    """Atwood machine acceleration and tension from Newton's second law."""
    return _out(simulate_atwood(m1=m1, m2=m2))


@mcp.tool(name="simulate_rl")
def simulate_rl_tool(
    resistance: float = 10.0,
    inductance: float = 0.5,
    v_source: float = 12.0,
    duration: float = 0.4,
) -> str:
    """Series RL current rise, RK45 versus the closed-form exponential."""
    return _out(simulate_rl(resistance=resistance, inductance=inductance, v_source=v_source, duration=duration))


@mcp.tool(name="simulate_freefall")
def simulate_freefall_tool(y0: float = 80.0, v0: float = 0.0, duration: float = 4.0) -> str:
    """Vertical free fall, RK45 versus y = y0 + v0 t − ½ g t²."""
    return _out(simulate_freefall(y0=y0, v0=v0, duration=duration))


@mcp.tool(name="simulate_kepler")
def simulate_kepler_tool(altitude_m: float = 400_000.0) -> str:
    """Circular Kepler identity T²/a³ = 4π²/GM."""
    return _out(simulate_kepler(altitude_m=altitude_m))


@mcp.tool(name="simulate_lc")
def simulate_lc_tool(
    inductance: float = 0.5,
    capacitance: float = 2e-6,
    q0: float = 1e-6,
    duration: float = 0.02,
) -> str:
    """Undamped LC oscillator, RK45 versus q = Q0 cos(ωt)."""
    return _out(simulate_lc(inductance=inductance, capacitance=capacitance, q0=q0, duration=duration))


@mcp.tool(name="simulate_lens")
def simulate_lens_tool(focal_length: float = 0.05, object_distance: float = 0.12) -> str:
    """Thin-lens Gaussian identity 1/f = 1/do + 1/di."""
    return _out(simulate_lens(focal_length=focal_length, object_distance=object_distance))


@mcp.tool(name="simulate_escape")
def simulate_escape_tool(altitude_m: float = 0.0) -> str:
    """Escape speed √(2GM/r) and the circular identity v_esc / v_circ = √2."""
    return _out(simulate_escape(altitude_m=altitude_m))


@mcp.tool(name="simulate_shm")
def simulate_shm_tool(
    mass: float = 1.0,
    stiffness: float = 16.0,
    amplitude: float = 0.1,
    duration: float = 4.0,
) -> str:
    """Undamped simple harmonic motion, RK45 versus x = A cos(ωt)."""
    return _out(simulate_shm(mass=mass, stiffness=stiffness, amplitude=amplitude, duration=duration))


@mcp.tool(name="simulate_doppler")
def simulate_doppler_tool(
    frequency: float = 440.0,
    v_source: float = 20.0,
    v_observer: float = 0.0,
    speed_sound: float = 343.0,
) -> str:
    """Acoustic Doppler shift along the line of sight."""
    return _out(
        simulate_doppler(
            frequency=frequency,
            v_source=v_source,
            v_observer=v_observer,
            speed_sound=speed_sound,
        )
    )


@mcp.tool(name="simulate_circular")
def simulate_circular_tool(radius: float = 10.0, speed: float = 5.0) -> str:
    """Uniform circular motion: a = v²/r and T = 2πr/v."""
    return _out(simulate_circular(radius=radius, speed=speed))


@mcp.tool(name="init_experiment")
def init_experiment_tool(model: str = "projectile", path: str = "") -> str:
    """Write a .veyra experiment from a catalog model, or return the source if path is empty."""
    from pathlib import Path

    from veyra.catalog import scaffold_experiment

    try:
        text = scaffold_experiment(model)
    except ValueError as exc:
        return _out(
            VeyraResult(ok=False, kind="dsl", title="init", checks=[Check("known model", False, str(exc))])
        )
    if path:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return text


@mcp.tool(name="sweep_model")
def sweep_model_tool(
    model: str = "projectile",
    param: str = "velocity",
    start: float = 10.0,
    stop: float = 50.0,
    steps: int = 9,
) -> str:
    """Sweep one catalog parameter and report the first numeric metric."""
    from veyra.catalog import sweep_model

    return _out(sweep_model(model, param, start, stop, steps))


@mcp.tool(name="math_console")
def math_console_tool(expression: str, action: str = "auto", variable: str = "x") -> str:
    """Solve, simplify, differentiate, integrate, or evaluate an expression."""
    return _out(math_console(expression, action, variable))


@mcp.tool(name="convert_quantity")
def convert_quantity_tool(value: str, to_unit: str, from_unit: str = "") -> str:
    """Convert a measured quantity into another unit of the same dimension."""
    return _out(convert_quantity(value, to_unit, from_unit))


@mcp.tool(name="lab_status")
def lab_status_tool() -> str:
    """Report whether the local Veyra laboratory is running, and how to open it."""
    import urllib.request

    from veyra.server import lab_health

    payload = lab_health()
    payload["running"] = False
    payload["start"] = "start_laboratory or python -m veyra serve examples"
    payload["cli"] = "python -m veyra serve examples"
    payload["cursor"] = "Command Palette → Veyra: Open Laboratory"
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=0.8) as response:
            remote = json.loads(response.read().decode("utf-8"))
            payload["running"] = bool(remote.get("ok"))
            served = remote.get("veyra")
            if served and served != payload["veyra"]:
                payload["served"] = served
    except Exception:  # noqa: BLE001
        payload["running"] = False
    return json.dumps(payload, indent=2)


@mcp.tool(name="start_laboratory")
def start_laboratory_tool() -> str:
    """Start the HTTP Workbench if it is down. Returns the laboratory URL."""
    from veyra.server import ensure_running

    return json.dumps(ensure_running(), indent=2)


@mcp.tool(name="analyze_measurement")
def analyze_measurement_tool(
    csv: str = "",
    path: str = "",
    x: str = "",
    y: str = "",
    x_unit: str = "",
    y_unit: str = "",
    fit: str = "linear",
    overlay: str = "",
    overlay_params: str = "",
) -> str:
    """Load measured CSV data, fit a curve, and/or overlay a catalog model. Reports residual and units."""
    extra = json.loads(overlay_params) if overlay_params.strip() else {}
    return _out(
        analyze_measurement(
            csv_text=csv,
            path=path or None,
            x=x,
            y=y,
            x_unit=x_unit,
            y_unit=y_unit,
            fit=fit,
            overlay=overlay,
            overlay_params=extra if isinstance(extra, dict) else {},
            workspace=Path.cwd(),
        )
    )


@mcp.tool(name="methods_protocol")
def methods_protocol_tool(run_id: str = "latest") -> str:
    """Return a methods paragraph for a fingerprinted laboratory run."""
    from veyra.protocol import methods_from_record
    from veyra.reproduce import load

    return methods_from_record(load(run_id))


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
