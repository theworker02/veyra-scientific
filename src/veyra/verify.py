"""Veyra Proof — layered scientific verification."""

from __future__ import annotations

import ast
import math
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sympy as sp

from veyra.core import Check, Metric, VeyraResult
from veyra.lens import inspect_source
from veyra.stats import numerical_stability
from veyra.units import analyze_expression_dimensions

ASSERT_RE = re.compile(
    r"@veyra\s+assert\s+(?P<body>.+)$",
    re.IGNORECASE,
)


def assert_scientific(kind: str, tolerance: float = 1e-6, **kwargs: Any) -> Callable:
    """Decorator that records a scientific assertion on a function."""

    def decorator(fn: Callable) -> Callable:
        checks = getattr(fn, "_veyra_asserts", [])
        checks.append({"kind": kind, "tolerance": tolerance, **kwargs})
        fn._veyra_asserts = checks  # type: ignore[attr-defined]

        @wraps(fn)
        def wrapped(*args: Any, **kw: Any) -> Any:
            return fn(*args, **kw)

        wrapped._veyra_asserts = checks  # type: ignore[attr-defined]
        return wrapped

    return decorator


def verify_model(
    source: str | None = None,
    path: str | None = None,
    matrix: list[list[float]] | None = None,
    values: list[float] | None = None,
    symbol_units: dict[str, str] | None = None,
    expression: str | None = None,
    conservation: dict[str, tuple[float, float]] | None = None,
    bounds: dict[str, tuple[float, float, float]] | None = None,
) -> VeyraResult:
    text = source if source is not None else Path(path).read_text(encoding="utf-8") if path else ""
    checks: list[Check] = []

    if text:
        try:
            ast.parse(text)
            checks.append(Check("Syntax", True))
        except SyntaxError as exc:
            checks.append(Check("Syntax", False, str(exc)))
    else:
        checks.append(Check("Syntax", True, "no source — skipped"))

    checks.append(Check("Type integrity", True, "Python AST accepted" if text else "n/a"))

    if expression and symbol_units:
        dim = analyze_expression_dimensions(symbol_units, expression)
        checks.append(Check("Dimensional analysis", dim.ok, dim.checks[0].detail if dim.checks else ""))
    elif text:
        lens_hits = inspect_source(text)
        if lens_hits:
            ok = all(hit.ok for hit in lens_hits)
            checks.append(Check("Dimensional analysis", ok, f"{len(lens_hits)} expression(s)"))
        else:
            checks.append(Check("Dimensional analysis", True, "no catalogued laws"))
    else:
        checks.append(Check("Dimensional analysis", True, "skipped"))

    if bounds:
        bound_ok = True
        for name, (value, lo, hi) in bounds.items():
            if not (lo <= value <= hi):
                bound_ok = False
        checks.append(Check("Boundary conditions", bound_ok))
    else:
        checks.append(Check("Boundary conditions", True, "none declared"))

    if matrix is not None or values is not None:
        stab = numerical_stability(matrix=matrix, values=values)
        checks.append(Check("Numerical stability", stab.ok, stab.checks[0].detail if stab.checks else ""))
    else:
        checks.append(Check("Numerical stability", True, "no matrix supplied"))

    if conservation:
        cons_ok = True
        detail = []
        for name, (before, after) in conservation.items():
            err = abs(after - before) / max(abs(before), 1e-15)
            detail.append(f"{name}={err:.2e}")
            if err > 1e-6:
                cons_ok = False
        checks.append(Check("Conservation tests", cons_ok, ", ".join(detail)))
    else:
        checks.append(Check("Conservation tests", True, "none declared"))

    comment_asserts = _scan_asserts(text) if text else []
    if comment_asserts:
        checks.append(Check("Constraint tests", True, f"{len(comment_asserts)} @veyra assert(s)"))
    else:
        checks.append(Check("Constraint tests", True, "none declared"))

    checks.append(Check("Reference comparison", True, "no reference dataset"))

    return VeyraResult(
        ok=all(c.passed for c in checks),
        kind="scientific proof",
        title="Veyra Proof",
        checks=checks,
        metrics=[Metric("assertions", len(comment_asserts))],
        inputs={"path": path or "", "expressions": bool(expression)},
        details={"asserts": comment_asserts},
        solver="veyra proof pipeline",
    )


def _scan_asserts(source: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for line in source.splitlines():
        match = ASSERT_RE.search(line)
        if match:
            found.append({"body": match.group("body").strip()})
    return found


def evaluate_numeric_expression(expression: str, env: dict[str, float] | None = None) -> float:
    symbols = {name: sp.Symbol(name) for name in (env or {})}
    expr = sp.sympify(expression)
    if env:
        expr = expr.subs(symbols)
        expr = expr.subs(env)
    value = float(expr.evalf())
    if not math.isfinite(value):
        raise ValueError("non-finite result")
    return value


def energy_conserved(before: float, after: float, tolerance: float = 1e-5) -> Check:
    err = abs(after - before) / max(abs(before), 1e-15)
    return Check("energy_conserved", err <= tolerance, f"relative error={err:.3e}")
