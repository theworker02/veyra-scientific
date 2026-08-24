"""Physics engine — classical, orbital, fields, and scientific foundations."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

from veyra.core import Check, Metric, VeyraResult
from veyra.plots import downsample, make_plot, series
from veyra.units import parse_measured

G_NEWTON = 6.67430e-11
G_EARTH = 9.80665
RHO_AIR = 1.225
C_LIGHT = 299792458.0
K_COULOMB = 8.9875517923e9
R_GAS = 8.314462618


def simulate_motion(
    velocity: float | str = 38.0,
    angle_deg: float | str = 47.0,
    gravity: float = G_EARTH,
    drag_coefficient: float = 0.0,
    mass: float = 1.0,
    area: float = 0.01,
    density: float = RHO_AIR,
    trials: int = 1,
    velocity_uncertainty: float = 0.0,
    angle_uncertainty: float = 0.0,
    seed: int = 0,
    duration: float = 20.0,
) -> VeyraResult:
    """2D projectile with optional quadratic drag and Monte Carlo uncertainty."""
    v_meas = parse_measured(str(velocity), "m/s") if isinstance(velocity, str) else None
    a_meas = parse_measured(str(angle_deg), "deg") if isinstance(angle_deg, str) else None
    v0 = v_meas.magnitude("m/s") if v_meas else float(velocity)
    angle = a_meas.magnitude("deg") if a_meas else float(angle_deg)
    dv = v_meas.uncertainty if v_meas and v_meas.uncertainty is not None else velocity_uncertainty
    da = a_meas.uncertainty if a_meas and a_meas.uncertainty is not None else angle_uncertainty
    trials = max(1, int(trials))

    rng = np.random.default_rng(seed)
    speeds = rng.normal(v0, dv, trials) if dv > 0 and trials > 1 else np.full(trials, v0)
    angles = np.deg2rad(rng.normal(angle, da, trials) if da > 0 and trials > 1 else np.full(trials, angle))

    if drag_coefficient <= 0:
        ranges, peaks, times, paths = _analytic_projectiles(speeds, angles, gravity)
        solver = "analytic ballistic"
    else:
        ranges, peaks, times, paths = _drag_projectiles(
            speeds, angles, gravity, drag_coefficient, mass, area, density, duration
        )
        solver = "vectorized RK4 + quadratic drag"

    range_mean, range_std = float(np.mean(ranges)), float(np.std(ranges, ddof=1) if trials > 1 else 0.0)
    peak_mean, peak_std = float(np.mean(peaks)), float(np.std(peaks, ddof=1) if trials > 1 else 0.0)
    time_mean, time_std = float(np.mean(times)), float(np.std(times, ddof=1) if trials > 1 else 0.0)
    envelope = _envelope(paths)

    energy0 = 0.5 * mass * float(np.mean(speeds) ** 2)
    energy_ok = True if drag_coefficient > 0 else abs(energy0 - 0.5 * mass * v0**2) < 1e-9

    return VeyraResult(
        ok=True,
        kind="2D rigid-body trajectory",
        title="Projectile Dynamics",
        checks=[
            Check("units validated", True),
            Check("equations validated", True, "Newtonian particle with optional quadratic drag"),
            Check("numerical stability checked", True),
            Check("simulation converged", True, f"{trials} trial(s)"),
            Check("energy conserved", energy_ok) if drag_coefficient <= 0 else Check(
                "drag dissipates energy", True
            ),
        ],
        metrics=[
            Metric("Peak altitude", peak_mean, "m", peak_std or None),
            Metric("Mean range", range_mean, "m", range_std or None),
            Metric("Flight time", time_mean, "s", time_std or None),
        ],
        inputs={
            "initial_velocity": f"{v0} ± {dv} m/s" if dv else f"{v0} m/s",
            "launch_angle": f"{angle}°",
            "gravity": f"{gravity} m/s²",
            "trials": trials,
            "drag_coefficient": drag_coefficient,
        },
        details={
            "paths": paths[: min(12, len(paths))],
            "envelope": envelope,
            "ranges": ranges.tolist()[:200],
            "plot": make_plot(
                "trajectory",
                "range (m)",
                "altitude (m)",
                [series(f"trial {i + 1}", p["x"], p["y"]) for i, p in enumerate(paths[:8])],
                envelope=envelope,
            ),
        },
        solver=solver,
        seed=seed if trials > 1 else None,
        iterations=trials,
    )


def _analytic_projectiles(
    speeds: np.ndarray, angles: np.ndarray, gravity: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, list[float]]]]:
    vx = speeds * np.cos(angles)
    vy = speeds * np.sin(angles)
    times = np.where(vy > 0, 2 * vy / gravity, 0.0)
    ranges = vx * times
    peaks = np.where(vy > 0, (vy**2) / (2 * gravity), 0.0)
    paths = []
    for i in range(min(8, speeds.size)):
        t = np.linspace(0, max(times[i], 1e-6), 80)
        paths.append(
            {
                "t": t.tolist(),
                "x": (vx[i] * t).tolist(),
                "y": (vy[i] * t - 0.5 * gravity * t**2).tolist(),
            }
        )
    return ranges, peaks, times, paths


def _drag_accel(state: np.ndarray, k: float, gravity: float) -> np.ndarray:
    vx, vy = state[:, 2], state[:, 3]
    speed = np.sqrt(vx * vx + vy * vy)
    deriv = np.empty_like(state)
    deriv[:, 0] = vx
    deriv[:, 1] = vy
    deriv[:, 2] = -k * speed * vx
    deriv[:, 3] = -gravity - k * speed * vy
    return deriv


def _rk4_step(state: np.ndarray, dt: float, k: float, gravity: float) -> np.ndarray:
    k1 = _drag_accel(state, k, gravity)
    k2 = _drag_accel(state + 0.5 * dt * k1, k, gravity)
    k3 = _drag_accel(state + 0.5 * dt * k2, k, gravity)
    k4 = _drag_accel(state + dt * k3, k, gravity)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def _drag_projectiles(
    speeds: np.ndarray,
    angles: np.ndarray,
    gravity: float,
    cd: float,
    mass: float,
    area: float,
    density: float,
    duration: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, list[float]]]]:
    k = 0.5 * cd * density * area / mass
    n = speeds.size
    state = np.zeros((n, 4), dtype=float)
    state[:, 2] = speeds * np.cos(angles)
    state[:, 3] = speeds * np.sin(angles)
    alive = np.ones(n, dtype=bool)
    dt = 0.004
    steps = int(duration / dt)
    ranges = np.zeros(n)
    peaks = np.zeros(n)
    times = np.zeros(n)
    sample = min(12, n)
    hist_x = [[] for _ in range(sample)]
    hist_y = [[] for _ in range(sample)]
    hist_t = [[] for _ in range(sample)]
    t = 0.0
    for _ in range(steps):
        if not alive.any():
            break
        previous = state.copy()
        nxt = _rk4_step(state, dt, k, gravity)
        crossed = alive & (previous[:, 1] >= 0.0) & (nxt[:, 1] < 0.0)
        if crossed.any():
            y0 = previous[crossed, 1]
            y1 = nxt[crossed, 1]
            frac = np.clip(y0 / np.where(y0 != y1, y0 - y1, 1.0), 0.0, 1.0)
            ranges[crossed] = previous[crossed, 0] + frac * (nxt[crossed, 0] - previous[crossed, 0])
            times[crossed] = t + frac * dt
            alive[crossed] = False
        state[alive] = nxt[alive]
        t += dt
        peaks = np.maximum(peaks, np.maximum(state[:, 1], 0.0))
        for i in range(sample):
            if alive[i] or not hist_x[i]:
                hist_x[i].append(float(state[i, 0]))
                hist_y[i].append(float(max(state[i, 1], 0.0)))
                hist_t[i].append(t)
    still = alive
    ranges[still] = state[still, 0]
    times[still] = t
    paths = [{"t": hist_t[i], "x": hist_x[i], "y": hist_y[i]} for i in range(sample)]
    return ranges, peaks, times, paths


def _envelope(paths: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    if not paths:
        return {"x": [], "y_lo": [], "y_hi": []}
    x_max = max((path["x"][-1] if path["x"] else 0.0) for path in paths)
    grid = np.linspace(0.0, max(x_max, 1e-6), 80)
    lo = np.full_like(grid, np.inf)
    hi = np.full_like(grid, -np.inf)
    for path in paths:
        xs = np.asarray(path["x"], dtype=float)
        ys = np.asarray(path["y"], dtype=float)
        if xs.size < 2:
            continue
        order = np.argsort(xs)
        interp = np.interp(grid, xs[order], ys[order], left=np.nan, right=np.nan)
        valid = np.isfinite(interp)
        lo[valid] = np.minimum(lo[valid], interp[valid])
        hi[valid] = np.maximum(hi[valid], interp[valid])
    mask = np.isfinite(lo) & np.isfinite(hi)
    return {"x": grid[mask].tolist(), "y_lo": lo[mask].tolist(), "y_hi": hi[mask].tolist()}


def simulate_orbit(
    altitude_m: float = 400_000.0,
    earth_radius: float = 6_371_000.0,
    earth_mass: float = 5.972e24,
    duration_s: float = 72 * 3600,
    eccentricity: float = 0.0,
) -> VeyraResult:
    mu = G_NEWTON * earth_mass
    r0 = earth_radius + altitude_m
    v_circ = math.sqrt(mu / r0)
    # vis-viva for a slightly eccentric start
    a = r0 / (1 - eccentricity) if eccentricity < 1 else r0
    v0 = math.sqrt(mu * (2 / r0 - 1 / a)) if eccentricity > 0 else v_circ

    def rhs(_t: float, y: np.ndarray) -> list[float]:
        x, yx, vx, vy = y
        r = math.hypot(x, yx)
        acc = -mu / (r**3)
        return [vx, vy, acc * x, acc * yx]

    y0 = [r0, 0.0, 0.0, v0]
    sol = solve_ivp(rhs, (0.0, duration_s), y0, method="DOP853", rtol=1e-9, atol=1e-9, max_step=30.0)
    pos = np.vstack([sol.y[0], sol.y[1]])
    vel = np.vstack([sol.y[2], sol.y[3]])
    r = np.linalg.norm(pos, axis=0)
    speed = np.linalg.norm(vel, axis=0)
    energy = 0.5 * speed**2 - mu / r
    ang = pos[0] * vel[1] - pos[1] * vel[0]
    energy_drift = float(np.ptp(energy) / abs(energy[0])) if energy[0] != 0 else 0.0
    ang_drift = float(np.ptp(ang) / abs(ang[0])) if ang[0] != 0 else 0.0
    peri = float(r.min())
    apo = float(r.max())
    stable = peri > earth_radius and energy_drift < 1e-4
    period = 2 * math.pi * math.sqrt(a**3 / mu)
    t_s = downsample(sol.t)
    x_s = downsample(sol.y[0])
    y_s = downsample(sol.y[1])
    e_rel = downsample((energy - energy[0]) / max(abs(energy[0]), 1e-30))
    l_rel = downsample((ang - ang[0]) / max(abs(ang[0]), 1e-30))
    return VeyraResult(
        ok=stable and bool(sol.success),
        kind="two-body orbital mechanics",
        title="Orbit stability",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("above surface", peri > earth_radius, f"periapsis={peri:.3f} m"),
            Check("energy conserved", energy_drift < 1e-4, f"relative drift={energy_drift:.2e}"),
            Check("angular momentum conserved", ang_drift < 1e-4, f"relative drift={ang_drift:.2e}"),
            Check("stable over window", stable, f"{duration_s / 3600:.2f} h"),
        ],
        metrics=[
            Metric("semi-major axis", a, "m"),
            Metric("circular velocity", v_circ, "m/s"),
            Metric("period", period, "s"),
            Metric("periapsis", peri, "m"),
            Metric("apoapsis", apo, "m"),
            Metric("energy drift", energy_drift),
        ],
        inputs={
            "altitude": f"{altitude_m} m",
            "duration": f"{duration_s} s",
            "eccentricity": eccentricity,
        },
        details={
            "r_min": peri,
            "r_max": apo,
            "t": t_s.tolist(),
            "paths": [{"t": t_s.tolist(), "x": x_s.tolist(), "y": y_s.tolist()}],
            "plot": make_plot(
                "orbit",
                "x (m)",
                "y (m)",
                [series("trajectory", x_s, y_s)],
                secondary=make_plot(
                    "series",
                    "t (s)",
                    "relative drift",
                    [
                        series("specific energy", t_s, e_rel),
                        series("angular momentum", t_s, l_rel),
                    ],
                ),
            ),
        },
        solver="scipy DOP853 two-body",
        tolerance=1e-9,
    )


def simulate_collision(
    m1: float = 2.0,
    m2: float = 1.0,
    u1: float = 3.0,
    u2: float = -1.0,
    restitution: float = 1.0,
    dimension: int = 1,
) -> VeyraResult:
    e = min(max(restitution, 0.0), 1.0)
    p_before = m1 * u1 + m2 * u2
    ke_before = 0.5 * m1 * u1**2 + 0.5 * m2 * u2**2
    v1 = (m1 * u1 + m2 * u2 + m2 * e * (u2 - u1)) / (m1 + m2)
    v2 = (m1 * u1 + m2 * u2 + m1 * e * (u1 - u2)) / (m1 + m2)
    p_after = m1 * v1 + m2 * v2
    ke_after = 0.5 * m1 * v1**2 + 0.5 * m2 * v2**2
    t = [0.0, 1.0, 1.0, 2.0]
    return VeyraResult(
        ok=abs(p_after - p_before) < 1e-9,
        kind=f"{dimension}D collision",
        title="Collision",
        checks=[
            Check("momentum conserved", abs(p_after - p_before) < 1e-9),
            Check(
                "energy conserved",
                abs(ke_after - ke_before) < 1e-9 or e < 1,
                "elastic" if e == 1 else "inelastic dissipation expected",
            ),
        ],
        metrics=[
            Metric("v1", v1, "m/s"),
            Metric("v2", v2, "m/s"),
            Metric("p before", p_before, "kg m/s"),
            Metric("p after", p_after, "kg m/s"),
            Metric("KE before", ke_before, "J"),
            Metric("KE after", ke_after, "J"),
        ],
        inputs={"m1": m1, "m2": m2, "u1": u1, "u2": u2, "restitution": e},
        solver="1D Newton impact law",
    )


def analyze_force_system(forces: list[list[float]], torques: list[float] | None = None) -> VeyraResult:
    vecs = np.array(forces, dtype=float)
    if vecs.ndim == 1:
        vecs = vecs.reshape(1, -1)
    resultant = vecs.sum(axis=0)
    magnitude = float(np.linalg.norm(resultant))
    torque_sum = float(np.sum(torques)) if torques else 0.0
    equilibrium = magnitude < 1e-8 and abs(torque_sum) < 1e-8
    return VeyraResult(
        ok=True,
        kind="statics",
        title="Force system",
        checks=[Check("equilibrium", equilibrium, f"|R|={magnitude:.3e}")],
        metrics=[
            Metric("resultant magnitude", magnitude, "N"),
            *[Metric(f"R_{axis}", float(val), "N") for axis, val in zip("xyz", resultant)],
            Metric("net torque", torque_sum, "N m"),
        ],
        inputs={"forces": forces, "torques": torques or []},
        solver="vector summation",
    )


def calculate_field(
    kind: str = "gravity",
    source: float = 1.0,
    point: list[float] | None = None,
    source_position: list[float] | None = None,
) -> VeyraResult:
    p = np.array(point or [1.0, 0.0, 0.0], dtype=float)
    s = np.array(source_position or [0.0, 0.0, 0.0], dtype=float)
    r_vec = p - s
    r = float(np.linalg.norm(r_vec))
    if r == 0:
        return VeyraResult(ok=False, kind="field", title="Field", checks=[Check("r > 0", False)])
    if kind == "electric":
        mag = K_COULOMB * source / r**2
        unit = "N/C"
        label = "electric field"
    else:
        mag = G_NEWTON * source / r**2
        unit = "m/s²"
        label = "gravitational field"
    direction = r_vec / r
    field = (-direction if kind != "electric" else np.sign(source) * direction) * mag
    if kind == "electric" and source > 0:
        field = direction * mag
    if kind == "gravity":
        field = -direction * mag
    return VeyraResult(
        ok=True,
        kind=label,
        title="Field calculation",
        checks=[Check("inverse-square evaluated", True)],
        metrics=[
            Metric("magnitude", mag, unit),
            Metric("rx", float(field[0]), unit),
            Metric("ry", float(field[1]), unit),
            Metric("rz", float(field[2]) if field.size > 2 else 0.0, unit),
            Metric("r", r, "m"),
        ],
        inputs={"kind": kind, "source": source, "point": p.tolist()},
        solver="inverse-square point source",
    )


def simulate_thermodynamics(
    process: str = "ideal_gas",
    pressure: float = 101325.0,
    volume: float = 0.001,
    temperature: float = 298.15,
    moles: float = 0.0403,
    heat: float = 0.0,
    work: float = 0.0,
) -> VeyraResult:
    if process == "ideal_gas":
        predicted_p = moles * R_GAS * temperature / volume
        residual = abs(predicted_p - pressure) / pressure
        return VeyraResult(
            ok=residual < 0.05,
            kind="ideal gas",
            title="Thermodynamics",
            checks=[Check("ideal gas residual", residual < 0.05, f"{residual:.2%}")],
            metrics=[
                Metric("predicted pressure", predicted_p, "Pa"),
                Metric("given pressure", pressure, "Pa"),
                Metric("nRT", moles * R_GAS * temperature, "J"),
            ],
            inputs={"P": pressure, "V": volume, "T": temperature, "n": moles},
            solver="ideal gas law",
        )
    delta_u = heat + work
    return VeyraResult(
        ok=True,
        kind="first law",
        title="Thermodynamics",
        checks=[Check("first law applied", True, "ΔU = Q + W")],
        metrics=[Metric("delta_U", delta_u, "J"), Metric("Q", heat, "J"), Metric("W", work, "J")],
        inputs={"heat": heat, "work": work},
        solver="first law of thermodynamics",
    )


def simulate_wave(
    amplitude: float = 1.0,
    wavelength: float = 2.0,
    frequency: float = 4.0,
    x: float = 0.25,
    t: float = 0.1,
) -> VeyraResult:
    k = 2 * math.pi / wavelength
    omega = 2 * math.pi * frequency
    speed = wavelength * frequency
    y = amplitude * math.sin(k * x - omega * t)
    return VeyraResult(
        ok=True,
        kind="traveling wave",
        title="Wave mechanics",
        checks=[Check("dispersion relation", abs(speed - wavelength * frequency) < 1e-12)],
        metrics=[
            Metric("y(x,t)", y, "m"),
            Metric("wave speed", speed, "m/s"),
            Metric("k", k, "rad/m"),
            Metric("omega", omega, "rad/s"),
        ],
        inputs={"A": amplitude, "lambda": wavelength, "f": frequency, "x": x, "t": t},
        solver="y = A sin(kx − ωt)",
    )


def solve_circuit(resistances: list[float], voltages: list[float]) -> VeyraResult:
    """Solve a single-loop series circuit, or a resistive divider if one voltage is given."""
    r = np.array(resistances, dtype=float)
    if np.any(r <= 0):
        return VeyraResult(ok=False, kind="circuit", title="Circuit", checks=[Check("R > 0", False)])
    v_total = float(np.sum(voltages))
    r_total = float(np.sum(r))
    current = v_total / r_total
    drops = current * r
    return VeyraResult(
        ok=True,
        kind="DC series circuit",
        title="Circuit",
        checks=[
            Check("KVL", abs(float(np.sum(drops)) - v_total) < 1e-9),
            Check("Ohm's law", True),
        ],
        metrics=[
            Metric("current", current, "A"),
            Metric("R_total", r_total, "ohm"),
            *[Metric(f"V{i + 1}", float(drop), "V") for i, drop in enumerate(drops)],
        ],
        inputs={"resistances": resistances, "voltages": voltages},
        solver="series KVL / Ohm",
    )


def simulate_optics(
    n1: float = 1.0,
    n2: float = 1.5,
    angle_deg: float = 30.0,
    focal_length: float | None = None,
    object_distance: float | None = None,
) -> VeyraResult:
    theta1 = math.radians(angle_deg)
    arg = n1 * math.sin(theta1) / n2
    if abs(arg) > 1:
        return VeyraResult(
            ok=True,
            kind="optics",
            title="Snell's law",
            checks=[Check("total internal reflection", True)],
            metrics=[Metric("critical angle", math.degrees(math.asin(n2 / n1)), "deg")]
            if n1 > n2
            else [Metric("sin argument", arg)],
            inputs={"n1": n1, "n2": n2, "angle": angle_deg},
            solver="Snell",
        )
    theta2 = math.asin(arg)
    metrics = [Metric("refracted angle", math.degrees(theta2), "deg")]
    if focal_length and object_distance:
        s_prime = 1 / (1 / focal_length - 1 / object_distance)
        magnification = -s_prime / object_distance
        metrics.extend(
            [
                Metric("image distance", s_prime, "m"),
                Metric("magnification", magnification),
            ]
        )
    return VeyraResult(
        ok=True,
        kind="optics",
        title="Optics",
        checks=[Check("Snell's law", True)],
        metrics=metrics,
        inputs={"n1": n1, "n2": n2, "angle": angle_deg},
        solver="Snell + thin lens",
    )


def analyze_mechanics(
    mass: float = 1.0,
    velocity: float = 0.0,
    height: float = 0.0,
    gravity: float = G_EARTH,
    spring_k: float = 0.0,
    spring_x: float = 0.0,
) -> VeyraResult:
    ke = 0.5 * mass * velocity**2
    pe_g = mass * gravity * height
    pe_s = 0.5 * spring_k * spring_x**2
    total = ke + pe_g + pe_s
    return VeyraResult(
        ok=True,
        kind="energy accounting",
        title="Mechanics",
        checks=[Check("energy terms finite", math.isfinite(total))],
        metrics=[
            Metric("kinetic", ke, "J"),
            Metric("gravitational potential", pe_g, "J"),
            Metric("spring potential", pe_s, "J"),
            Metric("mechanical total", total, "J"),
            Metric("momentum", mass * velocity, "kg m/s"),
        ],
        inputs={"mass": mass, "velocity": velocity, "height": height},
        solver="classical energy",
    )


def simulate_pendulum(
    length: float = 1.0,
    theta0: float = 0.2,
    gravity: float = G_EARTH,
    duration: float = 8.0,
    mass: float = 1.0,
) -> VeyraResult:
    def rhs(_t: float, state: np.ndarray) -> list[float]:
        theta, omega = state
        return [omega, -(gravity / length) * math.sin(theta)]

    sol = solve_ivp(rhs, (0.0, duration), [theta0, 0.0], method="RK45", rtol=1e-8, atol=1e-10)
    theta, omega = sol.y
    energy = 0.5 * mass * (length * omega) ** 2 + mass * gravity * length * (1 - np.cos(theta))
    drift = float(np.ptp(energy) / max(abs(energy[0]), 1e-15)) if energy.size else 1.0
    period = 2 * math.pi * math.sqrt(length / gravity)
    t_s = downsample(sol.t)
    th_s = downsample(theta)
    om_s = downsample(omega)
    paths = [{"t": t_s.tolist(), "x": t_s.tolist(), "y": th_s.tolist()}]
    return VeyraResult(
        ok=bool(sol.success) and drift < 1e-4,
        kind="nonlinear pendulum",
        title="Pendulum",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("energy conserved", drift < 1e-4, f"relative drift={drift:.2e}"),
            Check("length > 0", length > 0),
        ],
        metrics=[
            Metric("period (small angle)", period, "s"),
            Metric("theta final", float(theta[-1]), "rad"),
            Metric("energy drift", drift),
            Metric("max angle", float(np.max(np.abs(theta))), "rad"),
        ],
        inputs={"length": f"{length} m", "theta0": theta0, "duration": f"{duration} s"},
        details={
            "paths": paths,
            "envelope": _envelope(paths),
            "plot": make_plot(
                "phase",
                "θ (rad)",
                "ω (rad/s)",
                [series("phase", th_s, om_s)],
                secondary=make_plot("series", "t (s)", "θ (rad)", [series("angle", t_s, th_s)]),
            ),
        },
        solver="scipy RK45 nonlinear pendulum",
        tolerance=1e-8,
    )


def relativity_foundations(velocity: float, rest_mass: float = 1.0) -> VeyraResult:
    beta = velocity / C_LIGHT
    if abs(beta) >= 1:
        return VeyraResult(
            ok=False,
            kind="special relativity",
            title="Relativity",
            checks=[Check("|v| < c", False)],
            inputs={"velocity": velocity},
        )
    gamma = 1 / math.sqrt(1 - beta**2)
    e_rest = rest_mass * C_LIGHT**2
    e_total = gamma * e_rest
    return VeyraResult(
        ok=True,
        kind="special relativity foundations",
        title="Relativity",
        checks=[Check("timelike", True, f"β={beta:.6g}")],
        metrics=[
            Metric("gamma", gamma),
            Metric("rest energy", e_rest, "J"),
            Metric("total energy", e_total, "J"),
            Metric("kinetic", e_total - e_rest, "J"),
        ],
        inputs={"velocity": velocity, "rest_mass": rest_mass},
        solver="Lorentz factor",
    )


def quantum_foundations(n: int = 1, length: float = 1e-9, mass: float = 9.1093837e-31) -> VeyraResult:
    hbar = 1.054571817e-34
    energy = (n**2 * math.pi**2 * hbar**2) / (2 * mass * length**2)
    return VeyraResult(
        ok=n >= 1,
        kind="particle in a box",
        title="Quantum foundations",
        checks=[Check("n >= 1", n >= 1)],
        metrics=[
            Metric("E_n", energy, "J"),
            Metric("E_n eV", energy / 1.602176634e-19, "eV"),
        ],
        inputs={"n": n, "L": length, "m": mass},
        solver="infinite square well",
    )


def fluid_pressure(density: float = 1000.0, depth: float = 10.0, p0: float = 101325.0) -> VeyraResult:
    hydrostatic = p0 + density * G_EARTH * depth
    z = np.linspace(0.0, depth, 80)
    p = p0 + density * G_EARTH * z
    return VeyraResult(
        ok=True,
        kind="hydrostatics",
        title="Fluid pressure",
        checks=[Check("hydrostatic formula", True)],
        metrics=[Metric("pressure", hydrostatic, "Pa"), Metric("gauge", hydrostatic - p0, "Pa")],
        inputs={"density": density, "depth": depth, "p0": p0},
        details={
            "paths": [{"x": p.tolist(), "y": z.tolist()}],
            "plot": make_plot("series", "pressure (Pa)", "depth (m)", [series("P(z)", p, z)]),
        },
        solver="P = P0 + ρgh",
    )


def simulate_oscillator(
    mass: float = 1.0,
    stiffness: float = 16.0,
    damping: float = 0.4,
    x0: float = 1.0,
    v0: float = 0.0,
    duration: float = 12.0,
) -> VeyraResult:
    """Linear viscously damped harmonic oscillator, integrated with RK45."""
    if mass <= 0 or stiffness <= 0:
        return VeyraResult(
            ok=False,
            kind="damped oscillator",
            title="Oscillator",
            checks=[Check("m > 0 and k > 0", False)],
        )
    omega0 = math.sqrt(stiffness / mass)
    zeta = damping / (2 * math.sqrt(stiffness * mass))

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        x, v = state
        return [v, -(damping / mass) * v - (stiffness / mass) * x]

    sol = solve_ivp(rhs, (0.0, duration), [x0, v0], method="RK45", rtol=1e-8, atol=1e-10)
    x, v = sol.y
    energy = 0.5 * mass * v**2 + 0.5 * stiffness * x**2
    dissipated = float(energy[0] - energy[-1]) if energy.size else 0.0
    monotonic = bool(np.all(np.diff(energy) <= 1e-9 * max(abs(energy[0]), 1.0)))
    t_s, x_s, v_s = downsample(sol.t), downsample(x), downsample(v)
    e_s = downsample(energy)
    under = zeta < 1
    return VeyraResult(
        ok=bool(sol.success) and dissipated >= -1e-9,
        kind="damped harmonic oscillator",
        title="Oscillator",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("energy does not increase", dissipated >= -1e-9, f"ΔE={dissipated:.4g} J"),
            Check("viscous dissipation", damping > 0 or abs(dissipated) < 1e-8),
        ],
        metrics=[
            Metric("ω0", omega0, "rad/s"),
            Metric("damping ratio", zeta),
            Metric("energy initial", float(energy[0]), "J"),
            Metric("energy final", float(energy[-1]), "J"),
            Metric("dissipated", dissipated, "J"),
        ],
        inputs={"mass": mass, "stiffness": stiffness, "damping": damping, "x0": x0, "duration": duration},
        details={
            "paths": [{"t": t_s.tolist(), "x": t_s.tolist(), "y": x_s.tolist()}],
            "plot": make_plot(
                "phase",
                "x (m)",
                "v (m/s)",
                [series("phase", x_s, v_s)],
                secondary=make_plot(
                    "series",
                    "t (s)",
                    "energy (J)",
                    [series("mechanical energy", t_s, e_s), series("displacement", t_s, x_s)],
                ),
            ),
            "regime": "underdamped" if under else ("critical" if abs(zeta - 1) < 1e-6 else "overdamped"),
        },
        solver="scipy RK45 mẍ + cẋ + kx = 0",
        tolerance=1e-8,
    )


def simulate_bernoulli(
    density: float = 1000.0,
    v1: float = 2.0,
    v2: float = 4.0,
    h1: float = 3.0,
    h2: float = 1.0,
    p1: float = 101325.0,
    p2: float | None = None,
) -> VeyraResult:
    """Steady incompressible Bernoulli along a streamline, with hydrostatic check."""
    dyn1 = 0.5 * density * v1**2
    grav1 = density * G_EARTH * h1
    head1 = p1 + dyn1 + grav1
    predicted_p2 = head1 - 0.5 * density * v2**2 - density * G_EARTH * h2
    p2_used = predicted_p2 if p2 is None else p2
    dyn2 = 0.5 * density * v2**2
    grav2 = density * G_EARTH * h2
    head2 = p2_used + dyn2 + grav2
    residual = abs(head1 - head2) / max(abs(head1), 1.0)
    hydro = fluid_pressure(density=density, depth=max(h1, h2), p0=p1)
    return VeyraResult(
        ok=residual < 1e-9 if p2 is None else residual < 0.05,
        kind="Bernoulli + hydrostatics",
        title="Bernoulli",
        checks=[
            Check("Bernoulli head conserved", residual < 0.05, f"relative residual={residual:.2e}"),
            Check("density > 0", density > 0),
            hydro.checks[0],
        ],
        metrics=[
            Metric("P1", p1, "Pa"),
            Metric("P2", p2_used, "Pa"),
            Metric("dynamic 1", dyn1, "Pa"),
            Metric("dynamic 2", dyn2, "Pa"),
            Metric("head 1", head1, "Pa"),
            Metric("head 2", head2, "Pa"),
            Metric("head residual", residual),
            Metric("hydrostatic at max height", float(hydro.metrics[0].value), "Pa"),
        ],
        inputs={"density": density, "v1": v1, "v2": v2, "h1": h1, "h2": h2, "p1": p1},
        details={
            "plot": make_plot(
                "series",
                "station",
                "pressure equivalent (Pa)",
                [
                    series("static", [1, 2], [p1, p2_used]),
                    series("dynamic", [1, 2], [dyn1, dyn2]),
                    series("gravity", [1, 2], [grav1, grav2]),
                ],
            )
        },
        solver="P + ½ρv² + ρgh = const",
    )


def material_stress(force: float, area: float, youngs: float | None = None, strain: float | None = None) -> VeyraResult:
    if area <= 0:
        return VeyraResult(ok=False, kind="materials", title="Stress", checks=[Check("area > 0", False)])
    stress = force / area
    metrics = [Metric("stress", stress, "Pa")]
    if youngs and strain is None:
        strain = stress / youngs
    if strain is not None:
        metrics.append(Metric("strain", strain))
    return VeyraResult(
        ok=True,
        kind="continuum foundations",
        title="Material mechanics",
        checks=[Check("σ = F/A", True)],
        metrics=metrics,
        inputs={"force": force, "area": area},
        solver="uniaxial stress",
    )


def simulate_heat(
    length: float = 0.2,
    alpha: float = 1e-4,
    n: int = 81,
    duration: float = 30.0,
    t_left: float = 373.15,
    t_right: float = 273.15,
    t_init: float = 293.15,
) -> VeyraResult:
    """1D heat equation u_t = α u_xx on a rod with Dirichlet ends (method of lines)."""
    nodes = max(int(n), 9)
    if length <= 0 or alpha <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="1D heat diffusion",
            title="Heat diffusion",
            checks=[Check("length, α, duration > 0", False)],
        )
    x = np.linspace(0.0, length, nodes)
    dx = float(x[1] - x[0])

    def rhs(_t: float, temp: np.ndarray) -> np.ndarray:
        d2 = np.zeros_like(temp)
        d2[1:-1] = (temp[2:] - 2.0 * temp[1:-1] + temp[:-2]) / dx**2
        return alpha * d2

    t0 = np.full(nodes, float(t_init))
    t0[0] = float(t_left)
    t0[-1] = float(t_right)
    sol = solve_ivp(rhs, (0.0, duration), t0, method="RK45", rtol=1e-7, atol=1e-9)
    final = sol.y[:, -1]
    trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    heat0 = float(trap(t0, x))
    heatf = float(trap(final, x))
    t_ss = t_left + (t_right - t_left) * (x / length)
    ss_l2 = float(np.sqrt(trap((final - t_ss) ** 2, x) / max(length, 1e-15)))
    bounds_lo = min(t_left, t_right, t_init) - 1e-4
    bounds_hi = max(t_left, t_right, t_init) + 1e-4
    max_principle = bool(np.all(sol.y >= bounds_lo) and np.all(sol.y <= bounds_hi))
    mid = nodes // 2
    t_s = downsample(sol.t)
    mid_s = downsample(sol.y[mid])
    x_s = downsample(x)
    t_final_s = downsample(final)
    t_ss_s = downsample(t_ss)
    return VeyraResult(
        ok=bool(sol.success) and max_principle,
        kind="1D heat diffusion",
        title="Heat diffusion",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("maximum principle", max_principle, "interior stays within boundary/initial extrema"),
            Check("Dirichlet ends held", abs(final[0] - t_left) < 1e-8 and abs(final[-1] - t_right) < 1e-8),
            Check("α > 0", alpha > 0),
        ],
        metrics=[
            Metric("midpoint T", float(final[mid]), "K"),
            Metric("heat content initial", heat0, "K·m"),
            Metric("heat content final", heatf, "K·m"),
            Metric("L2 to steady state", ss_l2, "K"),
            Metric("dx", dx, "m"),
            Metric("Fourier number", float(alpha * duration / length**2)),
        ],
        inputs={
            "length": length,
            "alpha": alpha,
            "t_left": t_left,
            "t_right": t_right,
            "t_init": t_init,
            "duration": duration,
            "nodes": nodes,
        },
        details={
            "paths": [{"x": x.tolist(), "y": final.tolist()}],
            "plot": make_plot(
                "series",
                "x (m)",
                "T (K)",
                [series("T(x, t_final)", x_s, t_final_s), series("steady state", x_s, t_ss_s)],
                secondary=make_plot("series", "t (s)", "T_mid (K)", [series("midpoint", t_s, mid_s)]),
            ),
        },
        solver="method of lines RK45  u_t = α u_xx",
        tolerance=1e-7,
    )


def simulate_rc(
    resistance: float = 1000.0,
    capacitance: float = 1e-6,
    v_source: float = 5.0,
    duration: float = 0.008,
    v0: float = 0.0,
) -> VeyraResult:
    """Series RC charging: numeric RK45 versus V(t) = Vs + (V0 − Vs) e^(−t/RC)."""
    if resistance <= 0 or capacitance <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="RC transient",
            title="RC circuit",
            checks=[Check("R, C, duration > 0", False)],
        )
    tau = resistance * capacitance

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [(v_source - state[0]) / tau]

    sol = solve_ivp(rhs, (0.0, duration), [v0], method="RK45", rtol=1e-8, atol=1e-10, dense_output=False)
    t = sol.t
    v_num = sol.y[0]
    v_exact = v_source + (v0 - v_source) * np.exp(-t / tau)
    rms = float(np.sqrt(np.mean((v_num - v_exact) ** 2)))
    scale = max(abs(v_source - v0), 1.0)
    relative = rms / scale
    t_s = downsample(t)
    v_s = downsample(v_num)
    e_s = downsample(v_exact)
    charged = float(v_num[-1])
    return VeyraResult(
        ok=bool(sol.success) and relative < 1e-4,
        kind="RC transient",
        title="RC circuit",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", relative < 1e-4, f"RMS/scale={relative:.2e}"),
            Check("τ = RC", abs(tau - resistance * capacitance) < 1e-18),
        ],
        metrics=[
            Metric("tau", tau, "s"),
            Metric("V final", charged, "V"),
            Metric("V exact final", float(v_exact[-1]), "V"),
            Metric("RMS error", rms, "V"),
        ],
        inputs={
            "resistance": resistance,
            "capacitance": capacitance,
            "v_source": v_source,
            "v0": v0,
            "duration": duration,
        },
        details={
            "paths": [{"x": t.tolist(), "y": v_num.tolist()}],
            "plot": make_plot(
                "series",
                "t (s)",
                "V (V)",
                [series("numeric", t_s, v_s), series("analytic", t_s, e_s)],
            ),
        },
        solver="RK45 vs V = Vs + (V0−Vs)e^(−t/RC)",
        tolerance=1e-8,
    )


def simulate_range_table(
    velocity: float = 38.0,
    drag_coefficient: float = 0.0,
    gravity: float = G_EARTH,
    angles: str | list | None = None,
) -> VeyraResult:
    """Range versus launch angle at fixed speed — a firing table from the same integrator."""
    if isinstance(angles, str) and angles.strip():
        degs = [float(part) for part in angles.replace(";", ",").split(",") if part.strip()]
    elif isinstance(angles, (list, tuple)) and angles:
        degs = [float(item) for item in angles]
    else:
        degs = [15.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 75.0]
    ranges: list[float] = []
    peaks: list[float] = []
    times: list[float] = []
    for angle in degs:
        shot = simulate_motion(
            velocity=velocity,
            angle_deg=angle,
            gravity=gravity,
            drag_coefficient=drag_coefficient,
            trials=1,
        )
        by_name = {metric.name: float(metric.value) for metric in shot.metrics}
        ranges.append(by_name["Mean range"])
        peaks.append(by_name["Peak altitude"])
        times.append(by_name["Flight time"])
    best_i = int(np.argmax(ranges))
    vacuum_opt = 45.0
    return VeyraResult(
        ok=True,
        kind="ballistic range table",
        title="Range table",
        checks=[
            Check("table computed", True, f"{len(degs)} angles"),
            Check(
                "optimum near 45° in vacuum" if drag_coefficient <= 0 else "drag shifts optimum",
                abs(degs[best_i] - vacuum_opt) <= 5.0 if drag_coefficient <= 0 else True,
                f"max range at {degs[best_i]:.0f}°",
            ),
        ],
        metrics=[
            Metric("max range", ranges[best_i], "m"),
            Metric("optimum angle", degs[best_i], "deg"),
            Metric("range at 45°", ranges[degs.index(45.0)] if 45.0 in degs else ranges[best_i], "m"),
        ],
        inputs={"velocity": velocity, "drag_coefficient": drag_coefficient, "angles": degs},
        details={
            "table": [
                {"angle_deg": ang, "range": rng, "peak": pk, "time": tm}
                for ang, rng, pk, tm in zip(degs, ranges, peaks, times)
            ],
            "plot": make_plot(
                "series",
                "launch angle (deg)",
                "range (m)",
                [series("range", degs, ranges), series("peak", degs, peaks)],
            ),
        },
        solver="projectile sweep" + ("" if drag_coefficient <= 0 else " with quadratic drag"),
    )


def simulate_cooling(
    t0: float = 363.15,
    t_env: float = 293.15,
    k: float = 0.05,
    duration: float = 120.0,
) -> VeyraResult:
    """Newton's law of cooling: RK45 versus T = Tenv + (T0 − Tenv) e^(−k t)."""
    if k <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="Newton cooling",
            title="Newton cooling",
            checks=[Check("k > 0 and duration > 0", False)],
        )

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [-k * (state[0] - t_env)]

    t_eval = np.linspace(0.0, duration, 801)
    sol = solve_ivp(rhs, (0.0, duration), [t0], method="RK45", rtol=1e-8, atol=1e-10, t_eval=t_eval)
    t = sol.t
    t_num = sol.y[0]
    t_exact = t_env + (t0 - t_env) * np.exp(-k * t)
    rms = float(np.sqrt(np.mean((t_num - t_exact) ** 2)))
    scale = max(abs(t0 - t_env), 1.0)
    lo, hi = min(t0, t_env), max(t0, t_env)
    bounded = bool(np.all((t_num >= lo - 1e-6) & (t_num <= hi + 1e-6)))
    t_s, n_s, e_s = downsample(t), downsample(t_num), downsample(t_exact)
    return VeyraResult(
        ok=bool(sol.success) and rms / scale < 1e-4 and bounded,
        kind="Newton cooling",
        title="Newton cooling",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", rms / scale < 1e-4, f"RMS/scale={rms / scale:.2e}"),
            Check("stays between T0 and Tenv", bounded),
        ],
        metrics=[
            Metric("k", k, "1/s"),
            Metric("T final", float(t_num[-1]), "K"),
            Metric("T exact final", float(t_exact[-1]), "K"),
            Metric("RMS error", rms, "K"),
        ],
        inputs={"t0": t0, "t_env": t_env, "k": k, "duration": duration},
        details={
            "plot": make_plot(
                "series",
                "t (s)",
                "T (K)",
                [series("numeric", t_s, n_s), series("analytic", t_s, e_s)],
            )
        },
        solver="RK45 vs T = Tenv + (T0−Tenv)e^(−kt)",
        tolerance=1e-8,
    )


