"""MCP entry that installs the kernel from this plugin if python -m veyra would fail."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from bootstrap import ensure_kernel  # noqa: E402


def main() -> None:
    ensure_kernel()
    from veyra.mcp_server import run

    run()


if __name__ == "__main__":
    main()
