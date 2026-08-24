"""Install the laboratory kernel and Workbench extension from this plugin checkout.

This file must not import veyra. Directory and MCP first-run use it before the
kernel is on sys.path.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def plugin_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        marker = candidate / "pyproject.toml"
        if marker.is_file() and "veyra-scientific" in marker.read_text(encoding="utf-8"):
            return candidate
    raise RuntimeError("Veyra Scientific plugin root not found.")


def kernel_importable() -> bool:
    try:
        import veyra  # noqa: F401

        return True
    except ImportError:
        return False


def ensure_kernel(*, dev: bool = False) -> bool:
    """Install the kernel if missing. Returns True when pip ran."""
    if kernel_importable():
        return False
    root = plugin_root()
    target = f"{root}[dev]" if dev else str(root)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", target], cwd=root)
    return True


def _cursor_bins() -> list[str]:
    found: list[str] = []
    for name in ("cursor", "cursor.cmd", "code", "code.cmd"):
        path = shutil.which(name)
        if path:
            found.append(path)
    local = os.environ.get("LOCALAPPDATA") or ""
    extras = [
        Path(local) / "Programs" / "cursor" / "resources" / "app" / "bin" / "cursor.cmd",
        Path(local) / "Programs" / "cursor" / "Cursor.exe",
        Path("/usr/bin/cursor"),
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "cursor"
        / "resources"
        / "app"
        / "bin"
        / "cursor.cmd",
    ]
    for extra in extras:
        if extra.is_file():
            found.append(str(extra))
    unique: list[str] = []
    seen: set[str] = set()
    for item in found:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def install_extension() -> str:
    """Install a packaged Workbench extension into Cursor or VS Code."""
    root = plugin_root()
    ext = root / "extensions" / "veyra-workbench"
    if not (ext / "package.json").is_file():
        return "missing"
    vsix = root / "dist" / "veyra-workbench.vsix"
    if not vsix.is_file():
        package_script = root / "scripts" / "package_extension.py"
        try:
            subprocess.run(
                [sys.executable, str(package_script)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "package-failed"
    if not vsix.is_file():
        return "package-failed"
    for binary in _cursor_bins():
        try:
            result = subprocess.run(
                [binary, "--install-extension", str(vsix), "--force"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return "installed"
    return "install-failed"


def bootstrap(*, dev: bool = False, extension: bool = True) -> dict[str, str | bool]:
    pip_ran = ensure_kernel(dev=dev)
    ext = install_extension() if extension else "skipped"
    return {
        "kernel": "installed" if pip_ran else "present",
        "extension": ext,
        "root": str(plugin_root()),
        "ok": kernel_importable(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the Veyra laboratory from this plugin.")
    parser.add_argument("--dev", action="store_true", help="Include pytest/ruff extras.")
    parser.add_argument("--extension-only", action="store_true")
    parser.add_argument("--kernel-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.extension_only:
        payload = {"kernel": "skipped", "extension": install_extension(), "ok": True}
    else:
        payload = bootstrap(dev=args.dev, extension=not args.kernel_only)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"kernel     {payload['kernel']}")
        print(f"extension  {payload['extension']}")
        print("Workbench  http://127.0.0.1:8765/  (MCP start_laboratory or Veyra: Open Laboratory)")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
