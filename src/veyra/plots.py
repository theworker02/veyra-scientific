"""Plot payloads for the Workbench — JSON series the UI can draw."""

from __future__ import annotations

from typing import Any

import numpy as np


PLOT_POINTS = 220
SOURCE_POINTS = 8000


def downsample(values: np.ndarray | list, n: int = PLOT_POINTS) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size <= n:
        return arr
    idx = np.linspace(0, arr.size - 1, n).astype(int)
    return arr[idx]


def series(ident: str, x, y) -> dict[str, Any]:
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    source_x = downsample(xa, SOURCE_POINTS)
    source_y = downsample(ya, SOURCE_POINTS)
    payload: dict[str, Any] = {
        "id": ident,
        "x": downsample(xa, PLOT_POINTS).tolist(),
        "y": downsample(ya, PLOT_POINTS).tolist(),
        "x_src": source_x.tolist(),
        "y_src": source_y.tolist(),
    }
    return payload


def make_plot(
    kind: str,
    x_label: str,
    y_label: str,
    series_list: list[dict[str, Any]],
    envelope: dict[str, list[float]] | None = None,
    secondary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "x_label": x_label,
        "y_label": y_label,
        "series": series_list,
    }
    if envelope:
        payload["envelope"] = envelope
    if secondary:
        payload["secondary"] = secondary
    return payload
