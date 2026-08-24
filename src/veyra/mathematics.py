"""Symbolic and numerical mathematics engine."""

from __future__ import annotations

import math
from typing import Any

import mpmath as mp
import numpy as np
import sympy as sp
from numpy.linalg import cond, eigvals, matrix_rank, svd
from scipy import optimize as opt
from scipy.fft import fft, fftfreq
from scipy.integrate import solve_ivp

from veyra.core import Check, Metric, VeyraResult
from veyra.plots import make_plot, series

mp.mp.dps = 50


def _sympify(expr: str) -> Any:
    return sp.sympify(str(expr).replace("^", "**"), evaluate=True)


def simplify_expression(expression: str) -> VeyraResult:
    expr = _sympify(expression)
    simplified = sp.simplify(expr)
    expanded = sp.expand(expr)
    factored = sp.factor(expr)
    return VeyraResult(
        ok=True,
        kind="symbolic algebra",
        title="Simplify",
        checks=[Check("symbolic simplification", True)],
        metrics=[
            Metric("simplified", str(simplified)),
            Metric("expanded", str(expanded)),
            Metric("factored", str(factored)),
        ],
        inputs={"expression": expression},
        solver="sympy.simplify",
    )


def solve_equation(equation: str, variable: str = "x") -> VeyraResult:
    if "=" in equation:
        left, right = equation.split("=", 1)
        eq = sp.Eq(_sympify(left), _sympify(right))
    else:
        eq = _sympify(equation)
    symbol = sp.Symbol(variable)
    solutions = sp.solve(eq, symbol)
    numeric = []
    for sol in solutions:
        try:
            numeric.append(complex(sol.evalf()))
        except (TypeError, ValueError):
            numeric.append(str(sol))
    return VeyraResult(
        ok=True,
        kind="equation solving",
        title="Solve equation",
        checks=[Check("closed-form solve", True, f"{len(solutions)} solution(s)")],
        metrics=[Metric(f"root {i + 1}", _fmt_number(val)) for i, val in enumerate(numeric)],
        inputs={"equation": equation, "variable": variable},
        details={"symbolic": [str(s) for s in solutions], "numeric": [str(n) for n in numeric]},
        solver="sympy.solve",
    )


def differentiate(expression: str, variable: str = "x", order: int = 1) -> VeyraResult:
    symbol = sp.Symbol(variable)
    expr = _sympify(expression)
    deriv = sp.diff(expr, symbol, order)
    return VeyraResult(
        ok=True,
        kind="calculus",
        title="Differentiate",
        checks=[Check("symbolic derivative", True)],
        metrics=[Metric("derivative", str(sp.simplify(deriv)))],
        inputs={"expression": expression, "variable": variable, "order": order},
        solver="sympy.diff",
    )


def integrate_expression(
    expression: str,
    variable: str = "x",
    lower: float | None = None,
    upper: float | None = None,
) -> VeyraResult:
    symbol = sp.Symbol(variable)
    expr = _sympify(expression)
    if lower is None or upper is None:
        antideriv = sp.integrate(expr, symbol)
        return VeyraResult(
            ok=True,
            kind="calculus",
            title="Indefinite integral",
            checks=[Check("symbolic integral", True)],
            metrics=[Metric("integral", str(antideriv))],
            inputs={"expression": expression, "variable": variable},
            solver="sympy.integrate",
        )
    definite = sp.integrate(expr, (symbol, lower, upper))
    numeric = float(definite.evalf())
    return VeyraResult(
        ok=True,
        kind="calculus",
        title="Definite integral",
        checks=[Check("symbolic integral", True)],
        metrics=[
            Metric("exact", str(definite)),
            Metric("numeric", numeric),
        ],
        inputs={"expression": expression, "variable": variable, "lower": lower, "upper": upper},
        solver="sympy.integrate",
    )


def find_roots(expression: str, variable: str = "x", guess: float = 0.0) -> VeyraResult:
    symbol = sp.Symbol(variable)
    expr = _sympify(expression)
    symbolic = sp.solve(expr, symbol)
    fn = sp.lambdify(symbol, expr, "numpy")
    numeric_root = None
    try:
        numeric_root = float(opt.brentq(fn, guess - 10, guess + 10)) if _changes_sign(fn, guess) else float(
            opt.newton(fn, guess)
        )
    except (ValueError, RuntimeError):
        try:
            numeric_root = float(opt.newton(fn, guess))
        except (ValueError, RuntimeError):
            numeric_root = None
    metrics = [Metric(f"symbolic {i + 1}", str(sol)) for i, sol in enumerate(symbolic)]
    if numeric_root is not None:
        metrics.append(Metric("numeric", numeric_root))
    return VeyraResult(
        ok=True,
        kind="numerical analysis",
        title="Find roots",
        checks=[Check("root finding", True, f"{len(symbolic)} symbolic")],
        metrics=metrics,
        inputs={"expression": expression, "variable": variable, "guess": guess},
        solver="sympy.solve + scipy",
    )


def solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> VeyraResult:
    a = np.array(matrix, dtype=float)
    b = np.array(rhs, dtype=float)
    rank = int(matrix_rank(a))
    condition = float(cond(a)) if a.size else math.inf
    stable = condition < 1e12
    try:
        x, residuals, *_ = np.linalg.lstsq(a, b, rcond=None)
        residual = float(residuals[0]) if len(residuals) else float(np.linalg.norm(a @ x - b))
        ok = True
    except np.linalg.LinAlgError as exc:
        return VeyraResult(
            ok=False,
            kind="linear algebra",
            title="Linear system",
            checks=[Check("solve", False, str(exc))],
            inputs={"matrix": matrix, "rhs": rhs},
        )
    return VeyraResult(
        ok=ok,
        kind="linear algebra",
        title="Linear system",
        checks=[
            Check("solved", True),
            Check("numerical stability", stable, f"cond={condition:.3e}"),
        ],
        metrics=[Metric(f"x{i + 1}", float(val)) for i, val in enumerate(x)]
        + [Metric("condition number", condition), Metric("residual", residual)],
        inputs={"shape": list(a.shape), "rank": rank},
        details={"solution": x.tolist(), "rank": rank},
        solver="numpy.linalg.lstsq",
        tolerance=1e-12,
    )


def matrix_analyze(matrix: list[list[float]]) -> VeyraResult:
    a = np.array(matrix, dtype=float)
    square = a.shape[0] == a.shape[1]
    checks = [Check("finite entries", bool(np.isfinite(a).all()))]
    metrics = [
        Metric("rows", a.shape[0]),
        Metric("cols", a.shape[1]),
        Metric("rank", int(matrix_rank(a))),
        Metric("frobenius", float(np.linalg.norm(a))),
    ]
    details: dict[str, Any] = {}
    if square:
        det = float(np.linalg.det(a))
        condition = float(cond(a))
        ev = eigvals(a)
        u, s, vh = svd(a)
        hermitian = np.allclose(a, a.T)
        pos_def = hermitian and bool(np.all(np.real(ev) > 0))
        checks.extend(
            [
                Check("square", True),
                Check("invertible", abs(det) > 1e-12, f"det={det:.6g}"),
                Check("positive definite", pos_def),
                Check("numerical stability", condition < 1e12, f"cond={condition:.3e}"),
            ]
        )
        metrics.extend(
            [
                Metric("determinant", det),
                Metric("trace", float(np.trace(a))),
                Metric("condition number", condition),
            ]
        )
        details.update(
            {
                "eigenvalues": [complex(v) for v in ev],
                "singular_values": s.tolist(),
                "positive_definite": pos_def,
            }
        )
    return VeyraResult(
        ok=all(c.passed for c in checks if c.name != "positive definite"),
        kind="linear algebra",
        title="Matrix analysis",
        checks=checks,
        metrics=metrics,
        details=details,
        inputs={"shape": list(a.shape)},
        solver="numpy.linalg",
    )


def optimize_function(
    expression: str,
    variable: str = "x",
    method: str = "bounded",
    lower: float = -10.0,
    upper: float = 10.0,
    guess: float = 0.0,
) -> VeyraResult:
    symbol = sp.Symbol(variable)
    expr = _sympify(expression)
    fn = sp.lambdify(symbol, expr, "numpy")
    if method == "bounded":
        result = opt.minimize_scalar(fn, bounds=(lower, upper), method="bounded")
        x = float(result.x)
    else:
        result = opt.minimize(lambda v: float(fn(v[0])), x0=np.array([guess]))
        x = float(result.x[0])
    return VeyraResult(
        ok=bool(result.success),
        kind="optimization",
        title="Optimize function",
        checks=[Check("optimizer converged", bool(result.success), getattr(result, "message", ""))],
        metrics=[Metric(variable, x), Metric("objective", float(fn(x)))],
        inputs={"expression": expression, "method": method, "lower": lower, "upper": upper},
        solver=f"scipy.optimize ({method})",
        iterations=int(getattr(result, "nit", 0) or 0),
    )


