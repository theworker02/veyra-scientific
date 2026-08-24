from veyra.api import experiment_card, session_payload
from veyra.physics import simulate_bernoulli, simulate_oscillator
from veyra.stats import fit_model


def test_oscillator_dissipates_energy():
    result = simulate_oscillator(mass=1.0, stiffness=16.0, damping=0.5, duration=6.0)
    assert result.all_checks_passed()
    e0 = next(float(m.value) for m in result.metrics if m.name == "energy initial")
    e1 = next(float(m.value) for m in result.metrics if m.name == "energy final")
    assert e1 < e0
    plot = result.details["plot"]
    assert plot["kind"] == "phase"
    assert plot["series"][0]["x"]


def test_bernoulli_head_closes():
    result = simulate_bernoulli()
    assert result.all_checks_passed()
    residual = next(float(m.value) for m in result.metrics if m.name == "head residual")
    assert residual < 1e-12


def test_fit_exposes_residuals_for_ui():
    result = fit_model([0, 1, 2, 3, 4], [0.0, 2.0, 4.0, 6.0, 8.0], "linear")
    assert result.all_checks_passed()
    plot = result.details["plot"]
    assert plot["kind"] == "residuals"
    assert "residuals" in result.details
    assert len(result.details["residuals"]) == 5


def test_session_json_shape():
    osc = simulate_oscillator(duration=3.0)
    card = experiment_card(osc)
    assert "plot" in card
    assert "metrics" in card
    assert "integrity" in card
    payload = session_payload([osc], [])
    assert payload["veyra"] == "4.8.0"
    assert payload["experiments"][0]["run_id"] == osc.run_id
    assert "methods" in card
    assert card["model"] == "oscillator"
    pinned = session_payload([osc], [], pinned=[osc.run_id], titles={osc.run_id: "Bench oscillator"})
    assert pinned["experiments"][0]["pinned"] is True
    assert pinned["experiments"][0]["alias"] == "Bench oscillator"


def test_run_prefs_and_delete(tmp_path):
    from veyra.reproduce import delete_run, load_prefs, save_prefs, store

    osc = simulate_oscillator(duration=2.0)
    store(osc, tmp_path)
    save_prefs(tmp_path, {"pinned": [osc.run_id], "titles": {osc.run_id: "Keep"}})
    prefs = load_prefs(tmp_path)
    assert osc.run_id in prefs["pinned"]
    assert delete_run(osc.run_id, tmp_path) is True
    assert delete_run(osc.run_id, tmp_path) is False
