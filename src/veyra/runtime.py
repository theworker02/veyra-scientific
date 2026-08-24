"""The Veyra scientific runtime for declarative experiments.

This module is deliberately interface-neutral: the CLI, MCP server, Workbench,
and Cursor extension can all validate and execute the same experiment graph.
Legacy brace-format ``.veyra`` files continue to be handled by :mod:`veyra.dsl`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterable, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from veyra.catalog import bind_model_kwargs
from veyra.core import VERSION, Check, Metric, VeyraResult, json_default
from veyra.mathematics import math_console
from veyra.physics import run_named, simulate_motion
from veyra.units import Q_, UREG, parse_measured

EXPERIMENT_SCHEMA_VERSION = 1


class ExperimentFormatError(ValueError):
    """A useful diagnostic for a malformed declarative experiment."""


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CACHED = "cached"


@dataclass
class ScientificEvent:
    """A runtime event suitable for streaming to Cursor or the Workbench."""

    type: str
    node_id: str
    status: ExecutionStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentNode:
    id: str
    title: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    duration_ms: float | None = None
    result_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "result_hash": self.result_hash,
        }


@dataclass
class ExperimentGraph:
    experiment_hash: str
    nodes: list[ExperimentNode]

    def node(self, node_id: str) -> ExperimentNode:
        return next(node for node in self.nodes if node.id == node_id)

    def to_dict(self) -> dict[str, Any]:
        return {"experiment_hash": self.experiment_hash, "nodes": [node.to_dict() for node in self.nodes]}


class ParameterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | int | str | None = None
    unit: str = ""
    uncertainty: float | None = Field(default=None, ge=0)
    distribution: str | None = None
    mean: float | None = None
    sigma: float | None = Field(default=None, ge=0)

    @field_validator("unit")
    @classmethod
    def valid_unit(cls, value: str) -> str:
        if value:
            try:
                UREG.Unit(value.replace("^", "**"))
            except Exception as error:  # pint presents domain-specific diagnostics
                raise ValueError(f"unknown unit '{value}'") from error
        return value


class SimulationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = Field(min_length=1)
    solver: str = ""
    expression: str = ""
    action: str = "auto"
    variable: str = "x"
    rtol: float | None = Field(default=None, gt=0)
    atol: float | None = Field(default=None, gt=0)


class MonteCarloSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    samples: int = Field(default=1, ge=1, le=1_000_000)
    seed: int | None = None


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout: str | None = None
    workers: int | None = Field(default=None, ge=1)
    memory: str | None = None


class AssertionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1)


class ExperimentSpec(BaseModel):
    """Stable, portable schema for YAML-form ``.veyra`` experiments."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: int = Field(default=EXPERIMENT_SCHEMA_VERSION, ge=1)
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    simulation: SimulationSpec
    outputs: list[str] = Field(default_factory=list)
    assertions: list[AssertionSpec] = Field(default_factory=list, validation_alias="assert")
    monte_carlo: MonteCarloSpec | None = None
    resources: ResourceSpec | None = None
    references: list[str] = Field(default_factory=list)

    @field_validator("outputs")
    @classmethod
    def unique_outputs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("outputs must be unique")
        return value


class ScientificKernel(Protocol):
    """The interface implemented by the Veyra runtime and future kernels."""

    id: str
    domains: tuple[str, ...]

    def validate(self, experiment: ExperimentSpec) -> VeyraResult: ...

    def execute(self, experiment: ExperimentSpec, context: "ExecutionContext") -> AsyncIterable[ScientificEvent]: ...


@dataclass
class ExecutionContext:
    source: str = ""
    workspace: Path | None = None
    cache_enabled: bool = True


