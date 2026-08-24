"""Veyra Lens — scientific semantics over source expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from veyra.core import Check, Metric, VeyraResult
from veyra.units import analyze_expression_dimensions

MODELS = [
    {
        "name": "Newtonian gravitational force",
        "canonical": "G * m1 * m2 / r**2",
        "aliases": ["G*m1*m2/r**2", "G*(m1*m2)/r**2"],
        "wrong": ["G * (m1 + m2) / r**2", "G*(m1+m2)/r**2"],
        "symbols": {"F": "force", "G": "N*m**2/kg**2", "m1": "kg", "m2": "kg", "r": "m"},
        "result": "newton",
        "formula": "M L T^-2",
        "lhs": {"f", "force", "fg", "gravity"},
    },
    {
        "name": "Kinetic energy",
        "canonical": "0.5 * m * v**2",
        "aliases": ["(1/2)*m*v**2", "m*v**2/2"],
        "wrong": ["0.5 * m * v"],
        "symbols": {"E": "joule", "m": "kg", "v": "m/s"},
        "result": "joule",
        "formula": "M L^2 T^-2",
        "lhs": {"e", "ke", "energy", "kinetic"},
    },
    {
        "name": "Newton's second law",
        "canonical": "m * a",
        "aliases": ["m*a"],
        "wrong": ["m + a"],
        "symbols": {"F": "newton", "m": "kg", "a": "m/s**2"},
        "result": "newton",
        "formula": "M L T^-2",
        "lhs": {"f", "force"},
    },
    {
        "name": "Coulomb force",
        "canonical": "k * q1 * q2 / r**2",
        "aliases": ["k*q1*q2/r**2"],
        "wrong": ["k * (q1 + q2) / r**2"],
        "symbols": {"F": "newton", "k": "N*m**2/C**2", "q1": "C", "q2": "C", "r": "m"},
        "result": "newton",
        "formula": "M L T^-2",
        "lhs": {"f", "force", "fe"},
    },
    {
        "name": "Ideal gas law",
        "canonical": "n * R * T / V",
        "aliases": ["n*R*T/V"],
        "wrong": ["n * R * T * V"],
        "symbols": {"P": "Pa", "n": "mol", "R": "J/mol/K", "T": "K", "V": "m**3"},
        "result": "Pa",
        "formula": "M L^-1 T^-2",
        "lhs": {"p", "pressure"},
    },
    {
        "name": "Hooke's law",
        "canonical": "-k * x",
        "aliases": ["-k*x"],
        "wrong": ["k / x"],
        "symbols": {"F": "newton", "k": "N/m", "x": "m"},
        "result": "newton",
        "formula": "M L T^-2",
        "lhs": {"f", "force", "fspring"},
    },
    {
        "name": "Ohm's law",
        "canonical": "I * R",
        "aliases": ["I*R"],
        "wrong": ["I / R"],
        "symbols": {"V": "volt", "I": "ampere", "R": "ohm"},
        "result": "volt",
        "formula": "M L^2 T^-3 I^-1",
        "lhs": {"v", "voltage", "potential"},
    },
    {
        "name": "Thin lens",
        "canonical": "1/do + 1/di",
        "aliases": ["1/u + 1/v", "1/object + 1/image"],
        "wrong": ["do + di"],
        "symbols": {"f": "m", "do": "m", "di": "m"},
        "result": "1/m",
        "formula": "L^-1",
        "lhs": {"invf", "power"},
    },
    {
        "name": "Escape velocity",
        "canonical": "sqrt(2 * G * M / r)",
        "aliases": ["sqrt(2*G*M/r)"],
        "wrong": ["sqrt(G * M / r)"],
        "symbols": {"v": "m/s", "G": "N*m**2/kg**2", "M": "kg", "r": "m"},
        "result": "m/s",
        "formula": "L T^-1",
        "lhs": {"vesc", "escape", "v"},
    },
    {
        "name": "SHM angular frequency",
        "canonical": "sqrt(k / m)",
        "aliases": ["sqrt(k/m)"],
        "wrong": ["k / m"],
        "symbols": {"omega": "rad/s", "k": "N/m", "m": "kg"},
        "result": "rad/s",
        "formula": "T^-1",
        "lhs": {"omega", "w", "angular"},
    },
    {
        "name": "Doppler shift",
        "canonical": "f * (c + vo) / (c - vs)",
        "aliases": ["f*(c+vo)/(c-vs)"],
        "wrong": ["f * (c - vo) / (c + vs)"],
        "symbols": {"f": "Hz", "c": "m/s", "vo": "m/s", "vs": "m/s"},
        "result": "Hz",
        "formula": "T^-1",
        "lhs": {"fobs", "observed", "fp"},
    },
    {
        "name": "Centripetal acceleration",
        "canonical": "v**2 / r",
        "aliases": ["v^2/r"],
        "wrong": ["v / r**2"],
        "symbols": {"a": "m/s**2", "v": "m/s", "r": "m"},
        "result": "m/s^2",
        "formula": "L T^-2",
        "lhs": {"a", "ac", "centripetal"},
    },
]


@dataclass
class LensHit:
    line: int
    lhs: str
    expression: str
    result: VeyraResult


def inspect_expression(expression: str, symbol_units: dict[str, str] | None = None) -> VeyraResult:
    cleaned = _normalize(expression)
    match = _match_model(cleaned)
    checks = [Check("expression parsed", True, cleaned)]
    metrics = [Metric("expression", cleaned)]
    details: dict[str, object] = {}
    if match:
        model, status = match
        checks.append(Check("model recognized", True, model["name"]))
        if status == "wrong":
            checks.append(
                Check(
                    "scientific consistency",
                    False,
                    f"resembles {model['name']} but operators do not match the canonical law",
                )
            )
        else:
            checks.append(Check("scientific consistency", True, "matches canonical form"))
        checks.append(Check("expected dimension", True, model["formula"]))
        metrics.extend(
            [
                Metric("detected model", model["name"]),
                Metric("expected result", model["result"]),
                Metric("dimension", model["formula"]),
            ]
        )
        details["symbols"] = model["symbols"]
        details["model"] = model["name"]
        details["status"] = status
        units = symbol_units or {k: v for k, v in model["symbols"].items() if k not in {"F", "E", "P", "V"}}
        dim = analyze_expression_dimensions(units, model["canonical"])
        checks.extend(dim.checks)
    elif symbol_units:
        dim = analyze_expression_dimensions(symbol_units, cleaned)
        checks.extend(dim.checks)
        metrics.extend(dim.metrics)
    else:
        checks.append(Check("model recognized", False, "no catalog match"))
    return VeyraResult(
        ok=all(c.passed for c in checks if c.name != "model recognized"),
        kind="scientific lens",
        title="Veyra Lens",
        checks=checks,
        metrics=metrics,
        details=details,
        inputs={"expression": expression},
        solver="symbolic pattern catalog",
    )


def inspect_source(source: str) -> list[LensHit]:
    hits: list[LensHit] = []
    for index, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#") or stripped.startswith("@"):
            continue
        if re.search(r"\b(def|class|import|return|if|for|while|assert)\b", stripped):
            continue
        lhs, right = stripped.split("=", 1)
        lhs = lhs.strip()
        right = right.strip().rstrip(";")
        if re.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", right.replace(" ", "")):
            continue
        if not any(token in right for token in ("*", "/", "+", "**", "^")):
            continue
        result = inspect_expression(right)
        model = result.details.get("model")
        catalog = next((item for item in MODELS if item["name"] == model), None)
        if catalog and catalog.get("lhs") and lhs.lower() not in catalog["lhs"]:
            if result.details.get("status") != "wrong":
                continue
        hits.append(LensHit(line=index, lhs=lhs, expression=right, result=result))
    return hits


def inspect_file_result(source: str, path: str = "") -> VeyraResult:
    hits = inspect_source(source)
    checks = [
        Check(f"L{hit.line} {hit.lhs}", hit.result.ok, hit.result.checks[-1].detail if hit.result.checks else "")
        for hit in hits
    ]
    failed = sum(1 for hit in hits if not hit.result.ok)
    return VeyraResult(
        ok=failed == 0,
        kind="scientific lens",
        title="Veyra Lens",
        checks=checks or [Check("expressions found", True, "none")],
        metrics=[Metric("expressions", len(hits)), Metric("inconsistent", failed)],
        details={
            "hits": [
                {
                    "line": hit.line,
                    "lhs": hit.lhs,
                    "expression": hit.expression,
                    "ok": hit.result.ok,
                    "model": hit.result.details.get("model"),
                    "message": next(
                        (c.detail for c in hit.result.checks if not c.passed),
                        "recognized",
                    ),
                }
                for hit in hits
            ]
        },
        inputs={"path": path, "count": len(hits)},
        solver="symbolic pattern catalog",
    )


def _match_model(expression: str) -> tuple[dict, str] | None:
    expr = _sym(expression)
    for model in MODELS:
        if _equiv(expr, model["canonical"]) or any(_equiv(expr, alias) for alias in model["aliases"]):
            return model, "canonical"
        if any(_equiv(expr, wrong) for wrong in model["wrong"]):
            return model, "wrong"
    return None


def _equiv(left, right) -> bool:
    try:
        return bool(sp.simplify(_sym(left) - _sym(right)) == 0)
    except Exception:  # noqa: BLE001
        return str(left) == str(right)


def _sym(expression) -> sp.Expr:
    if isinstance(expression, sp.Basic):
        return expression
    return sp.sympify(_normalize(str(expression)))


def _normalize(expression: str) -> str:
    text = str(expression).strip().rstrip(";")
    text = text.replace("^", "**")
    return re.sub(r"\s+", "", text)
