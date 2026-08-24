"""JSON session payload the Workbench UI consumes."""

from __future__ import annotations

from typing import Any

from veyra.catalog import guess_model
from veyra.core import VERSION, VeyraResult
from veyra.format import format_quantity, integrity_label
from veyra.protocol import methods_paragraph


def experiment_card(result: VeyraResult, model: str | None = None) -> dict[str, Any]:
    score = result.integrity_score()
    plot = result.details.get("plot")
    if not plot:
        paths = result.details.get("paths") or []
        if paths:
            plot = {
                "kind": "trajectory",
                "x_label": "x",
                "y_label": "y",
                "series": [
                    {"id": f"series-{i}", "x": p.get("x", []), "y": p.get("y", [])}
                    for i, p in enumerate(paths[:8])
                    if p.get("x") and p.get("y")
                ],
                "envelope": result.details.get("envelope"),
            }
    metrics = [
        {
            "name": m.name,
            "value": m.value,
            "unit": m.unit,
            "uncertainty": m.uncertainty,
            "text": m.formatted() if hasattr(m, "formatted") else format_quantity(m.value, m.unit, m.uncertainty),
        }
        for m in result.metrics
    ]
    checks = [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in result.checks]
    return {
        "title": result.title,
        "kind": result.kind,
        "solver": result.solver,
        "run_id": result.run_id,
        "ok": result.all_checks_passed(),
        "integrity": score,
        "integrityLabel": integrity_label(score),
        "integrityPct": f"{score:.1%}",
        "inputs": {str(k): str(v) for k, v in result.inputs.items()},
        "metrics": metrics,
        "checks": checks,
        "warnings": list(result.warnings),
        "plot": plot,
        "created_at": result.created_at,
        "seed": result.seed,
        "tolerance": result.tolerance,
        "veyra_version": VERSION,
        "model": model or guess_model(result.kind, result.title),
        "methods": methods_paragraph(result),
        "table": result.details.get("table"),
        "hits": result.details.get("hits"),
        "graph": result.details.get("experiment_graph"),
        "reproducibility": result.details.get("reproducibility"),
        "selected_outputs": result.details.get("selected_outputs"),
    }


def session_payload(
    results: list[VeyraResult],
    history: list[dict[str, Any]] | None = None,
    pinned: list[str] | None = None,
    titles: dict[str, str] | None = None,
) -> dict[str, Any]:
    pinned_ids = list(pinned or [])
    aliases = titles or {}
    cards = [experiment_card(item) for item in results]
    for card in cards:
        run_id = str(card.get("run_id") or "")
        card["pinned"] = run_id in pinned_ids
        if run_id in aliases:
            card["alias"] = aliases[run_id]
    notebook = [
        {
            "run_id": item.get("run_id"),
            "title": aliases.get(str(item.get("run_id") or ""), item.get("title")),
            "kind": item.get("kind"),
            "ok": item.get("ok"),
            "created_at": item.get("created_at"),
        }
        for item in (history or [])[:40]
    ]
    return {
        "veyra": VERSION,
        "tagline": "Don't guess the science. Run it.",
        "experiments": cards,
        "history": notebook,
        "count": len(cards),
        "pinned": pinned_ids,
        "titles": aliases,
    }
