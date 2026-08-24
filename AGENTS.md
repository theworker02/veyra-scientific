# Veyra Scientific

This repository **is** a computational laboratory that runs inside Cursor. You are operating Veyra, not replacing it.

## Identity

- Tagline: **Don't guess the science. Run it.**
- Numeric truth comes from the Python kernel (`veyra`, MCP, or the Workbench). Never invent results.
- Kernel **v4.6.0**. The Workbench is a quiet control room at `http://127.0.0.1:8765/` after MCP `start_laboratory` or **Veyra: Open Laboratory**.
- Site: https://theworker02.github.io/veyra-scientific/
- Not affiliated with OpenAI. Visual language is Inter, hairlines, one teal accent `#10a37f`.

## How a person runs it

1. Install this plugin (Directory, Marketplace, or a local link). First MCP call or `sessionStart` runs `hooks/bootstrap.py` and installs the kernel from this checkout, then tries to install `extensions/veyra-workbench`.
2. Agent: MCP `start_laboratory` if the Workbench is needed. Human: **Veyra: Open Laboratory** (`Ctrl+Alt+V`) when the extension is present.
3. MCP tools (`lab_status`, `catalog_models`, `simulate_*`, `analyze_measurement`, `verify_model`).
4. `.veyra` files are scientific tests. `veyra test examples` is the suite. `veyra init <model>` writes a new one from the catalog.

## When editing science

Follow `.cursor/rules/scientific-verification.mdc`. Run the kernel. Report failed checks explicitly. Full FEA is out of scope.
