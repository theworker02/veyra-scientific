import json
from pathlib import Path
from urllib.request import Request, urlopen

from veyra.server import serve_background


def test_lab_api_run_and_catalog(tmp_path: Path):
    httpd = serve_background("127.0.0.1", 0, tmp_path, None)
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        with urlopen(f"{base}/api/catalog") as response:
            catalog = json.loads(response.read())
        assert catalog["veyra"] == "4.7.0"
        assert catalog["count"] >= 27
        with urlopen(f"{base}/api/health") as response:
            health = json.loads(response.read())
        assert health["ok"]
        assert health["veyra"] == "4.7.0"
        assert health["models"] >= 27
        request = Request(
            f"{base}/api/run",
            data=json.dumps({"model": "rc", "resistance": 1000, "capacitance": 1e-6}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            card = json.loads(response.read())
        assert card["model"] == "rc"
        assert card["ok"]
        with urlopen(f"{base}/api/session") as response:
            session = json.loads(response.read())
        assert session["experiments"][0]["run_id"] == card["run_id"]
        math_req = Request(
            f"{base}/api/math",
            data=json.dumps({"expression": "x^2 - 1 = 0", "action": "solve"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(math_req) as response:
            solved = json.loads(response.read())
        assert solved["ok"]
        assert len(solved["metrics"]) >= 2
        csv_text = (Path(__file__).resolve().parents[1] / "examples" / "data" / "linear.csv").read_text(encoding="utf-8")
        measure_req = Request(
            f"{base}/api/measure",
            data=json.dumps({"csv": csv_text, "x": "x", "y": "y", "x_unit": "s", "y_unit": "m", "fit": "linear"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(measure_req) as response:
            measured = json.loads(response.read())
        assert measured["ok"]
        assert measured["model"] == "measure"
        with urlopen(f"{base}/api/methods.html?run={measured['run_id']}") as response:
            page = response.read().decode("utf-8")
        assert "Veyra Scientific" in page
        assert measured["run_id"] in page
        dest = tmp_path / "examples" / "data"
        dest.mkdir(parents=True)
        (dest / "probe.csv").write_text("x,y\n0,0\n1,2\n2,4\n3,6\n", encoding="utf-8")
        with urlopen(f"{base}/api/data-files") as response:
            listing = json.loads(response.read())
        assert any(item["name"] == "probe.csv" for item in listing["files"])
        path_req = Request(
            f"{base}/api/measure",
            data=json.dumps(
                {"path": "examples/data/probe.csv", "x": "x", "y": "y", "fit": "linear"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(path_req) as response:
            from_path = json.loads(response.read())
        assert from_path["ok"]
    finally:
        httpd.shutdown()
