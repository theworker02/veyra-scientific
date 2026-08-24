"""Installed laboratory models — titles, groups, and parameter schemas for the Workbench."""

from __future__ import annotations

import inspect
import re
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

import numpy as np

from veyra.core import VERSION, Check, Metric, VeyraResult
from veyra.physics import DISPATCH, run_named
from veyra.plots import make_plot, series

ENTRIES: list[dict[str, Any]] = [
    {
        "id": "projectile",
        "title": "Projectile dynamics",
        "group": "Mechanics",
        "summary": "2D trajectory. Vacuum is analytic; Cd > 0 uses vectorized RK4 with quadratic drag and a Monte Carlo envelope.",
        "aliases": ["motion"],
        "params": [
            {"name": "velocity", "label": "Launch speed", "type": "number", "default": 38, "unit": "m/s", "min": 0.1, "step": 0.1},
            {"name": "angle_deg", "label": "Launch angle", "type": "number", "default": 47, "unit": "deg", "min": 0, "max": 90, "step": 0.5},
            {"name": "drag_coefficient", "label": "Drag Cd", "type": "number", "default": 0.15, "unit": "", "min": 0, "step": 0.01},
            {"name": "mass", "label": "Mass", "type": "number", "default": 1, "unit": "kg", "min": 0.001, "step": 0.01},
            {"name": "trials", "label": "Trials", "type": "integer", "default": 32, "unit": "", "min": 1, "max": 256},
        ],
    },
    {
        "id": "range",
        "title": "Ballistic range table",
        "group": "Mechanics",
        "summary": "Sweep launch angle at fixed speed and report range, peak, and the angle of maximum reach.",
        "aliases": ["rangetable"],
        "params": [
            {"name": "velocity", "label": "Launch speed", "type": "number", "default": 38, "unit": "m/s", "min": 0.1, "step": 0.1},
            {"name": "drag_coefficient", "label": "Drag Cd", "type": "number", "default": 0, "unit": "", "min": 0, "step": 0.01},
        ],
    },
    {
        "id": "orbit",
        "title": "Two-body orbit",
        "group": "Mechanics",
        "summary": "Earth-centered Keplerian motion integrated with DOP853. Energy and angular momentum are checked.",
        "aliases": ["twobody", "two-body"],
        "params": [
            {"name": "altitude_m", "label": "Altitude", "type": "number", "default": 400000, "unit": "m", "min": 1000, "step": 1000},
            {"name": "duration_s", "label": "Duration", "type": "number", "default": 5400, "unit": "s", "min": 60, "step": 60},
            {"name": "eccentricity", "label": "Eccentricity", "type": "number", "default": 0, "unit": "", "min": 0, "max": 0.9, "step": 0.01},
        ],
    },
    {
        "id": "collision",
        "title": "1D collision",
        "group": "Mechanics",
        "summary": "Two-body impact with restitution. Momentum is always checked; energy is checked when e = 1.",
        "aliases": [],
        "params": [
            {"name": "m1", "label": "Mass 1", "type": "number", "default": 2, "unit": "kg", "min": 0.001, "step": 0.1},
            {"name": "m2", "label": "Mass 2", "type": "number", "default": 1, "unit": "kg", "min": 0.001, "step": 0.1},
            {"name": "u1", "label": "Velocity 1", "type": "number", "default": 3, "unit": "m/s", "step": 0.1},
            {"name": "u2", "label": "Velocity 2", "type": "number", "default": -1, "unit": "m/s", "step": 0.1},
            {"name": "restitution", "label": "Restitution", "type": "number", "default": 1, "unit": "", "min": 0, "max": 1, "step": 0.05},
        ],
    },
    {
        "id": "pendulum",
        "title": "Nonlinear pendulum",
        "group": "Mechanics",
        "summary": "Planar pendulum integrated as an ODE. Energy conservation is tested on the computed trajectory.",
        "aliases": [],
        "params": [
            {"name": "length", "label": "Length", "type": "number", "default": 1, "unit": "m", "min": 0.01, "step": 0.01},
            {"name": "theta0", "label": "Initial angle", "type": "number", "default": 0.4, "unit": "rad", "step": 0.05},
            {"name": "duration", "label": "Duration", "type": "number", "default": 8, "unit": "s", "min": 0.5, "step": 0.5},
        ],
    },
    {
        "id": "oscillator",
        "title": "Damped oscillator",
        "group": "Mechanics",
        "summary": "Linear viscously damped mass–spring, RK45. Mechanical energy must not increase.",
        "aliases": ["damped"],
        "params": [
            {"name": "mass", "label": "Mass", "type": "number", "default": 1, "unit": "kg", "min": 0.01, "step": 0.01},
            {"name": "stiffness", "label": "Stiffness", "type": "number", "default": 16, "unit": "N/m", "min": 0.01, "step": 0.1},
            {"name": "damping", "label": "Damping", "type": "number", "default": 0.4, "unit": "N·s/m", "min": 0, "step": 0.05},
            {"name": "x0", "label": "Initial x", "type": "number", "default": 1, "unit": "m", "step": 0.1},
            {"name": "duration", "label": "Duration", "type": "number", "default": 12, "unit": "s", "min": 0.5, "step": 0.5},
        ],
    },
    {
        "id": "fluid",
        "title": "Hydrostatic pressure",
        "group": "Fluids",
        "summary": "P = P0 + ρgh along a vertical column.",
        "aliases": ["hydrostatic"],
        "params": [
            {"name": "density", "label": "Density", "type": "number", "default": 1000, "unit": "kg/m³", "min": 0.01, "step": 1},
            {"name": "depth", "label": "Depth", "type": "number", "default": 10, "unit": "m", "min": 0, "step": 0.1},
            {"name": "p0", "label": "Surface pressure", "type": "number", "default": 101325, "unit": "Pa", "min": 0, "step": 100},
        ],
    },
    {
        "id": "bernoulli",
        "title": "Bernoulli streamline",
        "group": "Fluids",
        "summary": "Steady incompressible Bernoulli between two stations, with a hydrostatic cross-check.",
        "aliases": [],
        "params": [
            {"name": "density", "label": "Density", "type": "number", "default": 1000, "unit": "kg/m³", "min": 0.01, "step": 1},
            {"name": "v1", "label": "Speed 1", "type": "number", "default": 2, "unit": "m/s", "min": 0, "step": 0.1},
            {"name": "v2", "label": "Speed 2", "type": "number", "default": 4, "unit": "m/s", "min": 0, "step": 0.1},
            {"name": "h1", "label": "Height 1", "type": "number", "default": 3, "unit": "m", "step": 0.1},
            {"name": "h2", "label": "Height 2", "type": "number", "default": 1, "unit": "m", "step": 0.1},
            {"name": "p1", "label": "Pressure 1", "type": "number", "default": 101325, "unit": "Pa", "min": 0, "step": 100},
        ],
    },
    {
        "id": "diffusion",
        "title": "1D heat diffusion",
        "group": "Thermo",
        "summary": "Transient heat equation on a rod (method of lines, RK45) with Dirichlet ends and a maximum principle check.",
        "aliases": ["heat1d", "heat-diffusion"],
        "params": [
            {"name": "length", "label": "Length", "type": "number", "default": 0.2, "unit": "m", "min": 0.01, "step": 0.01},
            {"name": "alpha", "label": "Diffusivity", "type": "number", "default": 0.0001, "unit": "m²/s", "min": 1e-8, "step": 0.00001},
            {"name": "t_left", "label": "T left", "type": "number", "default": 373.15, "unit": "K", "min": 0, "step": 1},
            {"name": "t_right", "label": "T right", "type": "number", "default": 273.15, "unit": "K", "min": 0, "step": 1},
            {"name": "t_init", "label": "T initial", "type": "number", "default": 293.15, "unit": "K", "min": 0, "step": 1},
            {"name": "duration", "label": "Duration", "type": "number", "default": 30, "unit": "s", "min": 0.1, "step": 1},
        ],
    },
    {
        "id": "thermo",
        "title": "Ideal gas state",
        "group": "Thermo",
        "summary": "Ideal-gas closure with residual against PV = nRT.",
        "aliases": [],
        "params": [
            {"name": "pressure", "label": "Pressure", "type": "number", "default": 101325, "unit": "Pa", "min": 1, "step": 100},
            {"name": "volume", "label": "Volume", "type": "number", "default": 0.001, "unit": "m³", "min": 1e-9, "step": 0.0001},
            {"name": "temperature", "label": "Temperature", "type": "number", "default": 298.15, "unit": "K", "min": 0.01, "step": 0.1},
            {"name": "moles", "label": "Amount", "type": "number", "default": 0.0403, "unit": "mol", "min": 1e-9, "step": 0.001},
        ],
    },
    {
        "id": "rc",
        "title": "RC transient",
        "group": "Circuits",
        "summary": "Series RC charging. Numeric RK45 is compared to the closed-form exponential.",
        "aliases": ["rccircuit"],
        "params": [
            {"name": "resistance", "label": "Resistance", "type": "number", "default": 1000, "unit": "Ω", "min": 0.01, "step": 10},
            {"name": "capacitance", "label": "Capacitance", "type": "number", "default": 0.000001, "unit": "F", "min": 1e-12, "step": 1e-7},
            {"name": "v_source", "label": "Source", "type": "number", "default": 5, "unit": "V", "step": 0.1},
            {"name": "duration", "label": "Duration", "type": "number", "default": 0.008, "unit": "s", "min": 1e-6, "step": 0.001},
        ],
    },
    {
        "id": "wave",
        "title": "Traveling wave",
        "group": "Waves",
        "summary": "Harmonic traveling wave: wavelength, period, and phase speed.",
        "aliases": [],
        "params": [
            {"name": "amplitude", "label": "Amplitude", "type": "number", "default": 1, "unit": "", "min": 0, "step": 0.1},
            {"name": "wavelength", "label": "Wavelength", "type": "number", "default": 2, "unit": "m", "min": 0.01, "step": 0.1},
            {"name": "frequency", "label": "Frequency", "type": "number", "default": 4, "unit": "Hz", "min": 0.01, "step": 0.1},
        ],
    },
    {
        "id": "optics",
        "title": "Snell refraction",
        "group": "Waves",
        "summary": "Snell's law at a planar interface, including TIR when the transmitted angle is undefined.",
        "aliases": [],
        "params": [
            {"name": "n1", "label": "n₁", "type": "number", "default": 1, "unit": "", "min": 1, "step": 0.01},
            {"name": "n2", "label": "n₂", "type": "number", "default": 1.5, "unit": "", "min": 1, "step": 0.01},
            {"name": "angle_deg", "label": "Incidence", "type": "number", "default": 30, "unit": "deg", "min": 0, "max": 90, "step": 0.5},
        ],
    },
    {
        "id": "stress",
        "title": "Uniaxial stress",
        "group": "Continuum",
        "summary": "σ = F/A, with optional strain from Young's modulus.",
        "aliases": ["material"],
        "params": [
            {"name": "force", "label": "Force", "type": "number", "default": 1000, "unit": "N", "step": 10},
            {"name": "area", "label": "Area", "type": "number", "default": 0.001, "unit": "m²", "min": 1e-12, "step": 0.0001},
        ],
    },
    {
        "id": "relativity",
        "title": "Special relativity",
        "group": "Foundations",
        "summary": "Lorentz factor, time dilation, and rest-energy scale for a given speed.",
        "aliases": [],
        "params": [
            {"name": "velocity", "label": "Speed", "type": "number", "default": 1e8, "unit": "m/s", "min": 0, "step": 1e6},
            {"name": "rest_mass", "label": "Rest mass", "type": "number", "default": 1, "unit": "kg", "min": 0, "step": 0.1},
        ],
    },
    {
        "id": "quantum",
        "title": "Particle in a box",
        "group": "Foundations",
        "summary": "Infinite square well energy levels from the textbook closed form.",
        "aliases": [],
        "params": [
            {"name": "n", "label": "Quantum number", "type": "integer", "default": 1, "unit": "", "min": 1, "max": 20},
            {"name": "length", "label": "Well width", "type": "number", "default": 1e-9, "unit": "m", "min": 1e-12, "step": 1e-10},
        ],
    },
    {
        "id": "cooling",
        "title": "Newton cooling",
        "group": "Thermo",
        "summary": "Newton's law of cooling. RK45 is compared to the closed-form exponential.",
        "aliases": ["newton-cooling"],
        "params": [
            {"name": "t0", "label": "T initial", "type": "number", "default": 363.15, "unit": "K", "min": 0, "step": 1},
            {"name": "t_env", "label": "T environment", "type": "number", "default": 293.15, "unit": "K", "min": 0, "step": 1},
            {"name": "k", "label": "Rate k", "type": "number", "default": 0.05, "unit": "1/s", "min": 1e-6, "step": 0.01},
            {"name": "duration", "label": "Duration", "type": "number", "default": 120, "unit": "s", "min": 0.1, "step": 1},
        ],
    },
    {
        "id": "decay",
        "title": "Radioactive decay",
        "group": "Foundations",
        "summary": "N = N0 e^(−λ t) with λ = ln 2 / t½. Numeric RK45 is checked against the closed form.",
        "aliases": ["radioactive"],
        "params": [
            {"name": "n0", "label": "N initial", "type": "number", "default": 1000, "unit": "", "min": 1e-9, "step": 10},
            {"name": "half_life", "label": "Half-life", "type": "number", "default": 10, "unit": "s", "min": 1e-6, "step": 0.5},
            {"name": "duration", "label": "Duration", "type": "number", "default": 40, "unit": "s", "min": 0.1, "step": 1},
        ],
    },
    {
        "id": "atwood",
        "title": "Atwood machine",
        "group": "Mechanics",
        "summary": "Two masses on an ideal pulley. Acceleration and tension from Newton's second law.",
        "aliases": [],
        "params": [
            {"name": "m1", "label": "Mass 1", "type": "number", "default": 1.2, "unit": "kg", "min": 0.001, "step": 0.05},
            {"name": "m2", "label": "Mass 2", "type": "number", "default": 1, "unit": "kg", "min": 0.001, "step": 0.05},
        ],
    },
    {
        "id": "rl",
        "title": "RL transient",
        "group": "Circuits",
        "summary": "Series RL current rise. Numeric RK45 is compared to the closed-form exponential.",
        "aliases": ["rlcircuit"],
        "params": [
            {"name": "resistance", "label": "Resistance", "type": "number", "default": 10, "unit": "Ω", "min": 0.01, "step": 0.5},
            {"name": "inductance", "label": "Inductance", "type": "number", "default": 0.5, "unit": "H", "min": 1e-6, "step": 0.05},
            {"name": "v_source", "label": "Source", "type": "number", "default": 12, "unit": "V", "step": 0.1},
            {"name": "duration", "label": "Duration", "type": "number", "default": 0.4, "unit": "s", "min": 1e-6, "step": 0.05},
        ],
    },
    {
        "id": "freefall",
        "title": "Free fall",
        "group": "Mechanics",
        "summary": "Vertical motion in uniform g. RK45 is checked against y = y0 + v0 t − ½ g t².",
        "aliases": ["free-fall"],
        "params": [
            {"name": "y0", "label": "Height", "type": "number", "default": 80, "unit": "m", "step": 1},
            {"name": "v0", "label": "Initial speed", "type": "number", "default": 0, "unit": "m/s", "step": 0.1},
            {"name": "duration", "label": "Duration", "type": "number", "default": 4, "unit": "s", "min": 0.05, "step": 0.1},
        ],
    },
    {
        "id": "kepler",
        "title": "Kepler period",
        "group": "Mechanics",
        "summary": "Circular Kepler identity T²/a³ = 4π²/GM, with period versus altitude.",
        "aliases": [],
        "params": [
            {"name": "altitude_m", "label": "Altitude", "type": "number", "default": 400000, "unit": "m", "min": 1000, "step": 1000},
        ],
    },
    {
        "id": "lc",
        "title": "LC oscillator",
        "group": "Circuits",
        "summary": "Undamped LC tank. RK45 is compared to q = Q0 cos(ωt), ω = 1/√(LC), with energy conservation.",
        "aliases": ["lccircuit"],
        "params": [
            {"name": "inductance", "label": "Inductance", "type": "number", "default": 0.5, "unit": "H", "min": 1e-9, "step": 0.05},
            {"name": "capacitance", "label": "Capacitance", "type": "number", "default": 0.000002, "unit": "F", "min": 1e-12, "step": 1e-7},
            {"name": "q0", "label": "q initial", "type": "number", "default": 0.000001, "unit": "C", "step": 1e-7},
            {"name": "duration", "label": "Duration", "type": "number", "default": 0.02, "unit": "s", "min": 1e-6, "step": 0.001},
        ],
    },
    {
        "id": "lens",
        "title": "Thin lens",
        "group": "Waves",
        "summary": "Gaussian lens formula 1/f = 1/do + 1/di, with magnification and di versus do.",
        "aliases": ["thin-lens"],
        "params": [
            {"name": "focal_length", "label": "Focal length", "type": "number", "default": 0.05, "unit": "m", "step": 0.001},
            {"name": "object_distance", "label": "Object distance", "type": "number", "default": 0.12, "unit": "m", "min": 0.001, "step": 0.01},
        ],
    },
    {
        "id": "escape",
        "title": "Escape velocity",
        "group": "Mechanics",
        "summary": "v_esc = √(2GM/r). The circular identity v_esc / v_circ = √2 is checked.",
        "aliases": [],
        "params": [
            {"name": "altitude_m", "label": "Altitude", "type": "number", "default": 0, "unit": "m", "min": 0, "step": 1000},
        ],
    },
    {
        "id": "shm",
        "title": "Simple harmonic motion",
        "group": "Mechanics",
        "summary": "Undamped mass–spring. RK45 is compared to x = A cos(ωt), ω = √(k/m).",
        "aliases": ["harmonic"],
        "params": [
            {"name": "mass", "label": "Mass", "type": "number", "default": 1, "unit": "kg", "min": 0.01, "step": 0.01},
            {"name": "stiffness", "label": "Stiffness", "type": "number", "default": 16, "unit": "N/m", "min": 0.01, "step": 0.1},
            {"name": "amplitude", "label": "Amplitude", "type": "number", "default": 0.1, "unit": "m", "min": 0.001, "step": 0.01},
            {"name": "duration", "label": "Duration", "type": "number", "default": 4, "unit": "s", "min": 0.1, "step": 0.5},
        ],
    },
    {
        "id": "doppler",
        "title": "Doppler shift",
        "group": "Waves",
        "summary": "Line-of-sight acoustic Doppler. Positive speed is toward the other body: f' = f (c+vo)/(c−vs).",
        "aliases": [],
        "params": [
            {"name": "frequency", "label": "Source f", "type": "number", "default": 440, "unit": "Hz", "min": 0.01, "step": 1},
            {"name": "v_source", "label": "Source speed", "type": "number", "default": 20, "unit": "m/s", "step": 1},
            {"name": "v_observer", "label": "Observer speed", "type": "number", "default": 0, "unit": "m/s", "step": 1},
            {"name": "speed_sound", "label": "Sound speed", "type": "number", "default": 343, "unit": "m/s", "min": 1, "step": 1},
        ],
    },
    {
        "id": "circular",
        "title": "Circular motion",
        "group": "Mechanics",
        "summary": "Uniform circular motion. Centripetal identity a = v²/r and T = 2πr/v.",
        "aliases": ["centripetal"],
        "params": [
            {"name": "radius", "label": "Radius", "type": "number", "default": 10, "unit": "m", "min": 0.01, "step": 0.1},
            {"name": "speed", "label": "Speed", "type": "number", "default": 5, "unit": "m/s", "min": 0.01, "step": 0.1},
        ],
    },
]

