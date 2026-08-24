from pathlib import Path

from veyra.dsl import run_path
from veyra.reproduce import store
from veyra.runtime import ExecutionContext, parse_experiment_spec, run_spec, validate_source

PROJECTILE = """\
name: runtime-projectile
version: 1
parameters:
  velocity:
    value: 42
    unit: m/s
  angle:
    value: 38
    unit: deg
  gravity:
    value: 9.80665
    unit: m/s^2
simulation:
  engine: mechanics.projectile
monte_carlo:
  samples: 4
  seed: 182740195
outputs:
  - range
  - max_height
  - flight_time
assert:
  - expression: range > 0
"""


def test_declarative_experiment_runs_with_real_graph(tmp_path: Path):
    result = run_spec(parse_experiment_spec(PROJECTILE), ExecutionContext(workspace=tmp_path))
    assert result.all_checks_passed()
    graph = result.details["experiment_graph"]
    assert [node["id"] for node in graph["nodes"]] == [
        "inputs",
        "validate",
        "execute",
        "outputs",
        "assertions",
    ]
    assert result.details["selected_outputs"]["range"]["unit"] == "m"
    assert result.details["reproducibility"]["experiment_hash"] == graph["experiment_hash"]
    assert result.seed == 182740195


def test_invalid_dimensions_fail_before_execution():
    invalid = PROJECTILE.replace("unit: m/s", "unit: kg", 1)
    result = validate_source(invalid)
    assert not result.all_checks_passed()
    velocity = next(check for check in result.checks if check.name == "unit velocity")
    assert "Cannot convert" in velocity.detail


def test_runtime_cache_and_veyr_artifact_are_reproducible(tmp_path: Path):
    experiment = parse_experiment_spec(PROJECTILE)
    first = run_spec(experiment, ExecutionContext(workspace=tmp_path))
    second = run_spec(experiment, ExecutionContext(workspace=tmp_path))
    assert first.all_checks_passed()
    assert second.details["reproducibility"]["cache_hit"] is True
    store(first, tmp_path)
    assert (tmp_path / ".veyra" / "results" / f"{first.run_id}.veyr").is_file()


def test_new_yaml_example_runs_through_the_existing_dsl_entry_point():
    root = Path(__file__).resolve().parents[1]
    result = run_path(root / "examples" / "runtime-projectile.veyra")[0]
    assert result.all_checks_passed()