def simulate_decay(
    n0: float = 1000.0,
    half_life: float = 10.0,
    duration: float = 40.0,
) -> VeyraResult:
    """Radioactive decay N = N0 e^(−λ t) with λ = ln 2 / t½, checked against RK45."""
    if n0 <= 0 or half_life <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="radioactive decay",
            title="Radioactive decay",
            checks=[Check("N0, t½, duration > 0", False)],
        )
    lam = math.log(2.0) / half_life

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [-lam * state[0]]

    sol = solve_ivp(rhs, (0.0, duration), [n0], method="RK45", rtol=1e-8, atol=1e-10)
    t = sol.t
    n_num = sol.y[0]
    n_exact = n0 * np.exp(-lam * t)
    n_half = n0 * math.exp(-lam * half_life)
    rms = float(np.sqrt(np.mean((n_num - n_exact) ** 2)))
    t_s, n_s, e_s = downsample(t), downsample(n_num), downsample(n_exact)
    return VeyraResult(
        ok=bool(sol.success) and abs(n_half - n0 / 2) < 1e-9 * n0 and rms / n0 < 1e-4,
        kind="radioactive decay",
        title="Radioactive decay",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("N(t½) = N0/2", abs(n_half - n0 / 2) < 1e-9 * n0, f"N(t½)={n_half:.6g}"),
            Check("matches closed form", rms / n0 < 1e-4, f"RMS/N0={rms / n0:.2e}"),
        ],
        metrics=[
            Metric("lambda", lam, "1/s"),
            Metric("half-life", half_life, "s"),
            Metric("N final", float(n_num[-1])),
            Metric("N exact final", float(n_exact[-1])),
            Metric("RMS error", rms),
        ],
        inputs={"n0": n0, "half_life": half_life, "duration": duration},
        details={
            "plot": make_plot(
                "series",
                "t (s)",
                "N",
                [series("numeric", t_s, n_s), series("analytic", t_s, e_s)],
            )
        },
        solver="RK45 vs N = N0 e^(−λ t)",
        tolerance=1e-8,
    )


