from veyra.catalog import catalog_payload, guess_model
from veyra.core import VERSION
from veyra.physics import simulate_freefall, simulate_kepler, simulate_rl
from veyra.server import lab_health


def test_version_is_4_3():
    assert VERSION == "4.7.0"


def test_rl_matches_closed_form():
    result = simulate_rl(resistance=10, inductance=0.5, v_source=12, duration=0.4)
    assert result.all_checks_passed()
    rms = next(float(m.value) for m in result.metrics if m.name == "RMS error")
    assert rms < 1e-4
    assert result.details["plot"]["series"]
    assert guess_model(result.kind) == "rl"


def test_freefall_matches_closed_form():
    result = simulate_freefall(y0=80, v0=0, duration=4)
    assert result.all_checks_passed()
    y_final = next(float(m.value) for m in result.metrics if m.name == "y final")
    y_exact = next(float(m.value) for m in result.metrics if m.name == "y exact final")
    assert abs(y_final - y_exact) < 1e-4
    assert guess_model(result.kind) == "freefall"


def test_kepler_third_law():
    result = simulate_kepler(altitude_m=400_000)
    assert result.all_checks_passed()
    minutes = next(float(m.value) for m in result.metrics if m.name == "period minutes")
    assert 90 < minutes < 95
    assert result.details["table"]
    assert guess_model(result.kind) == "kepler"


def test_catalog_includes_43_models():
    payload = catalog_payload()
    ids = {entry["id"] for entry in payload["entries"]}
    assert {"rl", "freefall", "kepler", "rc", "orbit"} <= ids
    assert payload["veyra"] == "4.7.0"
    assert payload["count"] >= 21


def test_lab_health_payload():
    payload = lab_health()
    assert payload["ok"]
    assert payload["veyra"] == "4.7.0"
    assert payload["models"] >= 21
    assert payload["laboratory"].startswith("http://127.0.0.1:8765")
