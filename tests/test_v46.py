import json
import subprocess
import sys
from pathlib import Path

from veyra.catalog import guess_model
from veyra.core import VERSION
from veyra.dsl import run_path
from veyra.measure import analyze_measurement
from veyra.protocol import methods_page
from veyra.stats import fit_model

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_4_6():
    assert VERSION == "4.7.0"


def test_linear_csv_fit_reports_units():
    result = analyze_measurement(
        path=ROOT / "examples" / "data" / "linear.csv",
        x="x",
        y="y",
        x_unit="s",
        y_unit="m",
        fit="linear",
    )
    assert result.all_checks_passed()
    r2 = next(float(m.value) for m in result.metrics if m.name == "R²")
    assert r2 > 0.99
    rmse = next(m for m in result.metrics if m.name == "fit RMSE")
    assert rmse.unit == "m"
    assert guess_model(result.kind) == "measure"


def test_cooling_csv_overlay_residual():
    result = analyze_measurement(
        path=ROOT / "examples" / "data" / "cooling.csv",
        x="t",
        y="T",
        x_unit="s",
        y_unit="K",
        fit="none",
        overlay="cooling",
        overlay_params={"t0": 363.15, "t_env": 293.15, "k": 0.05, "duration": 120},
    )
    assert result.all_checks_passed()
    rms = next(float(m.value) for m in result.metrics if m.name == "overlay RMSE")
    assert rms < 0.5
    unit = next(m.unit for m in result.metrics if m.name == "overlay RMSE")
    assert unit == "K"
    overlay_check = next(c for c in result.checks if c.name == "overlay evaluated at measured x")
    assert overlay_check.passed
    assert "source n=" in overlay_check.detail


def test_measured_experiments_run():
    linear = run_path(ROOT / "examples" / "measured-linear.veyra")
    cooling = run_path(ROOT / "examples" / "measured-cooling.veyra")
    assert linear[0].all_checks_passed()
    assert cooling[0].all_checks_passed()


def test_methods_page_is_an_artifact():
    fit = fit_model([0, 1, 2, 3, 4], [0.0, 2.0, 4.0, 6.0, 8.0], "linear")
    page = methods_page(fit.to_dict())
    assert "Veyra Scientific" in page
    assert fit.run_id in page
    assert "PASS" in page
    assert "<!doctype html>" in page.lower()


def test_workspace_hides_python_project_chrome():
    settings = json.loads((ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert settings["python.interpreter.infoVisibility"] == "never"
    assert settings["python.createEnvironment.trigger"] == "off"
    assert settings["files.exclude"]["**/__pycache__"] is True
    assert settings["files.exclude"]["workbench/node_modules"] is True
    assert settings["files.exclude"]["pyproject.toml"] is True


def test_plugin_is_directory_ready():
    cursor = json.loads((ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8"))
    portable = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor["name"] == "veyra-scientific"
    assert cursor["license"] == "MIT"
    assert cursor["logo"] == "assets/logo.svg"
    assert "displayName" not in cursor
    assert (ROOT / "assets" / "logo.svg").is_file()
    assert (ROOT / "LICENSE").is_file()
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert portable["$schema"].startswith("https://agent-plugins.org/")
    assert portable["license"] == "MIT"
    assert mcp["mcpServers"]["veyra"]["args"] == ["scripts/veyra-mcp.py"]
    assert "sessionStart" in hooks["hooks"]
    assert (ROOT / "hooks" / "bootstrap.py").is_file()
    assert (ROOT / "scripts" / "veyra-mcp.py").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()
    assert (ROOT / "CONTRIBUTING.md").is_file()
    assert (ROOT / "docs" / "index.html").is_file()
    assert (ROOT / "docs" / "media" / "workbench.svg").is_file()
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()
    pages = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    funding = (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
    assert "actions/upload-pages-artifact@v4" in pages
    assert "actions/deploy-pages@v4" in pages
    assert "github: theworker02" in funding
    assert "thanks_dev: u/gh/theworker02" in funding
    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_plugin.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr


def test_overlay_uses_source_series_not_plot_downsample():
    import numpy as np

    from veyra.core import VeyraResult
    from veyra.measure import _overlay_series
    from veyra.plots import PLOT_POINTS, series

    x = np.linspace(0.0, 10.0, 1000)
    y = np.exp(-0.05 * x)
    trace = series("analytic", x, y)
    assert len(trace["x"]) == PLOT_POINTS
    assert len(trace["x_src"]) == 1000
    result = VeyraResult(ok=True, kind="test", title="test", details={"plot": {"series": [trace]}})
    mx, my = _overlay_series(result)
    assert mx.size == 1000
    assert abs(float(my[0]) - 1.0) < 1e-12


def test_lab_csv_path_stays_in_workspace(tmp_path: Path):
    from veyra.measure import analyze_measurement, list_lab_csv, resolve_lab_csv

    data = tmp_path / "examples" / "data"
    data.mkdir(parents=True)
    csv_path = data / "inside.csv"
    csv_path.write_text("x,y\n0,0\n1,1\n2,2\n3,3\n", encoding="utf-8")
    files = list_lab_csv(tmp_path)
    assert any(item["name"] == "inside.csv" for item in files)
    assert resolve_lab_csv("examples/data/inside.csv", tmp_path) == csv_path.resolve()
    assert resolve_lab_csv("../outside.csv", tmp_path) is None
    loaded = analyze_measurement(
        path="examples/data/inside.csv",
        workspace=tmp_path,
        x="x",
        y="y",
        fit="linear",
    )
    assert loaded.checks[0].passed

