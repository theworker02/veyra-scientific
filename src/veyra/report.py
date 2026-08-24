"""Veyra Workbench — laboratory instrument UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from veyra.api import experiment_card
from veyra.core import VERSION, VeyraResult, json_default
from veyra.design import DARK, DURATION, EASE, FONT_MONO, FONT_SANS, LIGHT, RADIUS, RADIUS_PILL

PALETTE = {
    "bg": LIGHT["bg_soft"],
    "dark": DARK["bg_soft"],
    "text": LIGHT["text"],
    "muted": LIGHT["muted"],
    "success": LIGHT["accent"],
    "fail": LIGHT["danger"],
    "card": LIGHT["surface"],
    "border": LIGHT["border"],
}


def write_report(result: VeyraResult, path: str | Path, plot_png: bytes | None = None) -> Path:
    return write_session([result], path)


def write_session(
    results: list[VeyraResult],
    path: str | Path,
    history: list[dict[str, Any]] | None = None,
) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_session(results, history or []), encoding="utf-8")
    return dest


def plot_paths(paths: list[dict], dark: bool = False) -> bytes:
    import io

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=160)
    bg = DARK["bg"] if dark else LIGHT["bg"]
    muted = DARK["muted"] if dark else LIGHT["muted"]
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    for i, path in enumerate(paths):
        ax.plot(path["x"], path["y"], color=LIGHT["accent"] if i == 0 else muted, lw=1.6, alpha=0.9)
    ax.set_xlabel("Range (m)", color=muted)
    ax.set_ylabel("Altitude (m)", color=muted)
    ax.tick_params(colors=muted)
    for spine in ax.spines.values():
        spine.set_color(LIGHT["border"])
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_session(results: list[VeyraResult], history: list[dict[str, Any]]) -> str:
    cards = [_experiment_payload(item) for item in results]
    selected = cards[0] if cards else _empty_payload()
    nav = "".join(
        f'<button class="rail-item{" on" if i == 0 else ""}" data-go="{i}" type="button">'
        f'<span class="dot {"ok" if item["ok"] else "bad"}"></span>'
        f'<span class="rail-copy"><span class="rail-title">{_esc(item["title"])}</span>'
        f'<span class="rail-kind">{_esc(item["kind"])}</span></span></button>'
        for i, item in enumerate(cards)
    )
    history_rows = "".join(
        f"<tr><td class='mono'>{_esc(item.get('run_id', ''))}</td>"
        f"<td>{_esc(item.get('title', ''))}</td>"
        f"<td><span class='pill {('ok' if item.get('ok') else 'bad')}'>"
        f"{'Pass' if item.get('ok') else 'Fail'}</span></td></tr>"
        for item in history[:20]
    ) or "<tr><td colspan='3' class='quiet'>No prior runs in this workspace.</td></tr>"
    payload = json.dumps(cards, default=json_default)
    history_payload = json.dumps(
        [{"run_id": h.get("run_id"), "title": h.get("title"), "ok": h.get("ok")} for h in history[:20]],
        default=json_default,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Veyra Laboratory</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&display=swap" rel="stylesheet" />
  <style>{_css()}</style>
</head>
<body>
  <div class="app">
    <header class="mast">
      <div class="brand-block">
        <div class="mark" aria-hidden="true"></div>
        <div>
          <div class="eyebrow">Veyra Scientific</div>
          <div class="word">Laboratory</div>
        </div>
      </div>
      <div class="mast-actions">
        <button class="ghost" id="theme" type="button">Theme</button>
        <div id="status" class="status"><span class="live"></span><span id="status-label">Ready</span></div>
      </div>
    </header>
    <div class="stage">
      <aside class="rail">
        <div class="eyebrow">Experiments</div>
        <input id="filter" class="search" type="search" placeholder="Filter" autocomplete="off" />
        <nav id="rail">{nav or '<p class="quiet">No experiments</p>'}</nav>
        <p class="hint">J / K to move · 1–4 views · T theme</p>
      </aside>
      <main class="panel">
        <div class="tabs" role="tablist">
          <button class="tab on" data-view="results" type="button">Results</button>
          <button class="tab" data-view="physics" type="button">Model</button>
          <button class="tab" data-view="integrity" type="button">Integrity</button>
          <button class="tab" data-view="notebook" type="button">Notebook</button>
        </div>
        <section id="view-results">
          <div class="headline">
            <div>
              <h1 id="title">{_esc(selected["title"])}</h1>
              <p class="lede" id="meta">{_esc(selected["kind"])} · {_esc(selected["solver"])}</p>
            </div>
            <span id="badge" class="pill ok">{_esc(selected["integrityLabel"])}</span>
          </div>
          <div id="plot" class="plot-frame">{selected.get("svg") or ""}</div>
          <table class="sheet" id="metrics">{_metrics_html(selected.get("metrics") or [])}</table>
        </section>
        <section id="view-physics" class="hidden">
          <h1>Declared conditions</h1>
          <p class="lede">Inputs the engine actually used. Nothing here is inferred by a model.</p>
          <table class="sheet" id="inputs">{_inputs_html(selected.get("inputs") or {})}</table>
        </section>
        <section id="view-integrity" class="hidden">
          <h1>Scientific integrity</h1>
          <p class="lede" id="integrity-meta">{_esc(selected.get("integrityPct", "100%"))} of checks passed</p>
          <div class="bar" aria-hidden="true"><span id="bar-fill" style="width:{selected.get("integrity", 1)*100:.0f}%"></span></div>
          <ul class="checks" id="checks">{_checks_html(selected.get("checks") or [])}</ul>
        </section>
        <section id="view-notebook" class="hidden">
          <h1>Notebook</h1>
          <p class="lede">Fingerprinted runs stored in this workspace.</p>
          <table class="sheet">
            <thead><tr><th>Run</th><th>Experiment</th><th>Integrity</th></tr></thead>
            <tbody id="notebook">{history_rows}</tbody>
          </table>
        </section>
        <footer class="colophon">
          <span class="mono" id="run">Run { _esc(selected.get("run_id", "")) }</span>
          <span>Veyra {VERSION}</span>
        </footer>
      </main>
    </div>
  </div>
  <script>
    const experiments = {payload};
    const history = {history_payload};
    let index = 0;
    const $ = (id) => document.getElementById(id);
    const tabs = document.querySelectorAll(".tab");
    const themeBtn = $("theme");
    const root = document.documentElement;

    function applyTheme(mode) {{
      root.dataset.theme = mode;
      localStorage.setItem("veyra-theme", mode);
    }}
    applyTheme(localStorage.getItem("veyra-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
    themeBtn.addEventListener("click", () => applyTheme(root.dataset.theme === "dark" ? "light" : "dark"));

    function show(i) {{
      const item = experiments[i];
      if (!item) return;
      index = i;
      document.querySelectorAll(".rail-item").forEach((el, n) => el.classList.toggle("on", n === i));
      $("title").textContent = item.title;
      $("meta").textContent = item.kind + " · " + item.solver;
      $("plot").innerHTML = item.svg || "";
      $("metrics").innerHTML = item.metricsHtml;
      $("inputs").innerHTML = item.inputsHtml;
      $("checks").innerHTML = item.checksHtml;
      $("integrity-meta").textContent = item.integrityPct + " of checks passed";
      $("bar-fill").style.width = Math.round(item.integrity * 100) + "%";
      $("run").textContent = "Run " + item.run_id;
      $("badge").textContent = item.integrityLabel;
      $("badge").className = "pill " + (item.ok ? "ok" : "bad");
      $("status").classList.toggle("fail", !item.ok);
      $("status-label").textContent = item.ok ? "Ready" : "Failed";
    }}

    document.getElementById("rail").addEventListener("click", (event) => {{
      const btn = event.target.closest(".rail-item");
      if (btn) show(Number(btn.dataset.go));
    }});
    tabs.forEach((tab) => tab.addEventListener("click", () => {{
      tabs.forEach((el) => el.classList.toggle("on", el === tab));
      ["results", "physics", "integrity", "notebook"].forEach((name) => {{
        $("view-" + name).classList.toggle("hidden", name !== tab.dataset.view);
      }});
    }}));
    $("filter").addEventListener("input", (event) => {{
      const q = event.target.value.toLowerCase();
      document.querySelectorAll(".rail-item").forEach((el) => {{
        el.hidden = q && !el.textContent.toLowerCase().includes(q);
      }});
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.target.matches("input")) return;
      if (event.key === "j" || event.key === "ArrowDown") show(Math.min(index + 1, experiments.length - 1));
      if (event.key === "k" || event.key === "ArrowUp") show(Math.max(index - 1, 0));
      if (event.key === "t") themeBtn.click();
      if (["1","2","3","4"].includes(event.key)) tabs[Number(event.key) - 1]?.click();
    }});
  </script>
</body>
</html>
"""


