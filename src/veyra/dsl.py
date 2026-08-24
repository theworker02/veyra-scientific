"""Parser and runner for *.veyra scientific test cases."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veyra.core import Check, Metric, VeyraResult
from veyra.physics import (
    fluid_pressure,
    material_stress,
    simulate_bernoulli,
    simulate_collision,
    simulate_motion,
    simulate_orbit,
    simulate_oscillator,
    simulate_pendulum,
    simulate_thermodynamics,
)
from veyra.stats import fit_model, probability_check
from veyra.units import parse_measured

BLOCK_RE = re.compile(r"(?P<name>[A-Za-z_][\w-]*)\s*(?P<body>\{)?")
ASSIGN_RE = re.compile(
    r"^(?P<key>[A-Za-z_][\w]*)\s*=\s*(?P<value>.+?)\s*$"
)
BARE_RE = re.compile(r"^(?P<key>[A-Za-z_][\w]*)\s+(?P<value>.+?)\s*$")


@dataclass
class Experiment:
    name: str
    model: str = "custom"
    constants: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)
    equations: list[str] = field(default_factory=list)
    asserts: list[str] = field(default_factory=list)
    simulate: dict[str, str] = field(default_factory=dict)
    source: str = ""


def parse_veyra(text: str, source: str = "") -> list[Experiment]:
    experiments: list[Experiment] = []
    current: Experiment | None = None
    block: str | None = None
    depth = 0
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("experiment "):
            name = line[len("experiment ") :].split("{", 1)[0].strip()
            current = Experiment(name=name, source=source)
            experiments.append(current)
            depth += line.count("{") - line.count("}")
            continue
        if current is None:
            continue
        opens, closes = line.count("{"), line.count("}")
        header = line.split("{", 1)[0].strip()
        if opens and header in {"constants", "inputs", "equation", "assert", "simulate"}:
            block = header
            depth += opens - closes
            if closes and opens == closes:
                block = None
            continue
        if header.startswith("model"):
            match = ASSIGN_RE.match(header) or BARE_RE.match(header)
            if match:
                current.model = match.group("value").strip()
            depth += opens - closes
            continue
        if closes and not line.strip().startswith("}"):
            _ingest(current, block, line.rstrip("}").strip())
            depth += opens - closes
            if depth <= 1:
                block = None
            continue
        if line == "}":
            depth += opens - closes
            if depth <= 1:
                block = None
            if depth <= 0:
                current = None
                block = None
            continue
        _ingest(current, block, line)
        depth += opens - closes
    return experiments


def parse_file(path: str | Path) -> list[Experiment]:
    file = Path(path)
    return parse_veyra(file.read_text(encoding="utf-8"), source=str(file))


def _ingest(experiment: Experiment, block: str | None, line: str) -> None:
    if not line or not block:
        return
    if block == "equation":
        experiment.equations.append(line.rstrip(";"))
        return
    if block == "assert":
        experiment.asserts.append(line.rstrip(";"))
        return
    match = ASSIGN_RE.match(line) or BARE_RE.match(line)
    if not match:
        return
    key, value = match.group("key"), match.group("value")
    if block == "constants":
        experiment.constants[key] = value
    elif block == "inputs":
        experiment.inputs[key] = value
    elif block == "simulate":
        experiment.simulate[key] = value


def run_experiment(experiment: Experiment) -> VeyraResult:
    env = _eval_env(experiment)
    model = experiment.model if experiment.model != "custom" else experiment.name
    result = _dispatch_model(model, experiment, env)
    assert_checks = _run_asserts(experiment, env, result)
    result.checks = assert_checks + result.checks
    result.ok = result.ok and all(c.passed for c in assert_checks)
    result.title = experiment.name.replace("-", " ").title()
    if experiment.source:
        result.inputs = {**result.inputs, "source": experiment.source}
    return result


def run_path(path: str | Path) -> list[VeyraResult]:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    # v4.7 adds a declarative YAML format while retaining every existing
    # brace-format scientific test as a compatible execution path.
    from veyra.runtime import is_declarative_experiment, run_spec_path

    if is_declarative_experiment(text):
        return [run_spec_path(file)]
    return [run_experiment(exp) for exp in parse_veyra(text, source=str(file))]


def run_suite(root: str | Path) -> VeyraResult:
    files = sorted(Path(root).rglob("*.veyra"))
    named: list[Check] = []
    results: list[VeyraResult] = []
    for file in files:
        experiments = parse_file(file)
        for exp in experiments:
            item = run_experiment(exp)
            results.append(item)
            label = file.name if len(experiments) == 1 else f"{file.name}:{exp.name}"
            named.append(Check(label, item.all_checks_passed()))
    passed = sum(1 for item in results if item.all_checks_passed())
    failed = len(results) - passed
    return VeyraResult(
        ok=failed == 0,
        kind="scientific test suite",
        title="Veyra Scientific Test Suite",
        checks=named,
        metrics=[
            Metric("experiments", len(results)),
            Metric("passed", passed),
            Metric("failed", failed),
        ],
        details={"results": [item.to_dict() for item in results], "files": [str(f) for f in files]},
        inputs={"root": str(root), "experiments": len(results)},
        solver="veyra suite",
    )


def _eval_env(experiment: Experiment) -> dict[str, Any]:
    env: dict[str, Any] = {
        "pi": math.pi,
        "e": math.e,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "deg": math.pi / 180,
    }
    for key, raw in {**experiment.constants, **experiment.inputs}.items():
        try:
            measured = parse_measured(raw)
            env[key] = measured.value
            env[f"{key}__unit"] = measured.unit
            env[f"{key}__unc"] = measured.uncertainty or 0.0
            if measured.unit in {"degree", "deg"}:
                env[key] = math.radians(measured.value)
        except Exception:  # noqa: BLE001
            env[key] = raw
    for equation in experiment.equations:
        if "=" not in equation:
            continue
        left, right = [part.strip() for part in equation.split("=", 1)]
        env[left] = eval(right, {"__builtins__": {}}, env)  # noqa: S307
    return env


def _run_asserts(experiment: Experiment, env: dict[str, Any], model: VeyraResult) -> list[Check]:
    checks: list[Check] = []
    for statement in experiment.asserts:
        if statement.startswith("energy_conserved"):
            found = next((item for item in model.checks if "energy" in item.name), None)
            if found:
                checks.append(Check(statement, found.passed, found.detail))
            else:
                checks.append(Check(statement, False, "model did not report an energy check"))
            continue
        try:
            ok = bool(eval(_normalize_assert(statement), {"__builtins__": {}}, env))  # noqa: S307
            checks.append(Check(statement, ok))
        except Exception as exc:  # noqa: BLE001
            checks.append(Check(statement, False, str(exc)))
    return checks


def _normalize_assert(statement: str) -> str:
    statement = statement.replace(" deg", " * deg")
    return statement


def _number(env: dict[str, Any], *names: str, default: float | None = None) -> float | None:
    for name in names:
        if name in env:
            return float(env[name])
    return default


def _dispatch_model(model: str, experiment: Experiment, env: dict[str, Any]) -> VeyraResult:
    sim = experiment.simulate
    duration = _parse_float(sim.get("duration"), 10.0)
    trials = int(_parse_float(sim.get("trials"), 1))
    if model in {"projectile", "motion", "projectile-dynamics"}:
        velocity = _number(env, "velocity", "v", "v0", default=10.0) or 10.0
        # angle stored in radians if unit was deg
        angle = env.get("angle", env.get("theta", math.radians(45)))
        if isinstance(angle, (int, float)) and angle > 2 * math.pi:
            angle = math.radians(angle)
        g = _number(env, "g", "gravity", default=9.80665) or 9.80665
        drag = _number(env, "drag", "cd", "drag_coefficient", default=0.0) or 0.0
        return simulate_motion(
            velocity=velocity,
            angle_deg=math.degrees(float(angle)),
            gravity=g,
            drag_coefficient=drag,
            trials=trials,
            velocity_uncertainty=float(env.get("velocity__unc") or 0.0),
            duration=duration,
        )
    if model in {"orbit", "orbital-decay", "orbital"}:
        return simulate_orbit(
            altitude_m=_number(env, "altitude", default=400_000) or 400_000,
            duration_s=duration if duration > 100 else duration * 3600,
            eccentricity=_number(env, "eccentricity", default=0.0) or 0.0,
        )
    if model in {"pendulum"}:
        return simulate_pendulum(
            length=_number(env, "length", "l", default=1.0) or 1.0,
            theta0=_number(env, "theta0", "theta", default=0.2) or 0.2,
            gravity=_number(env, "g", "gravity", default=9.80665) or 9.80665,
            duration=duration,
        )
    if model in {"fluid", "fluid-pressure"}:
        return fluid_pressure(
            density=_number(env, "density", default=1000) or 1000,
            depth=_number(env, "depth", default=10) or 10,
            p0=_number(env, "p0", default=101325) or 101325,
        )
    if model in {"stress", "stress-analysis", "material"}:
        return material_stress(
            force=_number(env, "force", default=1) or 1,
            area=_number(env, "area", default=1) or 1,
        )
    if model in {"collision"}:
        return simulate_collision(
            m1=_number(env, "m1", default=2) or 2,
            m2=_number(env, "m2", default=1) or 1,
            u1=_number(env, "u1", default=3) or 3,
            u2=_number(env, "u2", default=-1) or -1,
            restitution=_number(env, "e", "restitution", default=1) or 1,
        )
    if model in {"heat-transfer", "thermo", "heat"}:
        return simulate_thermodynamics(
            pressure=_number(env, "pressure", default=101325) or 101325,
            volume=_number(env, "volume", default=0.001) or 0.001,
            temperature=_number(env, "temperature", default=298.15) or 298.15,
            moles=_number(env, "moles", default=0.0403) or 0.0403,
        )
    if model in {"oscillator", "damped"}:
        return simulate_oscillator(
            mass=_number(env, "mass", "m", default=1.0) or 1.0,
            stiffness=_number(env, "stiffness", "k", default=16.0) or 16.0,
            damping=_number(env, "damping", "c", default=0.4) or 0.4,
            x0=_number(env, "x0", default=1.0) or 1.0,
            duration=duration,
        )
    if model in {"diffusion", "heat1d", "heat-diffusion"}:
        from veyra.physics import simulate_heat

        return simulate_heat(
            length=_number(env, "length", "l", default=0.2) or 0.2,
            alpha=_number(env, "alpha", default=1e-4) or 1e-4,
            t_left=_number(env, "t_left", "tleft", default=373.15) or 373.15,
            t_right=_number(env, "t_right", "tright", default=273.15) or 273.15,
            t_init=_number(env, "t_init", "tinit", default=293.15) or 293.15,
            duration=duration if duration > 1 else 30.0,
        )
    if model in {"rc", "rccircuit"}:
        from veyra.physics import simulate_rc

        return simulate_rc(
            resistance=_number(env, "resistance", "r", default=1000) or 1000,
            capacitance=_number(env, "capacitance", "c", default=1e-6) or 1e-6,
            v_source=_number(env, "v_source", "v", default=5) or 5,
            duration=duration if duration < 10 else 0.008,
        )
    if model in {"range", "rangetable"}:
        from veyra.physics import simulate_range_table

        return simulate_range_table(
            velocity=_number(env, "velocity", "v", default=38) or 38,
            drag_coefficient=_number(env, "drag", "cd", "drag_coefficient", default=0.0) or 0.0,
        )
    if model in {"bernoulli"}:
        return simulate_bernoulli(
            density=_number(env, "density", default=1000) or 1000,
            v1=_number(env, "v1", default=2) or 2,
            v2=_number(env, "v2", default=4) or 4,
            h1=_number(env, "h1", default=3) or 3,
            h2=_number(env, "h2", default=1) or 1,
            p1=_number(env, "p1", "pressure", default=101325) or 101325,
        )
    if model in {"cooling", "newton-cooling"}:
        from veyra.physics import simulate_cooling

        return simulate_cooling(
            t0=_number(env, "t0", "t_init", default=363.15) or 363.15,
            t_env=_number(env, "t_env", "tenv", default=293.15) or 293.15,
            k=_number(env, "k", default=0.05) or 0.05,
            duration=duration if duration > 1 else 120.0,
        )
    if model in {"decay", "radioactive"}:
        from veyra.physics import simulate_decay

        return simulate_decay(
            n0=_number(env, "n0", "n", default=1000) or 1000,
            half_life=_number(env, "half_life", "halflife", default=10) or 10,
            duration=duration if duration > 1 else 40.0,
        )
    if model in {"atwood"}:
        from veyra.physics import simulate_atwood

        return simulate_atwood(
            m1=_number(env, "m1", default=1.2) or 1.2,
            m2=_number(env, "m2", default=1.0) or 1.0,
            gravity=_number(env, "g", "gravity", default=9.80665) or 9.80665,
        )
    if model in {"rl", "rlcircuit"}:
        from veyra.physics import simulate_rl

        return simulate_rl(
            resistance=_number(env, "resistance", "r", default=10) or 10,
            inductance=_number(env, "inductance", "l", default=0.5) or 0.5,
            v_source=_number(env, "v_source", "v", default=12) or 12,
            duration=duration if duration > 0.01 else 0.4,
        )
    if model in {"freefall", "free-fall"}:
        from veyra.physics import simulate_freefall

        return simulate_freefall(
            y0=_number(env, "y0", "height", default=80) or 80,
            v0=_number(env, "v0", default=0.0) or 0.0,
            gravity=_number(env, "g", "gravity", default=9.80665) or 9.80665,
            duration=duration if duration > 0.05 else 4.0,
        )
    if model in {"kepler"}:
        from veyra.physics import simulate_kepler

        return simulate_kepler(
            altitude_m=_number(env, "altitude", "altitude_m", default=400_000) or 400_000,
        )
    if model in {"lc", "lccircuit"}:
        from veyra.physics import simulate_lc

        return simulate_lc(
            inductance=_number(env, "inductance", "l", default=0.5) or 0.5,
            capacitance=_number(env, "capacitance", "c", default=2e-6) or 2e-6,
            q0=_number(env, "q0", default=1e-6) or 1e-6,
            i0=_number(env, "i0", default=0.0) or 0.0,
            duration=duration if duration > 0.001 else 0.02,
        )
    if model in {"lens", "thin-lens"}:
        from veyra.physics import simulate_lens

        return simulate_lens(
            focal_length=_number(env, "focal_length", "f", default=0.05) or 0.05,
            object_distance=_number(env, "object_distance", "do", default=0.12) or 0.12,
        )
    if model in {"escape"}:
        from veyra.physics import simulate_escape

        return simulate_escape(
            altitude_m=_number(env, "altitude", "altitude_m", default=0.0) or 0.0,
        )
    if model in {"shm", "harmonic"}:
        from veyra.physics import simulate_shm

        return simulate_shm(
            mass=_number(env, "mass", "m", default=1.0) or 1.0,
            stiffness=_number(env, "stiffness", "k", default=16.0) or 16.0,
            amplitude=_number(env, "amplitude", "a", "x0", default=0.1) or 0.1,
            duration=duration if duration > 0.1 else 4.0,
        )
    if model in {"doppler"}:
        from veyra.physics import simulate_doppler

        vs = _number(env, "v_source", "vs", default=20.0)
        vo = _number(env, "v_observer", "vo", default=0.0)
        return simulate_doppler(
            frequency=_number(env, "frequency", "f", default=440) or 440,
            v_source=20.0 if vs is None else vs,
            v_observer=0.0 if vo is None else vo,
            speed_sound=_number(env, "speed_sound", "c", default=343) or 343,
        )
    if model in {"circular", "centripetal"}:
        from veyra.physics import simulate_circular

        return simulate_circular(
            radius=_number(env, "radius", "r", default=10) or 10,
            speed=_number(env, "speed", "v", default=5) or 5,
        )
    if model in {"measure", "measurement"}:
        from veyra.measure import analyze_measurement

        raw_path = str(experiment.inputs.get("path") or env.get("path") or "")
        csv_path = None
        if raw_path:
            candidates = [Path(raw_path)]
            if experiment.source:
                parent = Path(experiment.source).resolve().parent
                candidates.append(parent / raw_path)
                candidates.append(parent / Path(raw_path).name)
                candidates.append(parent / "data" / Path(raw_path).name)
            candidates.append(Path.cwd() / raw_path)
            csv_path = next((item for item in candidates if item.is_file()), Path(raw_path))
        reserved = {
            "path",
            "x",
            "y",
            "fit",
            "overlay",
            "x_unit",
            "y_unit",
            "source",
        }
        overlay_params = {
            key: value
            for key, value in env.items()
            if isinstance(value, (int, float)) and key not in reserved and "__" not in key
        }
        return analyze_measurement(
            path=csv_path,
            x=str(experiment.inputs.get("x") or env.get("x") or ""),
            y=str(experiment.inputs.get("y") or env.get("y") or ""),
            x_unit=str(experiment.inputs.get("x_unit") or env.get("x_unit") or ""),
            y_unit=str(experiment.inputs.get("y_unit") or env.get("y_unit") or ""),
            fit=str(env.get("fit") or experiment.inputs.get("fit") or "none"),
            overlay=str(env.get("overlay") or experiment.inputs.get("overlay") or ""),
            overlay_params=overlay_params,
        )
    if model in {"fit", "least-squares"}:
        raw_x = experiment.inputs.get("x", "0 1 2 3 4")
        raw_y = experiment.inputs.get("y", "0.1 2.0 3.9 6.2 8.1")
        xs = [float(part) for part in str(raw_x).replace(",", " ").split()]
        ys = [float(part) for part in str(raw_y).replace(",", " ").split()]
        return fit_model(xs, ys, str(env.get("fit") or experiment.inputs.get("fit") or "linear"))
    if model in {"probability"}:
        values = env.get("values")
        if isinstance(values, str):
            parsed = [float(part) for part in values.replace(",", " ").split()]
        elif isinstance(values, (int, float)):
            raw = experiment.inputs.get("values", "0.5 0.5")
            parsed = [float(part) for part in raw.replace(",", " ").split()]
        else:
            parsed = [0.5, 0.5]
        return probability_check(parsed)
    if experiment.equations:
        metrics = [
            Metric(key, float(val))
            for key, val in env.items()
            if isinstance(val, (int, float)) and not key.endswith("__unc") and not key.endswith("__unit")
        ]
        return VeyraResult(
            ok=True,
            kind="symbolic experiment",
            title=experiment.name,
            checks=[Check("equations evaluated", True)],
            metrics=metrics[:12],
            solver="veyra expression evaluator",
        )
    return VeyraResult(
        ok=False,
        kind="unknown model",
        title=experiment.name,
        checks=[Check("known model", False, model)],
    )


def _parse_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    if raw.strip() == "adaptive":
        return default
    try:
        return parse_measured(raw).value
    except Exception:  # noqa: BLE001
        try:
            return float(raw.split()[0])
        except Exception:  # noqa: BLE001
            return default
