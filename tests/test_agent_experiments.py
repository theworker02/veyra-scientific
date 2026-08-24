import json

from veyra.agent import run_agent_experiment
from veyra.mcp_server import agent_run_experiment_tool


def test_agent_run_records_user_request_parameters_and_assertion():
    result = run_agent_experiment(
        "Simulate a 42 m/s projectile launched at 38 degrees.",
        "projectile",
        {"velocity": 42, "angle_deg": 38, "drag_coefficient": 0.0},
        ["mean_range > 100"],
    )
    assert result.all_checks_passed()
    assert result.kind == "agent experiment"
    assert result.inputs["catalog_model"] == "projectile"
    assert result.details["agent"]["execution"] == "local Veyra kernel"
    assert any(
        check.name == "agent assertion: mean_range > 100" and check.passed
        for check in result.checks
    )


def test_agent_run_rejects_unrequested_or_invalid_catalog_inputs_before_execution():
    missing_request = run_agent_experiment("", "projectile", {"velocity": 42})
    assert not missing_request.all_checks_passed()
    assert missing_request.checks[0].name == "user request provided"

    out_of_range = run_agent_experiment("Run it", "projectile", {"angle_deg": 120})
    assert not out_of_range.all_checks_passed()
    assert out_of_range.checks[0].name == "catalog parameter bounds"

    non_finite = run_agent_experiment("Run it", "projectile", {"velocity": float("nan")})
    assert not non_finite.all_checks_passed()
    assert "finite" in non_finite.checks[0].detail

    unknown = run_agent_experiment("Run it", "projectile", {"shell_command": 1})
    assert not unknown.all_checks_passed()
    assert unknown.checks[0].name == "known parameters"


def test_agent_run_mcp_tool_returns_structured_evidence():
    output = agent_run_experiment_tool(
        "Check an Atwood machine with a heavier first mass.",
        "atwood",
        {"m1": 1.2, "m2": 1.0},
        ["acceleration > 0"],
    )
    payload = json.loads(output[output.rfind("\n{") + 1 :])
    assert payload["kind"] == "agent experiment"
    assert payload["details"]["agent"]["model"] == "atwood"
    assert payload["integrity"] == 1.0