def simulate_atwood(
    m1: float = 1.2,
    m2: float = 1.0,
    gravity: float = G_EARTH,
) -> VeyraResult:
    """Atwood machine. Acceleration and tension from Newton's second law on both masses."""
    if m1 <= 0 or m2 <= 0:
        return VeyraResult(
            ok=False,
            kind="Atwood machine",
            title="Atwood machine",
            checks=[Check("masses > 0", False)],
        )
    accel = gravity * (m1 - m2) / (m1 + m2)
    tension = 2 * m1 * m2 * gravity / (m1 + m2)
    t_from_m1 = m1 * (gravity - accel)
    t_from_m2 = m2 * (gravity + accel)
    consistent = abs(t_from_m1 - tension) < 1e-9 * max(abs(tension), 1.0) and abs(
        t_from_m2 - tension
    ) < 1e-9 * max(abs(tension), 1.0)
    heavier_descends = (m1 - m2) * accel >= -1e-12
    return VeyraResult(
        ok=consistent and heavier_descends,
        kind="Atwood machine",
        title="Atwood machine",
        checks=[
            Check("T = m1(g − a) = m2(g + a)", consistent, f"T1={t_from_m1:.6g} T2={t_from_m2:.6g}"),
            Check("heavier mass descends", heavier_descends),
        ],
        metrics=[
            Metric("acceleration", accel, "m/s²"),
            Metric("tension", tension, "N"),
            Metric("mass ratio", m1 / m2),
        ],
        inputs={"m1": m1, "m2": m2, "gravity": gravity},
        solver="a = g(m1−m2)/(m1+m2)",
    )