class VeyraRuntime:
    """The shared, local scientific execution engine."""

    id = "veyra.runtime"
    domains = (
        "mathematics",
        "physics",
        "geometry",
        "statistics",
        "numerical-analysis",
        "optimization",
        "data-analysis",
        "linear-algebra",
        "calculus",
        "differential-equations",
    )

    def validate(self, experiment: ExperimentSpec) -> VeyraResult:
        checks: list[Check] = [Check("schema validated", True, f"experiment schema v{experiment.version}")]
        warnings: list[str] = []
        engine = experiment.simulation.engine
        if engine not in {"mechanics.projectile", "mathematics.symbolic"}:
            try:
                bind_model_kwargs(_catalog_engine(engine), {})
                checks.append(Check("simulation engine available", True, engine))
            except Exception:
                checks.append(Check("simulation engine available", False, engine))
        else:
            checks.append(Check("simulation engine available", True, engine))

        checks.extend(_validate_parameter_units(engine, experiment.parameters))
        if experiment.monte_carlo and experiment.monte_carlo.samples > 1 and experiment.monte_carlo.seed is None:
            warnings.append("Monte Carlo seed will be generated and recorded at execution time.")
        if experiment.simulation.rtol is not None and experiment.simulation.rtol < 1e-14:
            warnings.append("rtol is below typical float64 precision; solver convergence may be unreliable.")
        if experiment.simulation.atol is not None and experiment.simulation.atol < 1e-14:
            warnings.append("atol is below typical float64 precision; solver convergence may be unreliable.")
        return VeyraResult(
            ok=all(check.passed for check in checks),
            kind="experiment validation",
            title=experiment.name,
            checks=checks,
            warnings=warnings,
            inputs={"engine": engine, "parameters": len(experiment.parameters)},
            solver="veyra experiment schema",
        )

    async def execute(self, experiment: ExperimentSpec, context: ExecutionContext) -> AsyncIterable[ScientificEvent]:
        """Execute as a stream of graph events without coupling to a UI host."""
        graph = build_graph(experiment)
        validation = self.validate(experiment)
        validation_node = graph.node("validate")
        validation_node.status = ExecutionStatus.SUCCEEDED if validation.ok else ExecutionStatus.FAILED
        validation_node.result_hash = _hash_payload(validation.to_dict())
        yield ScientificEvent("node", validation_node.id, validation_node.status, "schema and units validated")
        if not validation.ok:
            yield ScientificEvent("result", "validate", ExecutionStatus.FAILED, "experiment validation failed")
            return

        cache_path = _cache_path(context, graph.experiment_hash)
        if context.cache_enabled and cache_path and cache_path.is_file():
            cached = _result_from_dict(json.loads(cache_path.read_text(encoding="utf-8")))
            execution = graph.node("execute")
            graph.node("validate").status = ExecutionStatus.SUCCEEDED
            execution.status = ExecutionStatus.CACHED
            execution.result_hash = cached.run_id
            graph.node("outputs").status = ExecutionStatus.CACHED
            graph.node("assertions").status = ExecutionStatus.CACHED
            _attach_runtime_details(cached, experiment, graph, cache_hit=True)
            yield ScientificEvent("node", execution.id, ExecutionStatus.CACHED, "deterministic cache hit")
            yield ScientificEvent("node", "outputs", ExecutionStatus.CACHED, "cached outputs restored")
            yield ScientificEvent("node", "assertions", ExecutionStatus.CACHED, "cached assertions restored")
            yield ScientificEvent("result", execution.id, ExecutionStatus.CACHED, data={"result": cached})
            return

        execution = graph.node("execute")
        execution.status = ExecutionStatus.RUNNING
        yield ScientificEvent("node", execution.id, ExecutionStatus.RUNNING, "kernel executing")
        started = time.perf_counter()
        try:
            result = _execute_engine(experiment)
        except Exception as error:  # preserve a useful science-facing failure
            execution.status = ExecutionStatus.FAILED
            execution.duration_ms = (time.perf_counter() - started) * 1000
            failed = VeyraResult(
                ok=False,
                kind="experiment execution",
                title=experiment.name,
                checks=[Check("kernel execution", False, str(error))],
                inputs={"engine": experiment.simulation.engine},
                solver=experiment.simulation.solver or "veyra runtime",
            )
            _attach_runtime_details(failed, experiment, graph)
            yield ScientificEvent("node", execution.id, ExecutionStatus.FAILED, str(error))
            yield ScientificEvent("result", execution.id, ExecutionStatus.FAILED, data={"result": failed})
            return

        execution.duration_ms = (time.perf_counter() - started) * 1000
        if experiment.monte_carlo is not None:
            # A configured stochastic experiment always carries its seed into
            # the result fingerprint and the exported reproducibility record.
            result.seed = experiment.monte_carlo.seed if experiment.monte_carlo.seed is not None else 0
            result.run_id = result.fingerprint()
        execution.status = ExecutionStatus.SUCCEEDED if result.all_checks_passed() else ExecutionStatus.FAILED
        execution.result_hash = _hash_payload(result.to_dict())
        outputs = graph.node("outputs")
        output_checks, selected = _select_outputs(result, experiment.outputs)
        outputs.status = ExecutionStatus.SUCCEEDED if all(check.passed for check in output_checks) else ExecutionStatus.FAILED
        outputs.result_hash = _hash_payload(selected)
        result.checks = output_checks + result.checks
        assertion_node = graph.node("assertions")
        assertion_checks = _evaluate_assertions(experiment.assertions, result)
        assertion_node.status = ExecutionStatus.SUCCEEDED if all(check.passed for check in assertion_checks) else ExecutionStatus.FAILED
        assertion_node.result_hash = _hash_payload([check.__dict__ for check in assertion_checks])
        result.checks = assertion_checks + result.checks
        result.ok = result.ok and all(check.passed for check in output_checks + assertion_checks)
        result.title = experiment.name
        result.inputs = {
            **result.inputs,
            "source": context.source,
            "engine": experiment.simulation.engine,
        }
        _attach_runtime_details(result, experiment, graph, selected_outputs=selected)
        if result.all_checks_passed() and context.cache_enabled and cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(result.to_dict(), indent=2, default=json_default), encoding="utf-8")
        yield ScientificEvent("node", execution.id, execution.status, "kernel completed")
        yield ScientificEvent("node", outputs.id, outputs.status, "outputs collected")
        yield ScientificEvent("node", assertion_node.id, assertion_node.status, "assertions evaluated")
        yield ScientificEvent("result", execution.id, execution.status, data={"result": result})


