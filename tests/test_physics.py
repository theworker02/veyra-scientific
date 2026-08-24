import math

from veyra.physics import simulate_collision, simulate_motion, simulate_orbit


def test_vacuum_projectile_range():
    result = simulate_motion(velocity=38, angle_deg=47, gravity=9.80665)
    expected = 38**2 * math.sin(math.radians(94)) / 9.80665
    got = next(m.value for m in result.metrics if m.name == "Mean range")
    assert abs(float(got) - expected) < 1e-6


def test_elastic_collision_conservation():
    result = simulate_collision(2, 1, 3, -1, 1)
    assert result.all_checks_passed()


def test_circular_orbit_stays_up():
    result = simulate_orbit(duration_s=5400)
    assert result.ok
    peri = next(m.value for m in result.metrics if m.name == "periapsis")
    assert float(peri) > 6_371_000
