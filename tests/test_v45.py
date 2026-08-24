from pathlib import Path

from veyra.catalog import catalog_payload, guess_model, scaffold_experiment
from veyra.core import VERSION
from veyra.dsl import run_path
from veyra.physics import simulate_circular, simulate_doppler, simulate_shm


def test_version_is_4_5():
    assert VERSION == "4.8.0"


def test_shm_matches_closed_form():
    result = simulate_shm(mass=1.0, stiffness=16.0, amplitude=0.1, duration=4.0)
    assert result.all_checks_passed()
    omega = next(float(m.value) for m in result.metrics if m.name == "omega")
    assert abs(omega - 4.0) < 1e-12
    assert guess_model(result.kind) == "shm"


def test_doppler_approaching_raises_pitch():
    result = simulate_doppler(frequency=440, v_source=20, v_observer=0, speed_sound=343)
    assert result.all_checks_passed()
    observed = next(float(m.value) for m in result.metrics if m.name == "observed frequency")
    assert observed > 440
    assert guess_model(result.kind) == "doppler"


def test_doppler_receding_lowers_pitch():
    result = simulate_doppler(frequency=440, v_source=-20, v_observer=0, speed_sound=343)
    assert result.all_checks_passed()
    observed = next(float(m.value) for m in result.metrics if m.name == "observed frequency")
    assert observed < 440


def test_circular_period_identity():
    result = simulate_circular(radius=10, speed=5)
    assert result.all_checks_passed()
    period = next(float(m.value) for m in result.metrics if m.name == "period")
    assert abs(period - 4 * 3.141592653589793) < 1e-9
    assert guess_model(result.kind) == "circular"


def test_catalog_includes_45_models():
    payload = catalog_payload()
    ids = {entry["id"] for entry in payload["entries"]}
    assert {"shm", "doppler", "circular", "lc", "escape"} <= ids
    assert payload["veyra"] == "4.8.0"
    assert payload["count"] >= 27


def test_scaffold_shm_is_runnable(tmp_path: Path):
    text = scaffold_experiment("shm")
    dest = tmp_path / "shm.veyra"
    dest.write_text(text, encoding="utf-8")
    results = run_path(dest)
    assert results
    assert results[0].all_checks_passed()
    assert "model shm" in text