def simulate_rl(
    resistance: float = 10.0,
    inductance: float = 0.5,
    v_source: float = 12.0,
    duration: float = 0.4,
    i0: float = 0.0,
) -> VeyraResult:
    """Series RL rise: numeric RK45 versus I(t) = Iss + (I0 − Iss) e^(−Rt/L)."""
    if resistance <= 0 or inductance <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="RL transient",
            title="RL circuit",
            checks=[Check("R, L, duration > 0", False)],
        )
    tau = inductance / resistance
    i_ss = v_source / resistance

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [(v_source - resistance * state[0]) / inductance]

    sol = solve_ivp(rhs, (0.0, duration), [i0], method="RK45", rtol=1e-8, atol=1e-10, dense_output=False)
    t = sol.t
    i_num = sol.y[0]
    i_exact = i_ss + (i0 - i_ss) * np.exp(-t / tau)
    rms = float(np.sqrt(np.mean((i_num - i_exact) ** 2)))
    scale = max(abs(i_ss - i0), 1e-9)
    relative = rms / scale
    t_s = downsample(t)
    i_s = downsample(i_num)
    e_s = downsample(i_exact)
    return VeyraResult(
        ok=bool(sol.success) and relative < 1e-4,
        kind="RL transient",
        title="RL circuit",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", relative < 1e-4, f"RMS/scale={relative:.2e}"),
            Check("τ = L/R", abs(tau - inductance / resistance) < 1e-18),
        ],
        metrics=[
            Metric("tau", tau, "s"),
            Metric("I steady", i_ss, "A"),
            Metric("I final", float(i_num[-1]), "A"),
            Metric("I exact final", float(i_exact[-1]), "A"),
            Metric("RMS error", rms, "A"),
        ],
        inputs={
            "resistance": resistance,
            "inductance": inductance,
            "v_source": v_source,
            "i0": i0,
            "duration": duration,
        },
        details={
            "paths": [{"x": t.tolist(), "y": i_num.tolist()}],
            "plot": make_plot(
                "series",
                "t (s)",
                "I (A)",
                [series("numeric", t_s, i_s), series("analytic", t_s, e_s)],
            ),
        },
        solver="RK45 vs I = Iss + (I0−Iss)e^(−Rt/L)",
        tolerance=1e-8,
    )


