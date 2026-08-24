# Changelog

All notable laboratory changes are recorded here. Version is the kernel version in `src/veyra/core.py`.

## 4.8.0 — Cursor agent experiment runner

### Agent execution

- Added `agent_run_experiment`, an MCP tool that lets Cursor agents execute an explicitly requested catalog model through the local Veyra kernel.
- The agent contract requires the user's stated request, validates model selection, parameter names, numeric values, and catalog bounds before execution, and records all of them with the result.
- Optional assertions are restricted to numeric metrics returned by the model; unsupported expressions and failed checks remain visible evidence rather than being silently ignored.
- Added the **Veyra Experiment Runner** agent and `/agent-experiment` command for Cursor, with instructions to ask for material missing inputs and report the run ID, assumptions, metrics, and failures.

### Distribution

- Bumped the kernel, plugin, Workbench, extension, citation metadata, and standalone-install instructions to 4.8.0.

## 4.7.0 — Scientific runtime milestone

### Reproducible execution

- Declarative YAML `.veyra` schema with strict validation and legacy brace-format compatibility.
- Interface-neutral runtime, real experiment graph, streaming lifecycle events, deterministic cache, and structured `.veyr` result artifacts.
- Shared CLI (`validate`, `graph`, `run`), MCP (`validate_experiment`, `experiment_graph`, `run_experiment`), and Workbench payload metadata.
- Projectile reference experiment and tests for schema diagnostics, dimensional rejection, graph provenance, cache reuse, and result artifacts.

### Scope boundary

- Resource budgets are recorded but v1 does not claim to enforce operating-system memory, timeout, cancellation, or worker isolation. Future execution brokers must implement and test those controls before exposing them as guarantees.

### Distribution

- Bootstrap now builds the dependency-free Workbench VSIX when it is absent before attempting installation.
- GitHub Actions validates the extension package; GitHub Pages deploys the existing static site from `docs/`.
- GitHub Sponsors and Thanks.dev funding are configured for `theworker02`.
- GitHub Release `v4.7.0` ships the Workbench VSIX plus Python wheel and source distribution assets, so the local CLI and Workbench can be used without Cursor.

### Presentation

- Reworked the README and project site into product documentation with installation, architecture, MCP, verification, and scope guidance.
- Standardized the Veyra mark across the Workbench, extension activity bar, documentation, and release media.
- Added `CITATION.cff` and a captured Workbench walkthrough GIF.

## 4.6.0

Directory-ready laboratory. Measurement instrument, methods page, Cursor plugin manifests, MIT license.

### Laboratory

- Overlay of a catalog model on measured CSV uses the **source series** (`x_src` / `y_src`), not the 220-point plot downsample. Newton cooling evaluates on a dense `t_eval` grid (801 points) against the closed form.
- Workbench Measurement can load a CSV **path** under the laboratory (`GET /api/data-files`, `POST /api/measure` with `path`). Browser file chooser and paste remain.
- Full FEA is out of scope and is labeled as such. Do not pretend mesh-based structural analysis.

### Cursor plugin

- MCP entry is `scripts/veyra-mcp.py`: installs the kernel from this checkout if `import veyra` fails, then starts stdio MCP.
- `sessionStart` hook (`hooks/ensure-lab.py`) installs the kernel and tries `cursor --install-extension extensions/veyra-workbench`.
- MCP `start_laboratory` starts `http://127.0.0.1:8765/` inside the MCP process so Directory users get the Workbench without the activity bar.
- `veyra install` and **Veyra: Doctor** install kernel and extension from this folder.
- Plugin skills/agents/commands are canonical at the repo root; `python scripts/sync_plugin.py` mirrors them into `.cursor/`.
- `.cursor-plugin/plugin.json` follows the documented Cursor schema (no `displayName`).

### Docs and CI

- CHANGELOG and CONTRIBUTING, including Directory / Marketplace / Pages steps after `main` exists on GitHub.
- Science CI: pytest and `veyra test examples`.
- Workbench figure on the README and GitHub Pages site.

## Earlier

Projectile with drag, orbits, Kepler, escape, free fall, SHM, Doppler, circular motion, pendulum, oscillator, Bernoulli, heat, RC / RL / LC, thin lens, cooling, decay, Atwood, range tables, Lens, live `.veyra` diagnostics, methods HTML.
