from pathlib import Path

from veyra.dsl import parse_veyra, run_experiment, run_suite

ROOT = Path(__file__).resolve().parents[1]


def test_parse_projectile():
    text = (ROOT / "examples" / "projectile.veyra").read_text(encoding="utf-8")
    experiments = parse_veyra(text)
    assert experiments[0].name == "projectile"
    assert "velocity" in experiments[0].inputs


def test_run_collision_example():
    text = (ROOT / "examples" / "collision.veyra").read_text(encoding="utf-8")
    result = run_experiment(parse_veyra(text)[0])
    assert result.all_checks_passed()


def test_suite_examples():
    result = run_suite(ROOT / "examples")
    assert result.metrics[0].value >= 8
    assert result.ok
