"""Shared result types, run fingerprints, and the instrument renderer."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from veyra.format import format_quantity, integrity_label

VERSION = "4.8.0"

RULE = "─" * 40


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

    def mark(self) -> str:
        return "[+]" if self.passed else "[x]"


@dataclass
class Metric:
    name: str
    value: float | str
    unit: str = ""
    uncertainty: float | None = None
    notes: str = ""

    def formatted(self) -> str:
        return format_quantity(self.value, self.unit, self.uncertainty)


@dataclass
class VeyraResult:
    ok: bool
    kind: str
    title: str
    checks: list[Check] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    solver: str = ""
    tolerance: float | None = None
    iterations: int | None = None
    seed: int | None = None
    precision: str = "float64"
    run_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        self.ok = bool(self.ok)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.run_id:
            self.run_id = self.fingerprint()

    def fingerprint(self) -> str:
        payload = {
            "kind": self.kind,
            "title": self.title,
            "inputs": self.inputs,
            "solver": self.solver,
            "tolerance": self.tolerance,
            "seed": self.seed,
            "precision": self.precision,
            "veyra": VERSION,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["veyra_version"] = VERSION
        data["integrity"] = self.integrity_score()
        data["platform"] = {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }
        return data

    def all_checks_passed(self) -> bool:
        return self.ok and all(check.passed for check in self.checks)

    def integrity_score(self) -> float:
        if not self.checks:
            return 1.0 if self.ok else 0.0
        return sum(1.0 for check in self.checks if check.passed) / len(self.checks)


def render_instrument(result: VeyraResult) -> str:
    """Render a restrained scientific instrument panel."""
    lines = [
        "Veyra Scientific",
        f"{'Experiment':<18}{result.title}",
        RULE,
    ]
    if result.kind:
        lines.append(f"{'Model':<18}{result.kind}")
    if result.solver:
        lines.append(f"{'Solver':<18}{result.solver}")
    if result.seed is not None:
        lines.append(f"{'Seed':<18}{result.seed}")
    if result.inputs:
        for key, value in result.inputs.items():
            lines.append(f"{_label(key):<18}{value}")
    if result.checks:
        lines.append("")
        for check in result.checks:
            suffix = f"  {check.detail}" if check.detail else ""
            lines.append(f"{check.mark()} {check.name}{suffix}")
    if result.metrics:
        lines.append("")
        width = max(len(metric.name) for metric in result.metrics)
        width = max(width, 16)
        for metric in result.metrics:
            lines.append(f"{metric.name:<{width}}  {metric.formatted()}")
    if result.warnings:
        lines.append("")
        for warning in result.warnings:
            lines.append(f"! {warning}")
    score = result.integrity_score()
    lines.extend(["", f"Run                 {result.run_id}"])
    lines.append(f"Scientific integrity {integrity_label(score)}  {score:.1%}")
    return "\n".join(lines)


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
