from veyra.mathematics import simplify_expression, solve_equation, solve_linear_system


def test_solve_cubic():
    result = solve_equation("x**3 - 6*x**2 + 11*x - 6 = 0")
    assert result.ok
    roots = sorted(float(m.value) for m in result.metrics if m.name.startswith("root"))
    assert roots == [1.0, 2.0, 3.0]


def test_simplify_square():
    result = simplify_expression("x**2 + 2*x + 1")
    assert "x + 1" in str(result.metrics[2].value) or "(x + 1)**2" in str(result.metrics[0].value)


def test_linear_system():
    result = solve_linear_system([[2, 1], [1, 1]], [4, 3])
    assert result.ok
    xs = {m.name: m.value for m in result.metrics}
    assert abs(xs["x1"] - 1) < 1e-9
    assert abs(xs["x2"] - 2) < 1e-9