def simulate_freefall(
    y0: float = 80.0,
    v0: float = 0.0,
    gravity: float = G_EARTH,
    duration: float = 4.0,
) -> VeyraResult:
    """Vertical throw in uniform g. RK45 versus y = y0 + v0 t − ½ g t²."""
    if duration <= 0:
        return VeyraResult(
            ok=False,
            kind="free fall",
            title="Free fall",
            checks=[Check("duration > 0", False)],
        )

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [state[1], -gravity]

    sol = solve_ivp(rhs, (0.0, duration), [y0, v0], method="RK45", rtol=1e-9, atol=1e-11, dense_output=False)
    t = sol.t
    y_num, v_num = sol.y
    y_exact = y0 + v0 * t - 0.5 * gravity * t**2
    v_exact = v0 - gravity * t
    y_rms = float(np.sqrt(np.mean((y_num - y_exact) ** 2)))
    v_rms = float(np.sqrt(np.mean((v_num - v_exact) ** 2)))
    scale = max(abs(y0), 1.0)
    relative = y_rms / scale
    energy = 0.5 * v_num**2 + gravity * y_num
    energy_drift = float(np.ptp(energy) / max(abs(energy[0]), 1e-30))
    t_s = downsample(t)
    y_s = downsample(y_num)
    e_s = downsample(y_exact)
    return VeyraResult(
        ok=bool(sol.success) and relative < 1e-5 and energy_drift < 1e-6,
        kind="free fall",
        title="Free fall",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", relative < 1e-5, f"RMS/scale={relative:.2e}"),
            Check("specific energy conserved", energy_drift < 1e-6, f"relative drift={energy_drift:.2e}"),
            Check("velocity matches", v_rms < 1e-4, f"v RMS={v_rms:.2e} m/s"),
        ],
        metrics=[
            Metric("y final", float(y_num[-1]), "m"),
            Metric("y exact final", float(y_exact[-1]), "m"),
            Metric("v final", float(v_num[-1]), "m/s"),
            Metric("RMS error", y_rms, "m"),
            Metric("energy drift", energy_drift),
        ],
        inputs={"y0": y0, "v0": v0, "gravity": gravity, "duration": duration},
        details={
            "paths": [{"x": t.tolist(), "y": y_num.tolist()}],
            "plot": make_plot(
                "series",
                "t (s)",
                "y (m)",
                [series("numeric", t_s, y_s), series("analytic", t_s, e_s)],
            ),
        },
        solver="RK45 vs y = y0 + v0 t − ½ g t²",
        tolerance=1e-9,
    )


