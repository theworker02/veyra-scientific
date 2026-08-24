from veyra.units import dimensional_formula, parse_measured, validate_units


def test_parse_uncertainty():
    measured = parse_measured("38.0 ± 0.3 m/s")
    assert measured.value == 38.0
    assert measured.uncertainty == 0.3


def test_energy_dimension():
    from veyra.units import Q_

    assert "M" in dimensional_formula(Q_(1, "joule"))
    assert "L" in dimensional_formula(Q_(1, "joule"))


def test_validate_units():
    result = validate_units({"velocity": "38 m/s", "angle": "47 deg"})
    assert result.ok
