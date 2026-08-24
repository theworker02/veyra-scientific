from veyra.format import format_quantity, integrity_label


def test_uncertainty_alignment():
    text = format_quantity(37.2702, "m", 0.512)
    assert "37.27" in text
    assert "0.51" in text
    assert text.endswith("m")


def test_si_prefix_energy():
    text = format_quantity(1221.0, "J")
    assert "kJ" in text


def test_integrity_labels():
    assert integrity_label(1.0) == "PASS"
    assert integrity_label(0.5) == "FAIL"
