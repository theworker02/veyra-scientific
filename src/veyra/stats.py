"""Statistics, uncertainty, fitting, and Monte Carlo."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from scipy import stats as scipy_stats
from scipy.optimize import curve_fit

from veyra.core import Check, Metric, VeyraResult
from veyra.plots import make_plot, series


def propagate_uncertainty(
    expression: str,
    variables: dict[str, tuple[float, float]],
    trials: int = 20_000,
    seed: int = 0,
) -> VeyraResult:
    """Monte Carlo uncertainty propagation for a scalar expression."""
    rng = np.random.default_rng(seed)
    samples = {name: rng.normal(mean, std, trials) for name, (mean, std) in variables.items()}
    env = {"np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan, "sqrt": np.sqrt, "exp": np.exp, "log": np.log}
    env.update(samples)
    values = eval(expression, {"__builtins__": {}}, env)  # noqa: S307
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    lo, hi = np.percentile(values, [2.5, 97.5])
    return VeyraResult(
        ok=np.isfinite(values).all(),
        kind="uncertainty propagation",
        title="Monte Carlo uncertainty",
        checks=[
            Check("finite samples", bool(np.isfinite(values).all())),
            Check("trials completed", True, f"{trials}"),
        ],
        metrics=[
            Metric("mean", mean),
            Metric("std", std),
            Metric("ci95_low", float(lo)),
            Metric("ci95_high", float(hi)),
        ],
        inputs={"expression": expression, "variables": variables, "trials": trials},
        seed=seed,
        iterations=trials,
        solver="Monte Carlo",
    )


def monte_carlo(
    sampler: str = "normal",
    n: int = 10_000,
    seed: int = 0,
    **params: float,
) -> VeyraResult:
    rng = np.random.default_rng(seed)
    if sampler == "uniform":
        values = rng.uniform(params.get("low", 0.0), params.get("high", 1.0), n)
    elif sampler == "pi":
        x, y = rng.uniform(-1, 1, n), rng.uniform(-1, 1, n)
        values = ((x**2 + y**2) <= 1).astype(float)
        estimate = 4 * float(values.mean())
        return VeyraResult(
            ok=True,
            kind="Monte Carlo",
            title="π estimate",
            checks=[Check("samples drawn", True)],
            metrics=[Metric("pi", estimate), Metric("error", abs(estimate - np.pi))],
            seed=seed,
            iterations=n,
            solver="unit-circle hit-or-miss",
        )
    else:
        values = rng.normal(params.get("mean", 0.0), params.get("std", 1.0), n)
    return VeyraResult(
        ok=True,
        kind="Monte Carlo",
        title="Sample",
        checks=[Check("samples drawn", True)],
        metrics=[
            Metric("mean", float(values.mean())),
            Metric("std", float(values.std(ddof=1))),
        ],
        seed=seed,
        iterations=n,
        solver=sampler,
    )


def fit_model(
    x: list[float],
    y: list[float],
    model: str = "linear",
) -> VeyraResult:
    xv = np.array(x, dtype=float)
    yv = np.array(y, dtype=float)
    if model == "quadratic":

        def fn(t, a, b, c):
            return a * t**2 + b * t + c

        p0 = (1.0, 1.0, 0.0)
        names = ["a", "b", "c"]
    elif model == "exponential":

        def fn(t, a, b):
            return a * np.exp(b * t)

        p0 = (1.0, 0.0)
        names = ["a", "b"]
    else:

        def fn(t, a, b):
            return a * t + b

        p0 = (1.0, 0.0)
        names = ["slope", "intercept"]
    popt, pcov = curve_fit(fn, xv, yv, p0=p0, maxfev=10_000)
    pred = fn(xv, *popt)
    ss_res = float(np.sum((yv - pred) ** 2))
    ss_tot = float(np.sum((yv - yv.mean()) ** 2)) or 1.0
    r2 = 1 - ss_res / ss_tot
    perr = np.sqrt(np.diag(pcov))
    return VeyraResult(
        ok=r2 > 0,
        kind="model fit",
        title=f"{model} fit",
        checks=[Check("fit converged", True), Check("R² computed", True)],
        metrics=[Metric(name, float(val), uncertainty=float(err)) for name, val, err in zip(names, popt, perr)]
        + [Metric("r_squared", r2), Metric("rmse", float(np.sqrt(ss_res / len(xv))))],
        inputs={"n": len(x), "model": model},
        details={
            "parameters": dict(zip(names, map(float, popt))),
            "residuals": (yv - pred).tolist(),
            "x": xv.tolist(),
            "y": yv.tolist(),
            "y_hat": pred.tolist(),
            "plot": make_plot(
                "residuals",
                "x",
                "y",
                [
                    series("observations", xv, yv),
                    series("fit", np.linspace(float(xv.min()), float(xv.max()), 80),
                           fn(np.linspace(float(xv.min()), float(xv.max()), 80), *popt)),
                ],
                secondary=make_plot(
                    "series",
                    "x",
                    "residual",
                    [series("residual", xv, yv - pred)],
                ),
            ),
        },
        solver="scipy.optimize.curve_fit",
    )


def sensitivity_analysis(
    expression: str,
    variables: dict[str, float],
    delta: float = 1e-4,
) -> VeyraResult:
    def evaluate(values: dict[str, float]) -> float:
        env = {"np": np, "sin": np.sin, "cos": np.cos, "sqrt": np.sqrt, **values}
        return float(eval(expression, {"__builtins__": {}}, env))  # noqa: S307

    base = evaluate(variables)
    metrics = [Metric("base", base)]
    for name, value in variables.items():
        step = delta if value == 0 else abs(value) * delta
        plus = dict(variables)
        plus[name] = value + step
        deriv = (evaluate(plus) - base) / step
        elasticity = deriv * value / base if base != 0 else deriv
        metrics.append(Metric(f"d/d{name}", deriv))
        metrics.append(Metric(f"elasticity {name}", elasticity))
    return VeyraResult(
        ok=True,
        kind="sensitivity",
        title="Sensitivity analysis",
        checks=[Check("finite differences", True)],
        metrics=metrics,
        inputs={"expression": expression, "variables": variables, "delta": delta},
        solver="forward difference",
        tolerance=delta,
    )


def compare_results(
    a: float,
    b: float,
    tolerance: float = 1e-6,
    relative: bool = True,
) -> VeyraResult:
    diff = abs(a - b)
    scale = max(abs(a), abs(b), 1e-15)
    err = diff / scale if relative else diff
    return VeyraResult(
        ok=err <= tolerance,
        kind="comparison",
        title="Compare results",
        checks=[Check("within tolerance", err <= tolerance, f"error={err:.3e}")],
        metrics=[Metric("a", a), Metric("b", b), Metric("error", err)],
        inputs={"tolerance": tolerance, "relative": relative},
        tolerance=tolerance,
    )


def probability_check(values: list[float], name: str = "distribution") -> VeyraResult:
    arr = np.array(values, dtype=float)
    total = float(arr.sum())
    nonneg = bool(np.all(arr >= -1e-15))
    return VeyraResult(
        ok=nonneg and abs(total - 1) < 1e-8,
        kind="probability",
        title=name,
        checks=[
            Check("non-negative", nonneg),
            Check("sums to 1", abs(total - 1) < 1e-8, f"sum={total:.8f}"),
        ],
        metrics=[Metric("sum", total), Metric("entropy", float(scipy_stats.entropy(np.clip(arr, 1e-15, None))))],
        inputs={"n": len(values)},
        solver="probability axioms",
    )


def numerical_stability(matrix: list[list[float]] | None = None, values: list[float] | None = None) -> VeyraResult:
    checks: list[Check] = []
    metrics: list[Metric] = []
    if matrix is not None:
        a = np.array(matrix, dtype=float)
        condition = float(np.linalg.cond(a)) if a.size else math_inf()
        checks.append(Check("well-conditioned", condition < 1e10, f"cond={condition:.3e}"))
        metrics.append(Metric("condition number", condition))
    if values is not None:
        arr = np.array(values, dtype=float)
        finite = bool(np.isfinite(arr).all())
        checks.append(Check("finite values", finite))
        if arr.size:
            metrics.append(Metric("dynamic range", float(np.nanmax(np.abs(arr)) / max(np.nanmin(np.abs(arr[arr != 0])), 1e-300))))
    return VeyraResult(
        ok=all(c.passed for c in checks) if checks else True,
        kind="numerical stability",
        title="Stability",
        checks=checks or [Check("nothing to check", True)],
        metrics=metrics,
        solver="condition number / finiteness",
    )


def math_inf() -> float:
    return float("inf")


def wrap_callable(fn: Callable[..., float], **kwargs: Any) -> float:
    return float(fn(**kwargs))
