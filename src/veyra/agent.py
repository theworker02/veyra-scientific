"""Agent-safe experiment execution for Cursor and MCP clients.

This module deliberately does not interpret natural language or execute shell
commands. A host agent maps a user's request to a catalog model and numeric
parameters; Veyra validates that request and performs the local computation.
"""

from __future__ import annotations

import ast
import math
from typing import Any

from veyra.catalog import bind_model_kwargs, lookup_entry
from veyra.core import Check, VeyraResult
from veyra.physics import run_named


def run_agent_experiment(
    request: str,
    model: str,
    parameters: dict[str, Any] | None = None,
    assertions: list[str] | None = None,
) -> VeyraResult:
    """Run a bounded catalog model on behalf of an explicitly requested agent task.

    Parameters use the units documented by the model catalog. The function
    rejects unknown, non-numeric, and out-of-range inputs before invoking the
    scientific kernel. Assertions may only compare returned numeric metrics.
    """
    request = request.strip()
    if not request:
        return _failure("user request provided", "an agent run requires the user's stated task")

    entry = lookup_entry(model)
    if entry is None:
        return _failure(
            "catalog model selected", f"unknown model '{model}'", request=request, model=model
        )

    raw = parameters or {}
    if not isinstance(raw, dict):
        return _failure(
            "parameter payload", "parameters must be an object", request=request, model=entry["id"]
        )

    parameter_specs = {str(item["name"]): item for item in entry["params"]}
    unknown = sorted(set(raw) - set(parameter_specs))
    if unknown:
        return _failure(
            "known parameters",
            f"unsupported for {entry['id']}: {', '.join(unknown)}",
            request=request,
            model=entry["id"],
        )

    invalid = _validate_parameter_values(raw, parameter_specs)
    if invalid:
        return _failure("catalog parameter bounds", invalid, request=request, model=entry["id"])

    bound = bind_model_kwargs(str(entry["id"]), raw)
    if len(bound) != len(raw):
        skipped = sorted(set(raw) - set(bound))
        return _failure(
            "executable parameters",
            f"could not bind: {', '.join(skipped)}",
            request=request,
            model=entry["id"],
        )

    result = run_named(str(entry["id"]), **bound)
    agent_checks = [
        Check("user request provided", True),
        Check("catalog model selected", True, str(entry["id"])),
        Check("catalog parameter bounds", True, f"{len(bound)} override(s)"),
    ]
    assertion_checks = _evaluate_assertions(assertions or [], result)
    result.checks = agent_checks + assertion_checks + result.checks
    result.ok = result.ok and all(check.passed for check in agent_checks + assertion_checks)
    result.kind = "agent experiment"
    result.title = f"Agent experiment: {entry['title']}"
    result.inputs = {
        **result.inputs,
        "agent_request": request,
        "catalog_model": entry["id"],
        "agent_parameters": bound,
    }
    result.details = {
        **result.details,
        "agent": {
            "request": request,
            "model": entry["id"],
            "model_title": entry["title"],
            "parameters": bound,
            "parameter_units": {
                name: spec.get("unit", "") for name, spec in parameter_specs.items()
            },
            "assertions": assertions or [],
            "execution": "local Veyra kernel",
        },
    }
    # The fingerprint must include the explicit agent request and bound inputs.
    result.run_id = result.fingerprint()
    return result


def _validate_parameter_values(raw: dict[str, Any], specs: dict[str, dict[str, Any]]) -> str:
    for name, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{name} must be a numeric value in the catalog unit"
        numeric = float(value)
        if not math.isfinite(numeric):
            return f"{name} must be finite"
        spec = specs[name]
        if spec.get("type") == "integer" and not numeric.is_integer():
            return f"{name} must be an integer"
        minimum = spec.get("min")
        maximum = spec.get("max")
        if minimum is not None and numeric < float(minimum):
            return f"{name} must be at least {minimum}"
        if maximum is not None and numeric > float(maximum):
            return f"{name} must be at most {maximum}"
    return ""


def _evaluate_assertions(assertions: list[str], result: VeyraResult) -> list[Check]:
    values = {
        metric.name.lower().replace(" ", "_"): float(metric.value)
        for metric in result.metrics
        if isinstance(metric.value, (int, float))
    }
    aliases = {"range": "mean_range", "max_height": "peak_altitude"}
    for alias, metric in aliases.items():
        if metric in values:
            values[alias] = values[metric]

    checks: list[Check] = []
    for expression in assertions:
        try:
            _validate_assertion_expression(expression, values)
            passed = bool(eval(expression.replace("^", "**"), {"__builtins__": {}}, values))  # noqa: S307
            checks.append(Check(f"agent assertion: {expression}", passed))
        except Exception as error:  # an unusable assertion is evidence of a failed request
            checks.append(Check(f"agent assertion: {expression}", False, str(error)))
    return checks


def _validate_assertion_expression(expression: str, values: dict[str, float]) -> None:
    if not expression.strip():
        raise ValueError("assertion must not be empty")
    parsed = ast.parse(expression.replace("^", "**"), mode="eval")
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.BoolOp,
        ast.Compare,
        ast.Constant,
        ast.Load,
        ast.Name,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    )
    for node in ast.walk(parsed):
        if not isinstance(node, allowed):
            raise ValueError("assertions may only compare numeric result metrics")
        if isinstance(node, ast.Name) and node.id not in values:
            raise ValueError(f"unknown result metric '{node.id}'")


def _failure(check: str, detail: str, *, request: str = "", model: str = "") -> VeyraResult:
    return VeyraResult(
        ok=False,
        kind="agent experiment",
        title="Agent experiment",
        checks=[Check(check, False, detail)],
        inputs={"agent_request": request, "catalog_model": model},
        solver="agent experiment contract",
    )