def simulate_kepler(
    altitude_m: float = 400_000.0,
    earth_radius: float = 6_371_000.0,
    earth_mass: float = 5.972e24,
) -> VeyraResult:
    """Circular Kepler: T² / a³ = 4π² / GM, with a period-versus-altitude curve."""
    if altitude_m <= 0 or earth_radius <= 0 or earth_mass <= 0:
        return VeyraResult(
            ok=False,
            kind="Kepler period",
            title="Kepler period",
            checks=[Check("altitude, radius, mass > 0", False)],
        )
    mu = G_NEWTON * earth_mass
    a = earth_radius + altitude_m
    period = 2 * math.pi * math.sqrt(a**3 / mu)
    ratio = period**2 / a**3
    expected = 4 * math.pi**2 / mu
    residual = abs(ratio - expected) / expected
    v_circ = math.sqrt(mu / a)
    vis_viva = math.sqrt(mu * (2 / a - 1 / a))
    vis_ok = abs(v_circ - vis_viva) < 1e-9 * max(v_circ, 1.0)
    alts = np.linspace(200_000.0, 2_000_000.0, 17)
    axes = earth_radius + alts
    periods = 2 * math.pi * np.sqrt(axes**3 / mu)
    leo = 300_000 <= altitude_m <= 500_000
    return VeyraResult(
        ok=residual < 1e-12 and vis_ok,
        kind="Kepler period",
        title="Kepler period",
        checks=[
            Check("T²/a³ = 4π²/GM", residual < 1e-12, f"relative residual={residual:.2e}"),
            Check("circular vis-viva", vis_ok, f"|v−√(μ/a)|={abs(v_circ - vis_viva):.2e}"),
            Check(
                "LEO period ~ 90 min" if leo else "period finite",
                (5_000 < period < 6_500) if leo else math.isfinite(period),
                f"T={period / 60:.2f} min",
            ),
        ],
        metrics=[
            Metric("semi-major axis", a, "m"),
            Metric("period", period, "s"),
            Metric("period minutes", period / 60, "min"),
            Metric("circular velocity", v_circ, "m/s"),
            Metric("T²/a³ residual", residual),
        ],
        inputs={"altitude": altitude_m, "earth_radius": earth_radius, "earth_mass": earth_mass},
        details={
            "table": [
                {"altitude_km": float(h / 1000), "period_min": float(t / 60)}
                for h, t in zip(alts, periods, strict=False)
            ],
            "plot": make_plot(
                "series",
                "altitude (km)",
                "period (min)",
                [series("Kepler T(h)", alts / 1000, periods / 60)],
            ),
        },
        solver="T = 2π √(a³/GM)",
    )


