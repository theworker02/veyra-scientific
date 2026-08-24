"""Uncertainty-aware SI formatting for instrument readouts."""

from __future__ import annotations

import math

_PREFIXES = (
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "µ"),
    (1e-9, "n"),
)

_NO_SCALE = {"", "1", "deg", "°", "rad", "dimensionless", "%", "s"}


def si_prefix(value: float, unit: str) -> tuple[float, str]:
    if unit in _NO_SCALE or not math.isfinite(value) or value == 0:
        return value, ""
    absv = abs(value)
    if 0.1 <= absv < 1000:
        return value, ""
    for factor, prefix in _PREFIXES:
        if factor == 1.0:
            continue
        scaled = value / factor
        if 0.1 <= abs(scaled) < 1000:
            return scaled, prefix
    return value, ""


def uncertainty_decimals(uncertainty: float) -> int:
    if not math.isfinite(uncertainty) or uncertainty <= 0:
        return 6
    exp = math.floor(math.log10(uncertainty))
    return max(0, -int(exp) + 1)


def format_quantity(value: float | str, unit: str = "", uncertainty: float | None = None) -> str:
    if isinstance(value, str):
        return value
    if not math.isfinite(float(value)):
        return str(value)
    scaled, prefix = si_prefix(float(value), unit)
    label = f"{prefix}{unit}".strip()
    if uncertainty is not None and uncertainty > 0:
        u_scaled, _ = si_prefix(float(uncertainty), unit)
        if prefix:
            factor = float(value) / scaled if scaled else 1.0
            u_scaled = float(uncertainty) / factor
        digits = uncertainty_decimals(u_scaled)
        return f"{scaled:.{digits}f} ± {u_scaled:.{digits}f} {label}".strip()
    text = f"{scaled:.6g} {label}".strip()
    return text


def integrity_label(score: float) -> str:
    if score >= 0.999:
        return "PASS"
    if score >= 0.8:
        return "REVIEW"
    return "FAIL"