KIND_TO_ID = {
    "2D rigid-body trajectory": "projectile",
    "ballistic range table": "range",
    "two-body orbital mechanics": "orbit",
    "1D collision": "collision",
    "nonlinear pendulum": "pendulum",
    "damped harmonic oscillator": "oscillator",
    "hydrostatics": "fluid",
    "Bernoulli + hydrostatics": "bernoulli",
    "1D heat diffusion": "diffusion",
    "ideal gas": "thermo",
    "RC transient": "rc",
    "traveling wave": "wave",
    "optics": "optics",
    "continuum foundations": "stress",
    "special relativity foundations": "relativity",
    "particle in a box": "quantum",
    "Newton cooling": "cooling",
    "radioactive decay": "decay",
    "Atwood machine": "atwood",
    "RL transient": "rl",
    "free fall": "freefall",
    "Kepler period": "kepler",
    "LC oscillator": "lc",
    "thin lens": "lens",
    "escape velocity": "escape",
    "simple harmonic motion": "shm",
    "Doppler shift": "doppler",
    "circular motion": "circular",
    "measurement": "measure",
}


def catalog_payload() -> dict[str, Any]:
    groups: dict[str, int] = {}
    for entry in ENTRIES:
        groups[entry["group"]] = groups.get(entry["group"], 0) + 1
    return {
        "veyra": VERSION,
        "models": sorted(DISPATCH),
        "entries": ENTRIES,
        "groups": groups,
        "count": len(ENTRIES),
    }