def parse_experiment_spec(text: str) -> ExperimentSpec:
    """Parse a safe, intentionally small YAML subset used by portable experiments."""
    try:
        payload = _parse_yaml_mapping(text)
    except ExperimentFormatError:
        raise
    try:
        return ExperimentSpec.model_validate(payload)
    except ValidationError as error:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
        )
        raise ExperimentFormatError(messages) from error


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    return parse_experiment_spec(Path(path).read_text(encoding="utf-8"))


def validate_source(text: str, source: str = "") -> VeyraResult:
    try:
        experiment = parse_experiment_spec(text)
    except ExperimentFormatError as error:
        return VeyraResult(
            ok=False,
            kind="experiment validation",
            title=Path(source).stem or "Veyra experiment",
            checks=[Check("schema validated", False, str(error))],
            inputs={"source": source},
            solver="veyra experiment schema",
        )
    return VeyraRuntime().validate(experiment)


def build_graph(experiment: ExperimentSpec) -> ExperimentGraph:
    canonical = {
        "experiment": experiment.model_dump(mode="json", by_alias=True),
        # Kernel version is scientific provenance. A prior runtime's result
        # cannot be a cache hit for this computation.
        "runtime": {"id": VeyraRuntime.id, "version": VERSION},
    }
    experiment_hash = _hash_payload(canonical)
    definition = canonical["experiment"]
    return ExperimentGraph(
        experiment_hash=experiment_hash,
        nodes=[
            ExperimentNode("inputs", "Initial conditions", inputs=definition["parameters"], outputs=list(definition["parameters"]), status=ExecutionStatus.SUCCEEDED),
            ExperimentNode("validate", "Schema and dimensional validation", dependencies=["inputs"]),
            ExperimentNode("execute", experiment.simulation.engine, parameters=definition["simulation"], dependencies=["validate"]),
            ExperimentNode("outputs", "Result selection", outputs=experiment.outputs, dependencies=["execute"]),
            ExperimentNode("assertions", "Scientific assertions", outputs=[item.expression for item in experiment.assertions], dependencies=["outputs"]),
        ],
    )


