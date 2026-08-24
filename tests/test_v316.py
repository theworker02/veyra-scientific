from veyra.catalog import catalog_payload, guess_model
from veyra.core import VERSION
from veyra.mathematics import math_console
from veyra.physics import simulate_heat, simulate_range_table, simulate_rc
from veyra.units import convert_quantity


def test_version_is_current():
    assert VERSION == "4.7.0"


def test_heat_obeys_maximum_principle():
    result = simulate_heat(length=0.2, alpha=1e-4, duration=8.0, n=41)
    assert result.all_checks_passed()
    mid = next(float(m.value) for m in result.metrics if m.name == "midpoint T")
    assert 273.15 <= mid <= 373.15
    assert result.details["plot"]["series"]


def test_rc_matches_closed_form():
    result = simulate_rc(resistance=1000, capacitance=1e-6, v_source=5, duration=0.008)
    assert result.all_checks_passed()
    rms = next(float(m.value) for m in result.metrics if m.name == "RMS error")
    assert rms < 1e-4


def test_vacuum_range_table_peaks_at_45():
    result = simulate_range_table(velocity=38, drag_coefficient=0.0)
    assert result.all_checks_passed()
    angle = next(float(m.value) for m in result.metrics if m.name == "optimum angle")
    assert abs(angle - 45.0) <= 5.0
    assert result.details["table"]


def test_catalog_includes_new_models():
    payload = catalog_payload()
    ids = {entry["id"] for entry in payload["entries"]}
    assert {"diffusion", "rc", "range", "projectile"} <= ids
    assert guess_model("1D heat diffusion") == "diffusion"


def test_math_console_solves():
    result = math_console("x^3 - 6*x^2 + 11*x - 6 = 0", "solve")
    assert result.ok
    assert result.metrics


def test_convert_speed():
    result = convert_quantity("38 m/s", "km/h")
    assert result.all_checks_passed()
    converted = next(float(m.value) for m in result.metrics if m.name == "to")
    assert abs(converted - 136.8) < 0.05
