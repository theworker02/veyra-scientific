"""2D/3D geometry kernel."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from veyra.core import Check, Metric, VeyraResult


def _as_array(points: list[list[float]]) -> np.ndarray:
    return np.array(points, dtype=float)


def geometry_measure(
    kind: str,
    points: list[list[float]] | None = None,
    radius: float | None = None,
    dimensions: list[float] | None = None,
) -> VeyraResult:
    pts = _as_array(points) if points else np.zeros((0, 2))
    if kind == "distance":
        if len(pts) < 2:
            return _fail("need two points")
        value = float(np.linalg.norm(pts[1] - pts[0]))
        return _ok("distance", [Metric("distance", value, "m")], {"points": points})
    if kind == "area_polygon":
        area = _polygon_area(pts)
        return _ok("polygon area", [Metric("area", abs(area), "m²")], {"signed_area": area})
    if kind == "area_circle":
        r = float(radius or 0)
        return _ok("circle area", [Metric("area", math.pi * r**2, "m²")], {"radius": r})
    if kind == "volume_sphere":
        r = float(radius or 0)
        return _ok("sphere volume", [Metric("volume", 4 / 3 * math.pi * r**3, "m³")], {"radius": r})
    if kind == "volume_box":
        dims = dimensions or [1, 1, 1]
        vol = float(np.prod(dims))
        return _ok("box volume", [Metric("volume", vol, "m³")], {"dimensions": dims})
    if kind == "triangle":
        if len(pts) < 3:
            return _fail("need three points")
        a, b, c = pts[0], pts[1], pts[2]
        area = 0.5 * float(np.linalg.norm(np.cross(_pad3(b - a), _pad3(c - a))))
        return _ok("triangle", [Metric("area", area, "m²")], {"points": points})
    return _fail(f"unknown measure '{kind}'")


def geometry_intersect(
    shape_a: dict[str, Any],
    shape_b: dict[str, Any],
) -> VeyraResult:
    kind = f"{shape_a.get('type', '')}-{shape_b.get('type', '')}"
    if shape_a.get("type") == "aabb" and shape_b.get("type") == "aabb":
        hit, volume, centroid = _aabb_intersect(shape_a, shape_b)
        return VeyraResult(
            ok=True,
            kind="AABB intersection",
            title="Geometry intersection",
            checks=[Check("intersection detected" if hit else "no intersection", True)],
            metrics=[
                Metric("intersects", "yes" if hit else "no"),
                Metric("overlap volume", volume, "m³"),
                Metric("centroid", str(centroid)),
            ],
            details={"centroid": centroid, "kind": kind},
            inputs={"a": shape_a, "b": shape_b},
            solver="axis-aligned overlap",
        )
    if shape_a.get("type") == "sphere" and shape_b.get("type") == "sphere":
        c1 = np.array(shape_a["center"], dtype=float)
        c2 = np.array(shape_b["center"], dtype=float)
        r1, r2 = float(shape_a["radius"]), float(shape_b["radius"])
        dist = float(np.linalg.norm(c1 - c2))
        hit = dist <= r1 + r2
        return VeyraResult(
            ok=True,
            kind="sphere intersection",
            title="Geometry intersection",
            checks=[Check("intersection detected" if hit else "no intersection", True)],
            metrics=[
                Metric("distance", dist, "m"),
                Metric("intersects", "yes" if hit else "no"),
            ],
            inputs={"a": shape_a, "b": shape_b},
            solver="sphere-sphere",
        )
    if shape_a.get("type") == "segment" and shape_b.get("type") == "segment":
        hit, point = _segment_intersect(shape_a["a"], shape_a["b"], shape_b["a"], shape_b["b"])
        return VeyraResult(
            ok=True,
            kind="segment intersection",
            title="Geometry intersection",
            checks=[Check("intersection detected" if hit else "no intersection", True)],
            metrics=[Metric("point", str(point) if point is not None else "none")],
            details={"point": point},
            inputs={"a": shape_a, "b": shape_b},
            solver="2D segment intersection",
        )
    return _fail(f"unsupported pair {kind}")


def geometry_transform(
    points: list[list[float]],
    translate: list[float] | None = None,
    scale: float | list[float] = 1.0,
    rotate_deg: float = 0.0,
    axis: str = "z",
) -> VeyraResult:
    pts = _as_array(points)
    dim = pts.shape[1]
    if isinstance(scale, list):
        pts = pts * np.array(scale, dtype=float)
    else:
        pts = pts * float(scale)
    if rotate_deg:
        pts = _rotate(pts, math.radians(rotate_deg), axis)
    if translate:
        pts = pts + np.array(translate, dtype=float)[:dim]
    return VeyraResult(
        ok=True,
        kind="transform",
        title="Geometry transform",
        checks=[Check("transform applied", True)],
        metrics=[Metric("points", len(pts))],
        details={"points": pts.tolist()},
        inputs={"translate": translate or [0, 0, 0], "scale": scale, "rotate_deg": rotate_deg},
        solver="affine",
    )


def geometry_validate(points: list[list[float]], kind: str = "polygon") -> VeyraResult:
    pts = _as_array(points)
    finite = bool(np.isfinite(pts).all())
    checks = [Check("finite coordinates", finite)]
    if kind == "polygon":
        area = _polygon_area(pts)
        checks.append(Check("non-zero area", abs(area) > 1e-12, f"area={area:.6g}"))
        checks.append(Check("simple orientation", True, "CCW" if area > 0 else "CW"))
    if kind == "mesh":
        checks.append(Check("at least 3 vertices", len(pts) >= 3))
    return VeyraResult(
        ok=all(c.passed for c in checks),
        kind="topology validation",
        title="Geometry validate",
        checks=checks,
        metrics=[Metric("vertices", len(pts))],
        inputs={"kind": kind, "n": len(pts)},
        solver="computational geometry checks",
    )


def geometry_nearest(origin: list[float], points: list[list[float]]) -> VeyraResult:
    pts = _as_array(points)
    o = np.array(origin, dtype=float)
    dists = np.linalg.norm(pts - o, axis=1)
    idx = int(np.argmin(dists))
    return VeyraResult(
        ok=True,
        kind="nearest neighbor",
        title="Geometry nearest",
        checks=[Check("query computed", True)],
        metrics=[
            Metric("index", idx),
            Metric("distance", float(dists[idx]), "m"),
        ],
        details={"point": pts[idx].tolist()},
        inputs={"origin": origin, "n": len(points)},
        solver="L2 nearest",
    )


def geometry_construct(kind: str, **kwargs: Any) -> VeyraResult:
    if kind == "regular_polygon":
        n = int(kwargs.get("sides", 6))
        r = float(kwargs.get("radius", 1.0))
        pts = [
            [r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)]
            for i in range(n)
        ]
        return VeyraResult(
            ok=n >= 3,
            kind="construction",
            title="Regular polygon",
            checks=[Check("sides >= 3", n >= 3)],
            metrics=[Metric("area", abs(_polygon_area(np.array(pts))), "m²")],
            details={"points": pts},
            inputs={"sides": n, "radius": r},
        )
    return _fail(f"unknown construct '{kind}'")


def geometry_sample(kind: str, count: int = 16, radius: float = 1.0, seed: int = 0) -> VeyraResult:
    rng = np.random.default_rng(seed)
    if kind == "disk":
        rho = np.sqrt(rng.random(count)) * radius
        theta = rng.random(count) * 2 * math.pi
        pts = np.column_stack([rho * np.cos(theta), rho * np.sin(theta)])
    elif kind == "sphere":
        z = rng.uniform(-1, 1, count)
        phi = rng.uniform(0, 2 * math.pi, count)
        rxy = np.sqrt(1 - z**2) * radius
        pts = np.column_stack([rxy * np.cos(phi), rxy * np.sin(phi), z * radius])
    else:
        pts = rng.normal(size=(count, 3))
    return VeyraResult(
        ok=True,
        kind="sampling",
        title="Geometry sample",
        checks=[Check("samples drawn", True)],
        metrics=[Metric("count", count)],
        details={"points": pts.tolist()},
        seed=seed,
        solver=kind,
    )


def geometry_mesh_analysis(vertices: list[list[float]], faces: list[list[int]]) -> VeyraResult:
    verts = _as_array(vertices)
    n_v, n_f = len(verts), len(faces)
    edge_set: set[tuple[int, int]] = set()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            edge_set.add(tuple(sorted((a, b))))
    n_e = len(edge_set)
    chi = n_v - n_e + n_f
    return VeyraResult(
        ok=True,
        kind="mesh analysis",
        title="Mesh",
        checks=[Check("Euler characteristic computed", True, f"χ={chi}")],
        metrics=[
            Metric("vertices", n_v),
            Metric("edges", n_e),
            Metric("faces", n_f),
            Metric("chi", chi),
        ],
        inputs={"vertices": n_v, "faces": n_f},
        solver="Euler characteristic",
    )


def _polygon_area(pts: np.ndarray) -> float:
    if len(pts) < 3:
        return 0.0
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _pad3(v: np.ndarray) -> np.ndarray:
    if v.size == 3:
        return v
    out = np.zeros(3)
    out[: v.size] = v
    return out


def _rotate(pts: np.ndarray, angle: float, axis: str) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    if pts.shape[1] == 2:
        rot = np.array([[c, -s], [s, c]])
        return pts @ rot.T
    if axis == "x":
        rot = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    elif axis == "y":
        rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    else:
        rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    padded = pts if pts.shape[1] == 3 else np.column_stack([pts, np.zeros(len(pts))])
    return padded @ rot.T


def _aabb_intersect(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, float, list[float]]:
    min_a, max_a = np.array(a["min"], dtype=float), np.array(a["max"], dtype=float)
    min_b, max_b = np.array(b["min"], dtype=float), np.array(b["max"], dtype=float)
    low = np.maximum(min_a, min_b)
    high = np.minimum(max_a, max_b)
    if np.any(high < low):
        return False, 0.0, [0.0, 0.0, 0.0]
    overlap = high - low
    volume = float(np.prod(np.maximum(overlap, 0)))
    centroid = ((low + high) / 2).tolist()
    return True, volume, centroid


def _segment_intersect(
    a1: list[float], a2: list[float], b1: list[float], b2: list[float]
) -> tuple[bool, list[float] | None]:
    p, r = np.array(a1, dtype=float), np.array(a2, dtype=float) - np.array(a1, dtype=float)
    q, s = np.array(b1, dtype=float), np.array(b2, dtype=float) - np.array(b1, dtype=float)
    rxs = float(r[0] * s[1] - r[1] * s[0])
    q_p = q - p
    if abs(rxs) < 1e-12:
        return False, None
    t = float(q_p[0] * s[1] - q_p[1] * s[0]) / rxs
    u = float(q_p[0] * r[1] - q_p[1] * r[0]) / rxs
    if 0 <= t <= 1 and 0 <= u <= 1:
        point = (p + t * r).tolist()
        return True, point
    return False, None


def _ok(title: str, metrics: list[Metric], details: dict[str, Any]) -> VeyraResult:
    return VeyraResult(
        ok=True,
        kind="geometry",
        title=title,
        checks=[Check("measured", True)],
        metrics=metrics,
        details=details,
        solver="geometry kernel",
    )


def _fail(message: str) -> VeyraResult:
    return VeyraResult(
        ok=False,
        kind="geometry",
        title="Geometry",
        checks=[Check("valid input", False, message)],
    )
