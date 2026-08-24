from veyra.catalog import catalog_payload, guess_model, sweep_model
from veyra.core import VERSION
from veyra.physics import simulate_atwood, simulate_cooling, simulate_decay
from veyra.reproduce import reproduce, store


def test_version_is_4_2():
    assert VERSION == "4.7.0"


def test_cooling_matches_closed_form():
    result = simulate_cooling(t0=363.15, t_env=293.15, k=0.05, duration=80.0)
    assert result.all_checks_passed()
    rms = next(float(m.value) for m in result.metrics if m.name == "RMS error")
    assert rms < 0.05
    assert result.details["plot"]["series"]


def test_decay_half_life_identity():
    result = simulate_decay(n0=1000, half_life=10, duration=40)
    assert result.all_checks_passed()
    lam = next(float(m.value) for m in result.metrics if m.name == "lambda")
    assert abs(lam - 0.069314718) < 1e-6


def test_atwood_tension_identity():
    result = simulate_atwood(m1=1.2, m2=1.0)
    assert result.all_checks_passed()
    accel = next(float(m.value) for m in result.metrics if m.name == "acceleration")
    assert accel > 0
    assert guess_model(result.kind) == "atwood"


def test_catalog_includes_42_models():
    payload = catalog_payload()
    ids = {entry["id"] for entry in payload["entries"]}
    assert {"cooling", "decay", "atwood", "projectile"} <= ids
    assert payload["veyra"] == "4.7.0"


def test_sweep_projectile_speed(tmp_path):
    result = sweep_model("projectile", "velocity", 20, 40, 5, {"angle_deg": 45, "drag_coefficient": 0, "trials": 1})
    assert result.ok
    assert result.details["table"]
    assert len(result.details["plot"]["series"][0]["x"]) == 5


def test_reproduce_uses_catalog_model(tmp_path):
    original = simulate_atwood(m1=1.5, m2=1.0)
    store(original, tmp_path, model="atwood")
    replay = reproduce(original.run_id, tmp_path)
    assert replay.ok
    assert any(check.name == "reproduced from fingerprint" for check in replay.checks)


def test_lab_status_reports_kernel():
    import json

    from veyra.mcp_server import lab_status_tool

    payload = json.loads(lab_status_tool())
    assert payload["veyra"] == "4.7.0"
    assert payload["laboratory"].startswith("http://127.0.0.1:8765")
    assert isinstance(payload["running"], bool)
    assert payload["models"] >= 4
    assert "python -m veyra serve" in payload["start"]


def test_doctor_exits_zero():
    from typer.testing import CliRunner

    from veyra.cli import app

    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "laboratory" in result.stdout.lower()
    assert "veyra" in result.stdout.lower()