def _css() -> str:
    return f"""
:root {{
  --bg: {LIGHT["bg"]};
  --text: {LIGHT["text"]};
  --muted: {LIGHT["muted"]};
  --graphite: {LIGHT["graphite"]};
  --subtle: {LIGHT["subtle"]};
  --border: {LIGHT["border"]};
  --hover: {LIGHT["hover"]};
  --accent: {LIGHT["accent"]};
  --radius: {RADIUS};
  --pill: {RADIUS_PILL};
  --ease: {EASE};
  --ms: {DURATION};
  --sans: {FONT_SANS};
  --mono: {FONT_MONO};
}}
[data-theme="dark"] {{
  --bg: {DARK["bg"]};
  --text: {DARK["text"]};
  --muted: {DARK["muted"]};
  --graphite: {DARK["graphite"]};
  --subtle: {DARK["subtle"]};
  --border: {DARK["border"]};
  --hover: {DARK["hover"]};
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0; min-height: 100%;
  background: var(--bg); color: var(--text);
  font: 16px/1.6 var(--sans); font-weight: 400;
  font-feature-settings: "tnum" 1, "cv11" 1;
}}
:focus-visible {{ box-shadow: 0 0 0 3px rgba(16,163,127,0.12); outline: none; }}
.app {{ max-width: none; padding: 48px 64px 96px; }}
.mast {{
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 24px; padding-bottom: 32px; border-bottom: 1px solid var(--border);
  margin-bottom: 48px;
}}
.brand-block {{ display: flex; align-items: baseline; gap: 16px; }}
.mark {{ display: none; }}
.eyebrow {{
  font-size: 12px; font-weight: 500; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}}
.word {{
  font-family: var(--sans); font-size: 40px; font-weight: 500;
  letter-spacing: -0.02em; line-height: 1.1;
}}
.mast-actions {{ display: flex; align-items: center; gap: 16px; }}
.ghost {{
  background: transparent; border: 0; color: var(--text);
  font: 14px/1 var(--sans); font-weight: 500; height: 40px; padding: 0 14px;
  border-radius: var(--radius); cursor: pointer;
  transition: background var(--ms) var(--ease);
}}
.ghost:hover {{ background: var(--hover); }}
.status {{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 500; color: var(--accent);
}}
.status.fail {{ color: var(--graphite); }}
.live {{ width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}
.stage {{ display: grid; grid-template-columns: 220px 1fr; gap: 64px; }}
.rail {{ background: transparent; border: 0; padding: 0; min-height: 0; }}
.search {{
  width: 100%; margin: 16px 0 8px; height: 40px; padding: 0 14px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg); color: var(--text); font: 14px var(--sans);
}}
.search:focus {{ border-color: var(--accent); }}
.search::placeholder {{ color: var(--subtle); }}
.rail-item {{
  display: flex; gap: 10px; align-items: flex-start; width: 100%;
  text-align: left; background: none; border: 0; border-bottom: 1px solid var(--border);
  color: var(--muted); padding: 12px 0; border-radius: 0; cursor: pointer; font: inherit;
}}
.rail-item:hover {{ color: var(--text); }}
.rail-item.on {{ color: var(--accent); }}
.rail-copy {{ display: flex; flex-direction: column; min-width: 0; }}
.rail-title {{ font-size: 14px; font-weight: 500; }}
.rail-kind {{ font-size: 12px; color: var(--muted); }}
.dot {{ width: 6px; height: 6px; border-radius: 50%; margin-top: 8px; flex: none; background: var(--subtle); }}
.dot.ok {{ background: var(--accent); }}
.hint {{ font-size: 12px; color: var(--subtle); margin: 24px 0 0; }}
.panel {{ background: transparent; border: 0; padding: 0; min-height: 0; }}
.tabs {{
  display: flex; gap: 24px; margin: 0 0 40px;
  border-bottom: 1px solid var(--border);
}}
.tab {{
  background: none; border: 0; border-bottom: 1px solid transparent;
  margin-bottom: -1px; color: var(--muted); cursor: pointer;
  font: 14px/1 var(--sans); font-weight: 500; padding: 0 0 12px;
}}
.tab:hover {{ color: var(--text); }}
.tab.on {{ color: var(--accent); border-bottom-color: var(--accent); }}
h1 {{
  margin: 0; font-size: 36px; font-weight: 500; letter-spacing: -0.02em; line-height: 1.15;
}}
.lede {{ margin: 8px 0 0; color: var(--muted); font-size: 15px; }}
.headline {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 32px; }}
.pill {{
  display: inline-flex; align-items: center; height: 28px; padding: 0 12px;
  border-radius: var(--pill); font-size: 12px; font-weight: 500;
  color: var(--accent); border: 1px solid var(--border); background: transparent;
}}
.pill.bad {{ color: var(--graphite); }}
.plot-frame {{ margin: 8px 0 40px; }}
.plot {{ width: 100%; height: auto; display: block; }}
.sheet {{ width: 100%; border-collapse: collapse; }}
.sheet th {{
  text-align: left; font-weight: 400; color: var(--muted); width: 42%;
  padding: 12px 0; border-bottom: 1px solid var(--border); font-size: 14px;
}}
.sheet td {{
  padding: 12px 0; border-bottom: 1px solid var(--border);
  font-variant-numeric: tabular-nums; font-weight: 500;
}}
.checks {{ list-style: none; padding: 8px 0 0; margin: 0; }}
.checks li {{ display: flex; gap: 10px; padding: 12px 0; color: var(--muted); border-bottom: 1px solid var(--border); }}
.checks .mark {{ color: var(--accent); font-weight: 500; min-width: 1em; }}
.checks li.bad .mark {{ color: var(--graphite); }}
.bar {{
  height: 1px; background: var(--border); margin: 24px 0 8px; overflow: hidden;
}}
.bar span {{ display: block; height: 100%; background: var(--accent); }}
.colophon {{
  display: flex; justify-content: space-between; gap: 12px;
  margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 12px;
}}
.mono {{ font-variant-numeric: tabular-nums; font-size: 12px; }}
.quiet {{ color: var(--muted); }}
.hidden {{ display: none; }}
@media (max-width: 860px) {{
  .stage {{ grid-template-columns: 1fr; gap: 32px; }}
  .app {{ padding: 32px 24px 64px; }}
  h1 {{ font-size: 28px; }}
}}
"""