def run_spec(experiment: ExperimentSpec, context: ExecutionContext | None = None) -> VeyraResult:
    """Synchronously consume the streaming runtime for the CLI and existing APIs."""
    async def collect() -> VeyraResult:
        result: VeyraResult | None = None
        async for event in VeyraRuntime().execute(experiment, context or ExecutionContext()):
            candidate = event.data.get("result")
            if isinstance(candidate, VeyraResult):
                result = candidate
        return result or VeyraResult(
            ok=False,
            kind="experiment execution",
            title=experiment.name,
            checks=[Check("kernel execution", False, "runtime produced no result")],
        )

    return asyncio.run(collect())


def run_spec_path(path: str | Path, workspace: Path | None = None) -> VeyraResult:
    source = Path(path)
    try:
        experiment = load_experiment_spec(source)
    except ExperimentFormatError as error:
        return VeyraResult(
            ok=False,
            kind="experiment validation",
            title=source.stem,
            checks=[Check("schema validated", False, str(error))],
            inputs={"source": str(source)},
            solver="veyra experiment schema",
        )
    root = workspace or _workspace_for(source)
    return run_spec(experiment, ExecutionContext(source=str(source), workspace=root))


def is_declarative_experiment(text: str) -> bool:
    """Distinguish YAML experiments from the original brace-format DSL."""
    return bool(re.search(r"^\s*(name|version|parameters|simulation)\s*:", text, re.MULTILINE))


def _execute_engine(experiment: ExperimentSpec) -> VeyraResult:
    engine = experiment.simulation.engine
    params = _parameter_values(experiment.parameters)
    if engine == "mechanics.projectile":
        monte = experiment.monte_carlo
        seed = monte.seed if monte and monte.seed is not None else 0
        return simulate_motion(
            velocity=_magnitude(params, "velocity", "m/s", 38.0),
            angle_deg=_magnitude(params, "angle", "deg", 45.0),
            gravity=_magnitude(params, "gravity", "m/s**2", 9.80665),
            drag_coefficient=float(params.get("drag", params.get("drag_coefficient", 0.0))),
            mass=_magnitude(params, "mass", "kg", 1.0),
            trials=monte.samples if monte else 1,
            seed=seed,
            velocity_uncertainty=_uncertainty(experiment.parameters, "velocity"),
            angle_uncertainty=_uncertainty(experiment.parameters, "angle"),
        )
    if engine == "mathematics.symbolic":
        expression = experiment.simulation.expression or str(params.get("expression") or "")
        if not expression:
            raise ValueError("mathematics.symbolic requires simulation.expression")
        return math_console(expression, experiment.simulation.action, experiment.simulation.variable)
    model = _catalog_engine(engine)
    kwargs = bind_model_kwargs(model, {key: value for key, value in params.items() if isinstance(value, (int, float))})
    return run_named(model, **kwargs)


def _catalog_engine(engine: str) -> str:
    return engine.replace("physics.", "").replace("mechanics.", "")