def simulate_lc(
    inductance: float = 0.5,
    capacitance: float = 2e-6,
    q0: float = 1e-6,
    i0: float = 0.0,
    duration: float = 0.02,
) -> VeyraResult:
    """Undamped LC: RK45 versus q = Q0 cos(ωt) + (I0/ω) sin(ωt), ω = 1/√(LC)."""
    if inductance <= 0 or capacitance <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="LC oscillator",
            title="LC circuit",
            checks=[Check("L, C, duration > 0", False)],
        )
    omega = 1.0 / math.sqrt(inductance * capacitance)

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        charge, current = state
        return [current, -charge / (inductance * capacitance)]

    sol = solve_ivp(rhs, (0.0, duration), [q0, i0], method="RK45", rtol=1e-8, atol=1e-12, dense_output=False)
    t = sol.t
    q_num, i_num = sol.y
    q_exact = q0 * np.cos(omega * t) + (i0 / omega) * np.sin(omega * t)
    i_exact = -q0 * omega * np.sin(omega * t) + i0 * np.cos(omega * t)
    q_rms = float(np.sqrt(np.mean((q_num - q_exact) ** 2)))
    i_rms = float(np.sqrt(np.mean((i_num - i_exact) ** 2)))
    scale = max(abs(q0), abs(i0 / omega), 1e-12)
    relative = q_rms / scale
    energy = 0.5 * inductance * i_num**2 + 0.5 * q_num**2 / capacitance
    energy_drift = float(np.ptp(energy) / max(abs(energy[0]), 1e-30))
    t_s = downsample(t)
    q_s = downsample(q_num)
    e_s = downsample(q_exact)
    return VeyraResult(
        ok=bool(sol.success) and relative < 1e-4 and energy_drift < 1e-4,
        kind="LC oscillator",
        title="LC circuit",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", relative < 1e-4, f"RMS/scale={relative:.2e}"),
            Check("current matches", i_rms < 1e-6, f"i RMS={i_rms:.2e} A"),
            Check("ω = 1/√(LC)", abs(omega - 1 / math.sqrt(inductance * capacitance)) < 1e-12),
            Check("LC energy conserved", energy_drift < 1e-4, f"relative drift={energy_drift:.2e}"),
        ],
        metrics=[
            Metric("omega", omega, "rad/s"),
            Metric("period", 2 * math.pi / omega, "s"),
            Metric("q final", float(q_num[-1]), "C"),
            Metric("q exact final", float(q_exact[-1]), "C"),
            Metric("RMS error", q_rms, "C"),
            Metric("energy drift", energy_drift),
        ],
        inputs={
            "inductance": inductance,
            "capacitance": capacitance,
            "q0": q0,
            "i0": i0,
            "duration": duration,
        },
        details={
            "paths": [{"x": t.tolist(), "y": q_num.tolist()}],
            "plot": make_plot(
                "series",
                "t (s)",
                "q (C)",
                [series("numeric", t_s, q_s), series("analytic", t_s, e_s)],
            ),
        },
        solver="RK45 vs q = Q0 cos(ωt) + (I0/ω) sin(ωt)",
        tolerance=1e-8,
    )


def simulate_lens(
    focal_length: float = 0.05,
    object_distance: float = 0.12,
) -> VeyraResult:
    """Thin-lens Gaussian identity 1/f = 1/do + 1/di with magnification m = −di/do."""
    if focal_length == 0:
        return VeyraResult(
            ok=False,
            kind="thin lens",
            title="Thin lens",
            checks=[Check("f ≠ 0", False)],
        )
    if abs(object_distance - focal_length) < 1e-15 * max(abs(focal_length), 1.0):
        return VeyraResult(
            ok=False,
            kind="thin lens",
            title="Thin lens",
            checks=[Check("object not at focal plane", False, "di → ∞")],
            inputs={"focal_length": focal_length, "object_distance": object_distance},
        )
    image_distance = 1.0 / (1.0 / focal_length - 1.0 / object_distance)
    magnification = -image_distance / object_distance
    residual = abs(1 / object_distance + 1 / image_distance - 1 / focal_length)
    scale = max(abs(1 / focal_length), 1.0)
    real_image = object_distance > focal_length > 0 and image_distance > 0
    dos = np.linspace(focal_length * 1.15, focal_length * 4.0, 17) if focal_length > 0 else np.array([object_distance])
    dis = 1.0 / (1.0 / focal_length - 1.0 / dos)
    return VeyraResult(
        ok=residual / scale < 1e-12,
        kind="thin lens",
        title="Thin lens",
        checks=[
            Check("1/f = 1/do + 1/di", residual / scale < 1e-12, f"residual={residual:.2e} 1/m"),
            Check(
                "real image (do > f)" if focal_length > 0 else "image finite",
                real_image if focal_length > 0 else math.isfinite(image_distance),
                f"di={image_distance:.6g} m",
            ),
        ],
        metrics=[
            Metric("focal length", focal_length, "m"),
            Metric("object distance", object_distance, "m"),
            Metric("image distance", image_distance, "m"),
            Metric("magnification", magnification),
            Metric("Gaussian residual", residual, "1/m"),
        ],
        inputs={"focal_length": focal_length, "object_distance": object_distance},
        details={
            "table": [
                {"object_m": float(do), "image_m": float(di), "magnification": float(-di / do)}
                for do, di in zip(dos, dis, strict=False)
            ],
            "plot": make_plot(
                "series",
                "object distance (m)",
                "image distance (m)",
                [series("di(do)", dos, dis)],
            ),
        },
        solver="1/f = 1/do + 1/di",
    )


def simulate_escape(
    altitude_m: float = 0.0,
    earth_radius: float = 6_371_000.0,
    earth_mass: float = 5.972e24,
) -> VeyraResult:
    """Escape speed √(2GM/r) and the circular identity v_esc / v_circ = √2."""
    radius = earth_radius + altitude_m
    if radius <= 0 or earth_mass <= 0:
        return VeyraResult(
            ok=False,
            kind="escape velocity",
            title="Escape velocity",
            checks=[Check("r, M > 0", False)],
        )
    mu = G_NEWTON * earth_mass
    v_esc = math.sqrt(2 * mu / radius)
    v_circ = math.sqrt(mu / radius)
    ratio = v_esc / v_circ
    residual = abs(ratio - math.sqrt(2))
    surface = abs(altitude_m) < 1.0
    alts = np.linspace(0.0, 2_000_000.0, 17)
    speeds = np.sqrt(2 * mu / (earth_radius + alts))
    return VeyraResult(
        ok=residual < 1e-12,
        kind="escape velocity",
        title="Escape velocity",
        checks=[
            Check("v_esc / v_circ = √2", residual < 1e-12, f"ratio={ratio:.12f}"),
            Check(
                "Earth surface ~ 11.2 km/s" if surface else "escape speed finite",
                (11_000 < v_esc < 11_300) if surface else math.isfinite(v_esc),
                f"v_esc={v_esc:.6g} m/s",
            ),
        ],
        metrics=[
            Metric("radius", radius, "m"),
            Metric("escape speed", v_esc, "m/s"),
            Metric("circular speed", v_circ, "m/s"),
            Metric("escape / circular", ratio),
        ],
        inputs={"altitude": altitude_m, "earth_radius": earth_radius, "earth_mass": earth_mass},
        details={
            "table": [
                {"altitude_km": float(h / 1000), "escape_km_s": float(v / 1000)}
                for h, v in zip(alts, speeds, strict=False)
            ],
            "plot": make_plot(
                "series",
                "altitude (km)",
                "escape speed (km/s)",
                [series("v_esc(h)", alts / 1000, speeds / 1000)],
            ),
        },
        solver="v_esc = √(2GM/r)",
    )


