from veyra.mathematics import solve_equation
from veyra.physics import run_named, simulate_motion, simulate_pendulum
from veyra.report import render_session, svg_trajectory


def test_caret_is_exponentiation():
    result = solve_equation("x^3 - 6*x^2 + 11*x - 6 = 0")
    roots = sorted(float(m.value) for m in result.metrics if m.name.startswith("root"))
    assert roots == [1.0, 2.0, 3.0]


def test_drag_shortens_range():
    vacuum = simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.0)
    drag = simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.15, trials=8)
    vac_range = next(float(m.value) for m in vacuum.metrics if m.name == "Mean range")
    drag_range = next(float(m.value) for m in drag.metrics if m.name == "Mean range")
    assert drag.solver.startswith("vectorized RK4")
    assert drag_range < vac_range


def test_orbit_dispatch_is_not_projectile():
    result = run_named("orbit", duration_s=1800)
    assert "orbital" in result.kind


def test_pendulum_conserves_energy():
    result = simulate_pendulum(length=1.0, theta0=0.15, duration=4.0)
    assert result.all_checks_passed()


def test_workbench_contains_instrument_chrome():
    motion = simulate_motion(velocity=38, angle_deg=47, drag_coefficient=0.1, trials=8)
    html = render_session([motion], [])
    assert "Veyra Scientific" in html
    assert "Laboratory" in html
    assert "<svg" in html
    assert motion.run_id in html


def test_svg_envelope_renders():
    svg = svg_trajectory(
        [{"x": [0, 1, 2], "y": [0, 1, 0]}],
        {"x": [0, 1, 2], "y_lo": [0, 0.5, 0], "y_hi": [0, 1.2, 0]},
    )
    assert "polyline" in svg
    assert "path" in svg