def _parameter_values(parameters: dict[str, ParameterSpec]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, parameter in parameters.items():
        if parameter.value is None:
            raise ValueError(f"parameter '{name}' has no executable value")
        if parameter.unit:
            values[name] = parse_measured(f"{parameter.value} {parameter.unit}").quantity
        else:
            values[name] = parameter.value
    return values


def _magnitude(values: dict[str, Any], name: str, unit: str, default: float) -> float:
    value = values.get(name)
    if value is None:
        return default
    if hasattr(value, "to"):
        return float(value.to(unit).magnitude)
    return float(value)


def _uncertainty(parameters: dict[str, ParameterSpec], name: str) -> float:
    return float(parameters.get(name).uncertainty or 0.0) if name in parameters else 0.0


def _validate_parameter_units(engine: str, parameters: dict[str, ParameterSpec]) -> list[Check]:
    expected = {
        "mechanics.projectile": {
            "velocity": "m/s",
            "angle": "degree",
            "gravity": "m/s**2",
            "mass": "kg",
        }
    }.get(engine, {})
    checks: list[Check] = []
    for name, parameter in parameters.items():
        if parameter.value is None and parameter.distribution is None:
            checks.append(Check(f"parameter {name}", False, "requires value or distribution"))
            continue
        if not parameter.unit:
            checks.append(Check(f"unit {name}", name not in expected, "dimensionless" if name not in expected else f"expected {expected[name]}"))
            continue
        try:
            actual = Q_(1, parameter.unit.replace("^", "**"))
            if name in expected:
                actual.to(expected[name])
                checks.append(Check(f"unit {name}", True, f"compatible with {expected[name]}"))
            else:
                checks.append(Check(f"unit {name}", True, str(actual.dimensionality)))
        except Exception as error:
            checks.append(Check(f"unit {name}", False, str(error)))
    return checks


def _select_outputs(result: VeyraResult, requested: list[str]) -> tuple[list[Check], dict[str, Any]]:
    aliases = {"range": "mean_range", "max_height": "peak_altitude", "flight_time": "flight_time"}
    metrics = {metric.name.lower().replace(" ", "_"): metric for metric in result.metrics}
    selected: dict[str, Any] = {}
    checks: list[Check] = []
    for name in requested:
        key = aliases.get(name, name).lower().replace(" ", "_")
        metric = metrics.get(key)
        if metric is None:
            checks.append(Check(f"output {name}", False, "model did not produce this output"))
        else:
            checks.append(Check(f"output {name}", True))
            selected[name] = {"value": metric.value, "unit": metric.unit, "uncertainty": metric.uncertainty}
    return checks, selected


def _evaluate_assertions(assertions: list[AssertionSpec], result: VeyraResult) -> list[Check]:
    values: dict[str, float] = {
        metric.name.lower().replace(" ", "_"): float(metric.value)
        for metric in result.metrics
        if isinstance(metric.value, (int, float))
    }
    for alias, metric_name in {"range": "mean_range", "max_height": "peak_altitude"}.items():
        if metric_name in values:
            values[alias] = values[metric_name]
    checks: list[Check] = []
    for assertion in assertions:
        expression = assertion.expression
        try:
            parsed = expression.replace("^", "**")
            if not re.fullmatch(r"[\w\s.+\-*/<>=!()]+", parsed):
                raise ValueError("contains unsupported syntax")
            checks.append(Check(expression, bool(eval(parsed, {"__builtins__": {}}, values))))  # noqa: S307
        except Exception as error:  # a failed assertion must remain a failed result
            checks.append(Check(expression, False, str(error)))
    return checks


def _attach_runtime_details(
    result: VeyraResult,
    experiment: ExperimentSpec,
    graph: ExperimentGraph,
    *,
    cache_hit: bool = False,
    selected_outputs: dict[str, Any] | None = None,
) -> None:
    result.details = {
        **result.details,
        "experiment": experiment.model_dump(mode="json", by_alias=True),
        "experiment_graph": graph.to_dict(),
        "selected_outputs": selected_outputs or result.details.get("selected_outputs", {}),
        "reproducibility": {
            "experiment_hash": graph.experiment_hash,
            "runtime": {"id": VeyraRuntime.id, "platform": platform.platform(), "python": platform.python_version()},
            "cache_hit": cache_hit,
            "random_seed": result.seed,
        },
    }


def _cache_path(context: ExecutionContext, experiment_hash: str) -> Path | None:
    if not context.workspace:
        return None
    return context.workspace / ".veyra" / "cache" / f"{experiment_hash}.json"


def _workspace_for(source: Path) -> Path:
    for candidate in [source.resolve().parent, *source.resolve().parents]:
        if (candidate / "pyproject.toml").is_file() or (candidate / "veyra.toml").is_file():
            return candidate
    return source.resolve().parent


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=json_default, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _result_from_dict(payload: dict[str, Any]) -> VeyraResult:
    return VeyraResult(
        ok=bool(payload.get("ok")),
        kind=str(payload.get("kind") or "experiment execution"),
        title=str(payload.get("title") or "Veyra experiment"),
        checks=[Check(**item) for item in payload.get("checks") or []],
        metrics=[Metric(**item) for item in payload.get("metrics") or []],
        details=dict(payload.get("details") or {}),
        warnings=list(payload.get("warnings") or []),
        inputs=dict(payload.get("inputs") or {}),
        solver=str(payload.get("solver") or ""),
        tolerance=payload.get("tolerance"),
        iterations=payload.get("iterations"),
        seed=payload.get("seed"),
        precision=str(payload.get("precision") or "float64"),
        run_id=str(payload.get("run_id") or ""),
        created_at=str(payload.get("created_at") or ""),
    )


def _parse_yaml_mapping(text: str) -> dict[str, Any]:
    """Parse the documented YAML subset without executing YAML tags or aliases."""
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ExperimentFormatError(f"line {number}: tabs are not allowed")
        lines.append((indent, stripped.strip()))
    if not lines:
        raise ExperimentFormatError("experiment is empty")

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines) or lines[index][0] < indent:
            return {}, index
        is_list = lines[index][1].startswith("- ") or lines[index][1] == "-"
        container: Any = [] if is_list else {}
        while index < len(lines):
            level, content = lines[index]
            if level < indent:
                break
            if level > indent:
                raise ExperimentFormatError(f"unexpected indentation near '{content}'")
            if is_list:
                if not content.startswith("-"):
                    break
                item = content[1:].strip()
                if not item:
                    value, index = parse_block(index + 1, _next_indent(index + 1, indent))
                    container.append(value)
                    continue
                if ":" in item:
                    key, raw_value = item.split(":", 1)
                    mapped: dict[str, Any] = {key.strip(): _yaml_scalar(raw_value.strip())} if raw_value.strip() else {}
                    index += 1
                    if index < len(lines) and lines[index][0] > indent:
                        child, index = parse_block(index, lines[index][0])
                        if raw_value.strip():
                            if not isinstance(child, dict):
                                raise ExperimentFormatError("list mapping continuation must be a mapping")
                            mapped.update(child)
                        else:
                            mapped[key.strip()] = child
                    container.append(mapped)
                    continue
                container.append(_yaml_scalar(item))
                index += 1
                continue
            if ":" not in content:
                raise ExperimentFormatError(f"expected key: value near '{content}'")
            key, raw_value = content.split(":", 1)
            key, raw_value = key.strip(), raw_value.strip()
            if not key:
                raise ExperimentFormatError("empty key")
            if raw_value:
                container[key] = _yaml_scalar(raw_value)
                index += 1
            else:
                if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
                    container[key] = {}
                    index += 1
                else:
                    container[key], index = parse_block(index + 1, lines[index + 1][0])
        return container, index

    def _next_indent(index: int, current: int) -> int:
        if index >= len(lines) or lines[index][0] <= current:
            raise ExperimentFormatError("list item requires an indented value")
        return lines[index][0]

    payload, next_index = parse_block(0, lines[0][0])
    if next_index != len(lines) or not isinstance(payload, dict):
        raise ExperimentFormatError("experiment root must be a mapping")
    return payload


def _yaml_scalar(value: str) -> Any:
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(value) if re.fullmatch(r"[+-]?\d+", value) else float(value)
    except ValueError:
        return value
