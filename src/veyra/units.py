"""Unit system and dimensional analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pint
from pint.errors import DimensionalityError, UndefinedUnitError

from veyra.core import Check, Metric, VeyraResult

UREG = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = UREG.Quantity

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_UNCERTAINTY = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:\s*±\s*(?P<unc>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))?"
    r"(?:\s+(?P<unit>.+))?\s*$"
)

DIMENSION_NAMES = {
    "length": "L",
    "mass": "M",
    "time": "T",
    "current": "I",
    "temperature": "Θ",
    "amount": "N",
    "luminosity": "J",
    "[length]": "L",
    "[mass]": "M",
    "[time]": "T",
    "[current]": "I",
    "[temperature]": "Θ",
    "[substance]": "N",
    "[luminosity]": "J",
}

COMMON_QUANTITIES = {
    "energy": "joule",
    "force": "newton",
    "power": "watt",
    "pressure": "pascal",
    "frequency": "hertz",
    "charge": "coulomb",
    "voltage": "volt",
    "resistance": "ohm",
    "velocity": "meter/second",
    "acceleration": "meter/second**2",
    "density": "kilogram/meter**3",
}


@dataclass
class Measured:
    value: float
    unit: str
    uncertainty: float | None = None
    quantity: Any = None

    def magnitude(self, to: str | None = None) -> float:
        qty = self.quantity if self.quantity is not None else Q_(self.value, self.unit or "dimensionless")
        if to:
            return float(qty.to(to).magnitude)
        return float(qty.magnitude)


def normalize_unit(text: str) -> str:
    text = text.translate(_SUPERSCRIPTS)
    text = text.replace("·", "*").replace("×", "*")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("^", "**")
    return text


def parse_measured(text: str, default_unit: str = "") -> Measured:
    raw = str(text).strip()
    match = _UNCERTAINTY.match(raw)
    if not match:
        if default_unit:
            qty = Q_(raw) if _looks_like_quantity(raw) else Q_(float(raw), default_unit)
            return Measured(float(qty.magnitude), str(qty.units), quantity=qty)
        qty = Q_(raw)
        return Measured(float(qty.magnitude), str(qty.units), quantity=qty)

    value = float(match.group("value"))
    unc = match.group("unc")
    unit = normalize_unit(match.group("unit") or default_unit or "dimensionless")
    qty = Q_(value, unit)
    return Measured(
        value=float(qty.magnitude),
        unit=str(qty.units),
        uncertainty=float(unc) if unc is not None else None,
        quantity=qty,
    )


def _looks_like_quantity(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def quantity(value: float | str, unit: str | None = None) -> Any:
    if isinstance(value, str) and unit is None:
        return parse_measured(value).quantity
    return Q_(float(value), normalize_unit(unit or "dimensionless"))


def dimensional_formula(unit_or_quantity: Any) -> str:
    qty = unit_or_quantity if hasattr(unit_or_quantity, "dimensionality") else Q_(1, unit_or_quantity)
    parts: list[str] = []
    for dim, exp in qty.dimensionality.items():
        symbol = DIMENSION_NAMES.get(str(dim), str(dim))
        exp_i = int(exp) if float(exp).is_integer() else exp
        if exp_i == 1:
            parts.append(symbol)
        else:
            parts.append(f"{symbol}^{exp_i}")
    return " ".join(parts) if parts else "1"


def compatible(a: str, b: str) -> bool:
    try:
        Q_(1, normalize_unit(a)).to(normalize_unit(b))
        return True
    except (DimensionalityError, UndefinedUnitError, ValueError):
        return False


def validate_units(assignments: dict[str, str], expected: dict[str, str] | None = None) -> VeyraResult:
    checks: list[Check] = []
    metrics: list[Metric] = []
    parsed: dict[str, Measured] = {}
    ok = True
    for name, raw in assignments.items():
        try:
            measured = parse_measured(raw)
            parsed[name] = measured
            formula = dimensional_formula(measured.quantity)
            metrics.append(Metric(name, measured.value, measured.unit, measured.uncertainty, formula))
            checks.append(Check(f"{name} units", True, f"{measured.unit} ({formula})"))
        except (UndefinedUnitError, ValueError, DimensionalityError) as exc:
            ok = False
            checks.append(Check(f"{name} units", False, str(exc)))
    if expected:
        for name, want in expected.items():
            if name not in parsed:
                ok = False
                checks.append(Check(f"{name} expected", False, "missing"))
                continue
            if compatible(parsed[name].unit, want):
                checks.append(Check(f"{name} matches {want}", True))
            else:
                ok = False
                checks.append(
                    Check(
                        f"{name} matches {want}",
                        False,
                        f"got {dimensional_formula(parsed[name].quantity)}",
                    )
                )
    return VeyraResult(
        ok=ok,
        kind="dimensional analysis",
        title="Unit validation",
        checks=checks,
        metrics=metrics,
        inputs=assignments,
        details={"dimensional_formulas": {k: m.notes for k, m in zip(assignments, metrics)}},
    )


def convert_quantity(value: float | str, to_unit: str, from_unit: str = "") -> VeyraResult:
    """Convert a measured quantity into another unit of the same dimension."""
    try:
        if from_unit:
            qty = Q_(float(value), normalize_unit(from_unit))
        else:
            qty = parse_measured(str(value)).quantity
        converted = qty.to(normalize_unit(to_unit))
        formula = dimensional_formula(converted)
        return VeyraResult(
            ok=True,
            kind="unit conversion",
            title="Convert",
            checks=[Check("compatible dimensions", True, formula)],
            metrics=[
                Metric("from", float(qty.magnitude), str(qty.units)),
                Metric("to", float(converted.magnitude), str(converted.units)),
                Metric("dimension", formula),
            ],
            inputs={"value": value, "from": from_unit or str(qty.units), "to": to_unit},
            solver="pint",
        )
    except (DimensionalityError, UndefinedUnitError, ValueError) as exc:
        return VeyraResult(
            ok=False,
            kind="unit conversion",
            title="Convert",
            checks=[Check("compatible dimensions", False, str(exc))],
            inputs={"value": value, "from": from_unit, "to": to_unit},
        )


def analyze_expression_dimensions(symbol_units: dict[str, str], expression: str) -> VeyraResult:
    """Substitute pint quantities into a Python expression and report the result dimension."""
    env: dict[str, Any] = {name: Q_(1, normalize_unit(unit)) for name, unit in symbol_units.items()}
    env.update(
        {
            "pi": 3.141592653589793,
            "e": 2.718281828459045,
        }
    )
    try:
        result = eval(expression, {"__builtins__": {}}, env)  # noqa: S307 — sandboxed locals only
        if not hasattr(result, "dimensionality"):
            result = Q_(result, "dimensionless")
        formula = dimensional_formula(result)
        return VeyraResult(
            ok=True,
            kind="dimensional analysis",
            title="Expression dimensions",
            checks=[Check("expression evaluated", True, formula)],
            metrics=[Metric("dimension", formula)],
            inputs={"expression": expression, **symbol_units},
            details={"unit": str(result.units), "formula": formula},
        )
    except Exception as exc:  # noqa: BLE001 — report any dimensional failure
        return VeyraResult(
            ok=False,
            kind="dimensional analysis",
            title="Expression dimensions",
            checks=[Check("expression evaluated", False, str(exc))],
            inputs={"expression": expression, **symbol_units},
        )