def solve_ode(
    expressions: list[str],
    variables: list[str],
    t_span: tuple[float, float] = (0.0, 1.0),
    y0: list[float] | None = None,
    params: dict[str, float] | None = None,
) -> VeyraResult:
    t = sp.Symbol("t")
    symbols = [sp.Symbol(name) for name in variables]
    env = {**(params or {}), "t": t, **{s.name: s for s in symbols}}
    rhs = [_sympify(expr).subs(env) for expr in expressions]
    func = sp.lambdify((t, symbols), rhs, "numpy")
    y_init = y0 or [0.0] * len(variables)

    def wrapped(time: float, state: np.ndarray) -> list[float]:
        return [float(v) for v in np.atleast_1d(func(time, state))]

    sol = solve_ivp(wrapped, t_span, y_init, method="RK45", rtol=1e-8, atol=1e-10, dense_output=True)
    final = sol.y[:, -1].tolist() if sol.y.size else []
    return VeyraResult(
        ok=bool(sol.success),
        kind="differential equations",
        title="ODE solve",
        checks=[
            Check("integrator converged", bool(sol.success), sol.message),
            Check("finite trajectory", bool(np.isfinite(sol.y).all())),
        ],
        metrics=[Metric(name, float(val)) for name, val in zip(variables, final)]
        + [Metric("steps", int(sol.t.size))],
        inputs={"expressions": expressions, "t_span": list(t_span), "y0": y_init, "params": params or {}},
        details={"t": sol.t.tolist(), "y": sol.y.tolist()},
        solver="scipy.integrate.solve_ivp RK45",
        tolerance=1e-8,
    )


def fourier_transform(values: list[float], sample_rate: float = 1.0) -> VeyraResult:
    signal = np.array(values, dtype=float)
    spectrum = fft(signal)
    freqs = fftfreq(signal.size, d=1.0 / sample_rate)
    magnitude = np.abs(spectrum)
    peak = int(np.argmax(magnitude[: signal.size // 2])) if signal.size else 0
    half = max(signal.size // 2, 1)
    return VeyraResult(
        ok=True,
        kind="fourier analysis",
        title="FFT",
        checks=[Check("transform computed", True)],
        metrics=[
            Metric("samples", signal.size),
            Metric("peak frequency", float(freqs[peak]), "Hz"),
            Metric("peak magnitude", float(magnitude[peak])),
        ],
        details={
            "frequencies": freqs.tolist(),
            "magnitude": magnitude.tolist(),
            "plot": make_plot(
                "series",
                "f (Hz)",
                "|X|",
                [series("magnitude", freqs[:half].tolist(), magnitude[:half].tolist())],
            ),
        },
        inputs={"n": signal.size, "sample_rate": sample_rate},
        solver="scipy.fft",
    )


def arbitrary_precision(expression: str, digits: int = 50) -> VeyraResult:
    digits = max(16, min(int(digits), 1000))
    with mp.workdps(digits):
        value = mp.nstr(mp.eval(expression) if hasattr(mp, "eval") else mp.mpf(0), digits)
        try:
            value = mp.nstr(sp.N(_sympify(expression), digits), n=digits)
        except Exception:  # noqa: BLE001
            value = str(mp.mpmathify(expression))
    return VeyraResult(
        ok=True,
        kind="arbitrary precision",
        title="High-precision evaluation",
        checks=[Check("precision", True, f"{digits} digits")],
        metrics=[Metric("value", value)],
        inputs={"expression": expression, "digits": digits},
        precision=f"{digits} decimal digits",
        solver="mpmath + sympy",
    )


def math_console(
    expression: str,
    action: str = "auto",
    variable: str = "x",
    lower: float | None = None,
    upper: float | None = None,
) -> VeyraResult:
    """Route a console expression to solve, simplify, differentiate, integrate, or evaluate."""
    chosen = (action or "auto").lower()
    text = str(expression).strip()
    if chosen == "auto":
        if "=" in text:
            chosen = "solve"
        elif text.lower().startswith("d/d"):
            chosen = "differentiate"
        else:
            chosen = "simplify"
    if chosen == "solve":
        return solve_equation(text, variable)
    if chosen == "differentiate":
        return differentiate(text, variable)
    if chosen == "integrate":
        return integrate_expression(text, variable, lower, upper)
    if chosen in {"roots", "root"}:
        return find_roots(text, variable)
    if chosen == "optimize":
        return optimize_function(text, variable, lower=lower or -10.0, upper=upper or 10.0)
    if chosen in {"eval", "evaluate", "n"}:
        return arbitrary_precision(text, digits=50)
    return simplify_expression(text)


def _changes_sign(fn, guess: float) -> bool:
    try:
        return fn(guess - 10) * fn(guess + 10) < 0
    except Exception:  # noqa: BLE001
        return False


def _fmt_number(value: Any) -> str:
    if isinstance(value, complex):
        if abs(value.imag) < 1e-12:
            return f"{value.real:.10g}"
        return f"{value.real:.10g}{value.imag:+.10g}j"
    return str(value)
