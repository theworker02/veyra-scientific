from veyra.geometry import geometry_intersect, geometry_measure


def test_distance():
    result = geometry_measure("distance", points=[[0, 0], [3, 4]])
    assert abs(float(result.metrics[0].value) - 5) < 1e-12


def test_aabb_overlap():
    result = geometry_intersect(
        {"type": "aabb", "min": [0, 0, 0], "max": [2, 2, 2]},
        {"type": "aabb", "min": [1, 1, 1], "max": [3, 3, 3]},
    )
    volume = next(m.value for m in result.metrics if m.name == "overlap volume")
    assert abs(float(volume) - 1) < 1e-12
