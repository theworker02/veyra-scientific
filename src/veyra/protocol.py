"""Methods paragraphs for a laboratory run — what was actually computed."""

from __future__ import annotations

from typing import Any

from veyra.core import VERSION, VeyraResult


def methods_paragraph(result: VeyraResult) -> str:
    declared = "; ".join(f"{_plain(key)} {value}" for key, value in result.inputs.items()) or "none recorded"
    passed = sum(1 for check in result.checks if check.passed)
    total = len(result.checks)
    solver = result.solver or "unspecified solver"
    return (
        f"This computation was produced by Veyra Scientific {VERSION}, a local deterministic engine. "
        f"Experiment: {result.title} ({result.kind}). Solver: {solver}. "
        f"Declared conditions: {declared}. "
        f"Integrity: {passed}/{total} checks passed. Run fingerprint {result.run_id}."
    )


def methods_from_record(record: dict[str, Any]) -> str:
    result = VeyraResult(
        ok=bool(record.get("ok", True)),
        kind=str(record.get("kind") or "experiment"),
        title=str(record.get("title") or "Run"),
        solver=str(record.get("solver") or ""),
        inputs=dict(record.get("inputs") or {}),
        run_id=str(record.get("run_id") or ""),
        checks=[],
    )
    from veyra.core import Check

    for item in record.get("checks") or []:
        result.checks.append(Check(item.get("name", "check"), bool(item.get("passed")), item.get("detail", "")))
    if not result.run_id:
        result.run_id = result.fingerprint()
    return methods_paragraph(result)


def methods_page(record: dict[str, Any]) -> str:
    """One-page HTML methods artifact a person can keep or print."""
    from html import escape

    methods = methods_from_record(record)
    title = escape(str(record.get("title") or "Run"))
    kind = escape(str(record.get("kind") or ""))
    solver = escape(str(record.get("solver") or ""))
    run_id = escape(str(record.get("run_id") or ""))
    version = escape(str(record.get("veyra_version") or VERSION))
    created = escape(str(record.get("created_at") or ""))
    ok = bool(record.get("ok"))
    integrity = "PASS" if ok else "FAIL"
    integrity_color = "#10a37f" if ok else "#6e6e6e"
    checks = record.get("checks") or []
    metrics = record.get("metrics") or []
    inputs = record.get("inputs") or {}
    check_rows = []
    for item in checks:
        mark = "+" if item.get("passed") else "x"
        name = escape(str(item.get("name") or "check"))
        detail = escape(str(item.get("detail") or ""))
        check_rows.append(
            f'<tr><td class="mark">{mark}</td><td>{name}'
            + (f'<span class="detail"> {detail}</span>' if detail else "")
            + "</td></tr>"
        )
    metric_rows = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        name = escape(str(item.get("name") or ""))
        value = escape(str(item.get("value", "")))
        unit = escape(str(item.get("unit") or ""))
        metric_rows.append(
            f"<tr><td>{name}</td><td class='num'>{value}{(' ' + unit) if unit else ''}</td></tr>"
        )
    input_rows = []
    for key, value in inputs.items():
        input_rows.append(f"<tr><td>{escape(_plain(str(key)))}</td><td class='num'>{escape(str(value))}</td></tr>")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Veyra methods · {title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&display=swap" rel="stylesheet" />
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #ffffff;
      color: #0d0d0d;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      font-size: 15px;
      line-height: 1.6;
    }}
    main {{ max-width: 40rem; margin: 0 auto; padding: 3rem 1.5rem 4rem; }}
    h1 {{ font-size: 28px; font-weight: 500; letter-spacing: -0.02em; margin: 0; }}
    .kicker {{ font-size: 12px; font-weight: 500; color: #6e6e6e; letter-spacing: 0.08em; text-transform: uppercase; }}
    .integrity {{ color: {integrity_color}; font-weight: 500; font-size: 13px; }}
    .meta {{ color: #6e6e6e; font-size: 13px; font-variant-numeric: tabular-nums; }}
    hr {{ border: 0; border-top: 1px solid #e5e5e5; margin: 2rem 0; }}
    p.methods {{ color: #3c3c3c; max-width: 42em; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ text-align: left; font-weight: 400; color: #6e6e6e; padding: 0.6rem 0; border-bottom: 1px solid #e5e5e5; }}
    td {{ padding: 0.55rem 0; border-bottom: 1px solid #e5e5e5; vertical-align: top; }}
    td.num {{ font-variant-numeric: tabular-nums; }}
    td.mark {{ width: 1.5rem; color: #6e6e6e; }}
    .detail {{ color: #9b9b9b; }}
    @media print {{
      body {{ background: #fff; }}
      main {{ padding: 0; }}
    }}
  </style>
</head>
<body>
  <main>
    <p class="kicker">Veyra Scientific {version}</p>
    <h1>{title}</h1>
    <p class="meta">{kind} · {solver}</p>
    <p class="integrity">{integrity}</p>
    <p class="meta">Run {run_id}{(' · ' + created) if created else ''}</p>
    <hr />
    <p class="kicker">Methods</p>
    <p class="methods">{escape(methods)}</p>
    <hr />
    <p class="kicker">Conditions</p>
    <table>
      <tbody>
        {''.join(input_rows) or '<tr><td>none recorded</td></tr>'}
      </tbody>
    </table>
    <hr />
    <p class="kicker">Checks</p>
    <table>
      <tbody>
        {''.join(check_rows) or '<tr><td>none</td></tr>'}
      </tbody>
    </table>
    <hr />
    <p class="kicker">Metrics</p>
    <table>
      <thead><tr><th>Quantity</th><th>Value</th></tr></thead>
      <tbody>
        {''.join(metric_rows) or '<tr><td>none</td></tr>'}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def _plain(key: str) -> str:
    return str(key).replace("_", " ")