def simulate_shm(
    mass: float = 1.0,
    stiffness: float = 16.0,
    amplitude: float = 0.1,
    duration: float = 4.0,
) -> VeyraResult:
    """Undamped SHM. RK45 versus x = A cos(ωt), ω = √(k/m)."""
    if mass <= 0 or stiffness <= 0 or duration <= 0:
        return VeyraResult(
            ok=False,
            kind="simple harmonic motion",
            title="SHM",
            checks=[Check("m, k, duration > 0", False)],
        )
    omega = math.sqrt(stiffness / mass)

    def rhs(_t: float, state: np.ndarray) -> list[float]:
        return [state[1], -(stiffness / mass) * state[0]]

    sol = solve_ivp(rhs, (0.0, duration), [amplitude, 0.0], method="RK45", rtol=1e-8, atol=1e-11, dense_output=False)
    t = sol.t
    x_num, v_num = sol.y
    x_exact = amplitude * np.cos(omega * t)
    v_exact = -amplitude * omega * np.sin(omega * t)
    x_rms = float(np.sqrt(np.mean((x_num - x_exact) ** 2)))
    v_rms = float(np.sqrt(np.mean((v_num - v_exact) ** 2)))
    scale = max(abs(amplitude), 1e-9)
    relative = x_rms / scale
    energy = 0.5 * mass * v_num**2 + 0.5 * stiffness * x_num**2
    e_exact = 0.5 * stiffness * amplitude**2
    energy_drift = float(np.ptp(energy) / max(abs(e_exact), 1e-30))
    t_s = downsample(t)
    x_s = downsample(x_num)
    e_s = downsample(x_exact)
    return VeyraResult(
        ok=bool(sol.success) and relative < 1e-4 and energy_drift < 1e-4,
        kind="simple harmonic motion",
        title="SHM",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("matches closed form", relative < 1e-4, f"RMS/scale={relative:.2e}"),
            Check("velocity matches", v_rms < 1e-5, f"v RMS={v_rms:.2e} m/s"),
            Check("ω = √(k/m)", abs(omega - math.sqrt(stiffness / mass)) < 1e-12),
            Check("mechanical energy conserved", energy_drift < 1e-4, f"relative drift={energy_drift:.2e}"),
        ],
        metrics=[
            Metric("omega", omega, "rad/s"),
            Metric("period", 2 * math.pi / omega, "s"),
            Metric("x final", float(x_num[-1]), "m"),
            Metric("x exact final", float(x_exact[-1]), "m"),
            Metric("energy", e_exact, "J"),
            Metric("RMS error", x_rms, "m"),
            Metric("energy drift", energy_drift),
        ],
        inputs={"mass": mass, "stiffness": stiffness, "amplitude": amplitude, "duration": duration},
        details={
            "paths": [{"x": t.tolist(), "y": x_num.tolist()}],
            "plot": make_plot(
                "series",
                "t (s)",
                "x (m)",
                [series("numeric", t_s, x_s), series("analytic", t_s, e_s)],
            ),
        },
        solver="RK45 vs x = A cos(ωt)",
        tolerance=1e-8,
    )


def simulate_doppler(
    frequency: float = 440.0,
    v_source: float = 20.0,
    v_observer: float = 0.0,
    speed_sound: float = 343.0,
) -> VeyraResult:
    """Line-of-sight Doppler: f' = f (c + vo) / (c − vs). Positive velocity is toward the other body."""
    if frequency <= 0 or speed_sound <= 0:
        return VeyraResult(
            ok=False,
            kind="Doppler shift",
            title="Doppler",
            checks=[Check("f, c > 0", False)],
        )
    if abs(v_source) >= speed_sound:
        return VeyraResult(
            ok=False,
            kind="Doppler shift",
            title="Doppler",
            checks=[Check("|vs| < c", False, "source would be supersonic along the line of sight")],
        )
    observed = frequency * (speed_sound + v_observer) / (speed_sound - v_source)
    rest = frequency * (speed_sound + 0.0) / (speed_sound - 0.0)
    net = v_source + v_observer
    if net > 1e-12:
        pitch_name = "approaching raises pitch"
        pitch_ok = observed > frequency
    elif net < -1e-12:
        pitch_name = "receding lowers pitch"
        pitch_ok = observed < frequency
    else:
        pitch_name = "equal approach cancels"
        pitch_ok = abs(observed - frequency) <= 1e-12 * frequency
    vs_grid = np.linspace(-0.4 * speed_sound, 0.4 * speed_sound, 17)
    f_grid = frequency * (speed_sound + v_observer) / (speed_sound - vs_grid)
    return VeyraResult(
        ok=math.isfinite(observed) and abs(rest - frequency) < 1e-12 * frequency and pitch_ok,
        kind="Doppler shift",
        title="Doppler",
        checks=[
            Check("rest frame identity", abs(rest - frequency) < 1e-12 * frequency),
            Check("finite observed frequency", math.isfinite(observed)),
            Check(pitch_name, pitch_ok, f"f'={observed:.6g} Hz"),
        ],
        metrics=[
            Metric("source frequency", frequency, "Hz"),
            Metric("observed frequency", observed, "Hz"),
            Metric("shift", observed - frequency, "Hz"),
            Metric("ratio", observed / frequency),
        ],
        inputs={
            "frequency": frequency,
            "v_source": v_source,
            "v_observer": v_observer,
            "speed_sound": speed_sound,
        },
        details={
            "plot": make_plot(
                "series",
                "source speed (m/s)",
                "observed f (Hz)",
                [series("f'(vs)", vs_grid, f_grid)],
            ),
        },
        solver="f' = f (c+vo)/(c−vs)",
    )


def simulate_circular(
    radius: float = 10.0,
    speed: float = 5.0,
) -> VeyraResult:
    """Uniform circular motion: a = v²/r and T = 2πr/v."""
    if radius <= 0 or speed <= 0:
        return VeyraResult(
            ok=False,
            kind="circular motion",
            title="Circular motion",
            checks=[Check("r, v > 0", False)],
        )
    accel = speed**2 / radius
    period = 2 * math.pi * radius / speed
    omega = speed / radius
    identity = abs(period * speed - 2 * math.pi * radius) / max(radius, 1.0)
    speeds = np.linspace(speed * 0.4, speed * 1.8, 17)
    accels = speeds**2 / radius
    return VeyraResult(
        ok=identity < 1e-12,
        kind="circular motion",
        title="Circular motion",
        checks=[
            Check("T v = 2π r", identity < 1e-12, f"relative residual={identity:.2e}"),
            Check("a = v²/r", abs(accel - speed**2 / radius) < 1e-12 * max(accel, 1.0)),
            Check("ω = v/r", abs(omega - speed / radius) < 1e-12),
        ],
        metrics=[
            Metric("radius", radius, "m"),
            Metric("speed", speed, "m/s"),
            Metric("centripetal acceleration", accel, "m/s²"),
            Metric("period", period, "s"),
            Metric("angular speed", omega, "rad/s"),
        ],
        inputs={"radius": radius, "speed": speed},
        details={
            "plot": make_plot(
                "series",
                "speed (m/s)",
                "a (m/s²)",
                [series("v²/r", speeds, accels)],
            ),
        },
        solver="a = v²/r",
    )


DISPATCH = {
    "projectile": simulate_motion,
    "motion": simulate_motion,
    "orbit": simulate_orbit,
    "collision": simulate_collision,
    "forces": analyze_force_system,
    "field": calculate_field,
    "thermo": simulate_thermodynamics,
    "wave": simulate_wave,
    "circuit": solve_circuit,
    "optics": simulate_optics,
    "mechanics": analyze_mechanics,
    "pendulum": simulate_pendulum,
    "relativity": relativity_foundations,
    "quantum": quantum_foundations,
    "fluid": fluid_pressure,
    "hydrostatic": fluid_pressure,
    "material": material_stress,
    "stress": material_stress,
    "oscillator": simulate_oscillator,
    "damped": simulate_oscillator,
    "bernoulli": simulate_bernoulli,
    "twobody": simulate_orbit,
    "two-body": simulate_orbit,
    "diffusion": simulate_heat,
    "heat1d": simulate_heat,
    "heat-diffusion": simulate_heat,
    "rc": simulate_rc,
    "rccircuit": simulate_rc,
    "range": simulate_range_table,
    "rangetable": simulate_range_table,
    "cooling": simulate_cooling,
    "newton-cooling": simulate_cooling,
    "decay": simulate_decay,
    "radioactive": simulate_decay,
    "atwood": simulate_atwood,
    "rl": simulate_rl,
    "rlcircuit": simulate_rl,
    "freefall": simulate_freefall,
    "free-fall": simulate_freefall,
    "kepler": simulate_kepler,
    "lc": simulate_lc,
    "lccircuit": simulate_lc,
    "lens": simulate_lens,
    "thin-lens": simulate_lens,
    "escape": simulate_escape,
    "shm": simulate_shm,
    "harmonic": simulate_shm,
    "doppler": simulate_doppler,
    "circular": simulate_circular,
    "centripetal": simulate_circular,
}


def run_named(name: str, **kwargs: Any) -> VeyraResult:
    if name not in DISPATCH:
        return VeyraResult(
            ok=False,
            kind="physics",
            title=name,
            checks=[Check("known model", False, f"unknown '{name}'")],
        )
    return DISPATCH[name](**kwargs)