def _experiment_payload(result: VeyraResult) -> dict[str, Any]:
    card = experiment_card(result)
    plot = card.get("plot") or {}
    series = plot.get("series") or []
    paths = [{"x": s.get("x", []), "y": s.get("y", [])} for s in series]
    card["svg"] = svg_trajectory(
        paths,
        plot.get("envelope") or result.details.get("envelope"),
        x_label=plot.get("x_label") or _axis_labels(result)[0],
        y_label=plot.get("y_label") or _axis_labels(result)[1],
    )
    card["metricsHtml"] = _metrics_html(card.get("metrics") or [])
    card["inputsHtml"] = _inputs_html(result.inputs)
    card["checksHtml"] = _checks_html(card.get("checks") or [])
    return card


def _empty_payload() -> dict[str, Any]:
    return {
        "title": "Veyra",
        "kind": "",
        "solver": "",
        "run_id": "",
        "ok": True,
        "integrity": 1.0,
        "integrityLabel": "PASS",
        "integrityPct": "100%",
        "inputs": {},
        "metrics": [],
        "checks": [],
        "svg": "",
    }


def _axis_labels(result: VeyraResult) -> tuple[str, str]:
    kind = result.kind.lower()
    if "pendulum" in kind:
        return "time", "angle"
    if "orbit" in kind:
        return "x", "y"
    if "trajectory" in kind or "projectile" in kind:
        return "range", "altitude"
    return "x", "y"