def lookup_entry(name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for entry in ENTRIES:
        aliases = [str(item).lower() for item in (entry.get("aliases") or [])]
        if entry["id"] == key or key in aliases:
            return entry
    return None


_UNIT_TOKEN = {
    "Ω": "ohm",
    "m²": "m^2",
    "m³": "m^3",
    "kg/m³": "kg/m^3",
    "N·s/m": "N*s/m",
    "°": "deg",
}


def scaffold_experiment(name: str) -> str:
    """Render a runnable .veyra file from a catalog model schema."""
    entry = lookup_entry(name)
    if entry is None:
        raise ValueError(f"unknown model '{name}'")
    lines = [f"experiment {entry['id']} {{", f"    model {entry['id']}", "    inputs {"]
    duration_line = ""
    asserted = ""
    for param in entry["params"]:
        unit = _UNIT_TOKEN.get(str(param.get("unit") or ""), str(param.get("unit") or ""))
        default = param["default"]
        value = f"{default:g}" if isinstance(default, float) else str(default)
        unit_part = f" {unit}" if unit else ""
        lines.append(f"        {param['name']} = {value}{unit_part}")
        if param["name"] == "duration":
            duration_line = f"        duration = {value}{unit_part}"
        if not asserted and float(default) > 0 and param["name"] not in {"v0", "u2", "theta0", "x0"}:
            asserted = param["name"]
    lines.append("    }")
    if asserted:
        lines.append("    assert {")
        lines.append(f"        {asserted} > 0")
        lines.append("    }")
    if duration_line:
        lines.append("    simulate {")
        lines.append(duration_line)
        lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def guess_model(kind: str, title: str = "") -> str | None:
    if kind in KIND_TO_ID:
        return KIND_TO_ID[kind]
    blob = f"{kind} {title}".lower()
    for entry in ENTRIES:
        if entry["id"] in blob or entry["title"].lower() in blob:
            return str(entry["id"])
        if any(alias in blob for alias in entry.get("aliases") or []):
            return str(entry["id"])
    return None


def bind_model_kwargs(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    fn = DISPATCH.get(name)
    if fn is None:
        return {}
    try:
        hints = get_type_hints(fn)
    except Exception:  # noqa: BLE001
        hints = {}
    signature = inspect.signature(fn)
    bound: dict[str, Any] = {}
    for key, param in signature.parameters.items():
        if key not in raw:
            continue
        value = raw[key]
        if value is None or value == "":
            continue
        bound[key] = _coerce(value, hints.get(key, param.annotation))
    return bound


def _coerce(value: Any, annotation: Any) -> Any:
    if annotation is inspect.Parameter.empty:
        return value
    origin = get_origin(annotation)
    args = [item for item in get_args(annotation) if item is not type(None)]
    union_origins: set[Any] = {Union}
    if hasattr(types, "UnionType"):
        union_origins.add(types.UnionType)
    type_list = list(args) if origin in union_origins else [annotation]
    if int in type_list and float not in type_list:
        if isinstance(value, str):
            match = re.search(r"-?\d+", value)
            return int(match.group(0)) if match else int(value)
        return int(float(value))
    if float in type_list:
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", value, re.I)
            if match:
                return float(match.group(0))
        return float(value)
    if list in type_list or origin is list:
        if isinstance(value, list):
            return value
        return [float(part) for part in str(value).replace(",", " ").split() if part]
    if str in type_list:
        return str(value)
    return value


def numeric_inputs(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, (int, float)):
            out[key] = value
        elif isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", value, re.I)
            out[key] = float(match.group(0)) if match else value
        else:
            out[key] = value
    return out


def sweep_model(
    name: str,
    param: str,
    start: float,
    stop: float,
    steps: int = 12,
    base: dict[str, Any] | None = None,
) -> VeyraResult:
    """Run one catalog model across a 1-D parameter grid. Inner trials are not stored."""
    if name not in DISPATCH:
        return VeyraResult(
            ok=False,
            kind="parameter sweep",
            title="Sweep",
            checks=[Check("known model", False, f"unknown '{name}'")],
        )
    count = max(2, min(int(steps), 48))
    grid = np.linspace(float(start), float(stop), count)
    xs: list[float] = []
    ys: list[float] = []
    metric_name = "metric"
    metric_unit = ""
    rows: list[dict[str, Any]] = []
    passed = 0
    for value in grid:
        kwargs = bind_model_kwargs(name, {**(base or {}), param: float(value)})
        result = run_named(name, **kwargs)
        numeric = next((m for m in result.metrics if isinstance(m.value, (int, float))), None)
        if numeric is None:
            continue
        metric_name = numeric.name
        metric_unit = numeric.unit
        xs.append(float(value))
        ys.append(float(numeric.value))
        passed += int(result.ok)
        rows.append({"param": float(value), metric_name: float(numeric.value), "ok": int(result.ok)})
    if not xs:
        return VeyraResult(
            ok=False,
            kind="parameter sweep",
            title=f"{name} sweep",
            checks=[Check("numeric metric", False, "no metric to plot")],
            inputs={"model": name, "param": param},
        )
    return VeyraResult(
        ok=passed == len(xs),
        kind="parameter sweep",
        title=f"{name} vs {param}",
        checks=[
            Check("sweep completed", True, f"{len(xs)} nodes"),
            Check("all nodes passed", passed == len(xs), f"{passed}/{len(xs)}"),
        ],
        metrics=[
            Metric("nodes", len(xs)),
            Metric(f"{metric_name} min", min(ys), metric_unit),
            Metric(f"{metric_name} max", max(ys), metric_unit),
        ],
        inputs={"model": name, "param": param, "start": start, "stop": stop, "steps": count},
        details={
            "table": rows,
            "plot": make_plot("series", param, f"{metric_name} ({metric_unit})".strip(), [series(metric_name, xs, ys)]),
        },
        solver="catalog parameter sweep",
    )
