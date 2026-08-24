from pathlib import Path

from veyra.catalog import catalog_payload, guess_model, scaffold_experiment
from veyra.core import VERSION
from veyra.dsl import run_path
from veyra.physics import simulate_escape, simulate_lc, simulate_lens


def test_version_is_4_4():
    assert VERSION == "4.8.0"


def test_lc_matches_closed_form():
    result = simulate_lc(inductance=0.5, capacitance=2e-6, q0=1e-6, duration=0.02)
    assert result.all_checks_passed()
    rms = next(float(m.value) for m in result.metrics if m.name == "RMS error")
    assert rms < 1e-9
    assert guess_model(result.kind) == "lc"


def test_thin_lens_gaussian_identity():
    result = simulate_lens(focal_length=0.05, object_distance=0.12)
    assert result.all_checks_passed()
    image = next(float(m.value) for m in result.metrics if m.name == "image distance")
    assert image > 0
    mag = next(float(m.value) for m in result.metrics if m.name == "magnification")
    assert mag < 0
    assert guess_model(result.kind) == "lens"


def test_escape_sqrt2_identity():
    result = simulate_escape(altitude_m=0.0)
    assert result.all_checks_passed()
    speed = next(float(m.value) for m in result.metrics if m.name == "escape speed")
    assert 11_000 < speed < 11_300
    ratio = next(float(m.value) for m in result.metrics if m.name == "escape / circular")
    assert abs(ratio - 2**0.5) < 1e-12
    assert guess_model(result.kind) == "escape"


def test_catalog_includes_44_models():
    payload = catalog_payload()
    ids = {entry["id"] for entry in payload["entries"]}
    assert {"lc", "lens", "escape", "rl", "kepler"} <= ids
    assert payload["veyra"] == "4.8.0"
    assert payload["count"] >= 24


def test_scaffold_experiment_is_runnable(tmp_path: Path):
    text = scaffold_experiment("lc")
    dest = tmp_path / "lc.veyra"
    dest.write_text(text, encoding="utf-8")
    results = run_path(dest)
    assert results
    assert results[0].all_checks_passed()
    assert "model lc" in text