def svg_trajectory(
    paths: list[dict[str, Any]],
    envelope: dict[str, Any] | None = None,
    x_label: str = "range",
    y_label: str = "altitude",
) -> str:
    series = [path for path in paths if path.get("x") and path.get("y")]
    if not series and not (envelope and envelope.get("x")):
        return ""
    xs = [float(x) for path in series for x in path["x"]]
    ys = [float(y) for path in series for y in path["y"]]
    if envelope and envelope.get("x"):
        xs.extend(float(x) for x in envelope["x"])
        ys.extend(float(y) for y in envelope.get("y_lo", []))
        ys.extend(float(y) for y in envelope.get("y_hi", []))
    if not xs or not ys:
        return ""
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x == min_x:
        max_x += 1
    if max_y == min_y:
        max_y += 1
    width, height, pad_l, pad_r, pad_t, pad_b = 760, 300, 44, 20, 16, 36

    def px(x: float, y: float) -> tuple[float, float]:
        return (
            pad_l + (x - min_x) / (max_x - min_x) * (width - pad_l - pad_r),
            height - pad_b - (y - min_y) / (max_y - min_y) * (height - pad_t - pad_b),
        )

    parts = [
        f'<svg class="plot" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">',
        f'<rect width="{width}" height="{height}" fill="transparent" />',
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + frac * (height - pad_t - pad_b)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{LIGHT["border"]}" stroke-width="1" />'
        )
    if envelope and envelope.get("x"):
        hi = [_fmt_pt(*px(x, y)) for x, y in zip(envelope["x"], envelope["y_hi"])]
        lo = [_fmt_pt(*px(x, y)) for x, y in zip(reversed(envelope["x"]), reversed(envelope["y_lo"]))]
        parts.append(
            f'<path d="M {" L ".join(hi + lo)} Z" fill="{LIGHT["accent"]}" fill-opacity="0.12" />'
        )
    for i, path in enumerate(series[:8]):
        pts = " ".join(_fmt_pt(*px(float(x), float(y))) for x, y in zip(path["x"], path["y"]))
        opacity = "1" if i == 0 else "0.22"
        parts.append(
            f'<polyline fill="none" stroke="{LIGHT["accent"]}" stroke-opacity="{opacity}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="{pts}" />'
        )
    parts.append(
        f'<text x="{(pad_l + width - pad_r) / 2:.0f}" y="{height - 8}" text-anchor="middle" '
        f'fill="{LIGHT["muted"]}" font-size="11" font-family="Inter, sans-serif">{_esc(x_label)}</text>'
    )
    parts.append(
        f'<text x="14" y="{height / 2:.0f}" text-anchor="middle" transform="rotate(-90 14 {height / 2:.0f})" '
        f'fill="{LIGHT["muted"]}" font-size="11" font-family="Inter, sans-serif">{_esc(y_label)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _fmt_pt(x: float, y: float) -> str:
    return f"{x:.1f},{y:.1f}"


def _metrics_html(metrics: list[dict[str, Any]]) -> str:
    if not metrics:
        return "<tr><td class='quiet'>No scalar metrics</td></tr>"
    return "".join(
        f"<tr><th>{_esc(m['name'])}</th><td>{_esc(m.get('text') or m.get('value', ''))}</td></tr>"
        for m in metrics
    )


def _inputs_html(inputs: dict[str, Any]) -> str:
    if not inputs:
        return "<tr><td class='quiet'>No declared inputs</td></tr>"
    return "".join(
        f"<tr><th>{_esc(str(k).replace('_', ' '))}</th><td>{_esc(v)}</td></tr>" for k, v in inputs.items()
    )


def _checks_html(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "<li class='quiet'>No checks recorded</li>"
    rows = []
    for check in checks:
        cls = "ok" if check.get("passed") else "bad"
        mark = "+" if check.get("passed") else "×"
        detail = f"<span>{_esc(check.get('detail', ''))}</span>" if check.get("detail") else ""
        rows.append(
            f'<li class="{cls}"><span class="mark">{mark}</span>'
            f'<span>{_esc(check.get("name", ""))} {detail}</span></li>'
        )
    return "".join(rows)


def _esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
