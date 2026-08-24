#!/usr/bin/env python3
"""After scientific edits, remind the agent to run Veyra instead of guessing."""

from __future__ import annotations

import json
import sys

payload = json.load(sys.stdin)
path = str(payload.get("file_path") or payload.get("path") or "")
scientific = path.endswith((".py", ".veyra", ".ipynb"))
if not scientific:
    print("{}")
    raise SystemExit(0)

message = (
    "A scientific file was edited. Invoke Veyra before reporting numeric results: "
    "`veyra verify` for source, `veyra run` / `veyra test` for experiments, "
    "and Lens/Proof MCP tools for equations. Never fabricate computed values."
)
json.dump({"additional_context": message}, sys.stdout)
