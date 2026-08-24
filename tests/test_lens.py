from pathlib import Path

from veyra.lens import inspect_expression, inspect_file_result

ROOT = Path(__file__).resolve().parents[1]


def test_gravity_canonical():
    result = inspect_expression("G * ((m1 * m2) / r**2)")
    assert result.ok
    assert any("Newtonian" in str(m.value) for m in result.metrics)


def test_gravity_wrong_operator():
    result = inspect_expression("G * ((m1 + m2) / r**2)")
    assert any(c.name == "scientific consistency" and not c.passed for c in result.checks)


def test_file_skips_scientific_literals():
    source = (ROOT / "examples" / "inconsistent.py").read_text(encoding="utf-8")
    result = inspect_file_result(source, "inconsistent.py")
    hits = result.details["hits"]
    assert all(hit["lhs"] != "G" for hit in hits)
    assert any(hit["lhs"] == "F" and hit["ok"] is False for hit in hits)
