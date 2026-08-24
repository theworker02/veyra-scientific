---
name: veyra-lab
description: >-
  Use Veyra Scientific to compute mathematics, physics, geometry, statistics,
  and verification instead of estimating. Apply whenever the user asks to
  simulate, solve, verify, integrate, sweep, or test a scientific model, or to
  open the laboratory.
---

# Veyra Lab

Veyra is a local computational laboratory that runs **inside Cursor**. It is not a chat model. Do not invent numeric scientific results.

Directory install of this plugin ships skills, MCP, rules, commands, and hooks. The first MCP call or `sessionStart` hook runs `hooks/bootstrap.py`, which installs the kernel from this checkout and tries to install `extensions/veyra-workbench` (activity bar). The Agent can still open the Workbench with MCP `start_laboratory` if the extension is not present.

## Surfaces

| Surface | When to use it |
|---|---|
| MCP tools | Agent computation. Prefer these over guessing. |
| `start_laboratory` | Start http://127.0.0.1:8765/ without the activity-bar extension. |
| `python -m veyra …` | Terminal. Same kernel as MCP. |
| Workbench | Human UI at `http://127.0.0.1:8765/` after `start_laboratory` or **Veyra: Open Laboratory**. |
| Command Palette | **Veyra: Open Laboratory** when the Workbench extension is installed. |

## Workflow

1. If the user wants the UI, check `lab_status`. If the server is down, call `start_laboratory`.
2. Identify the domain: math, physics, geometry, statistics, or verification.
3. Call the matching MCP tool, or run `veyra` in the terminal.
4. Reason only over the structured result Veyra returned.
5. If a `.veyra` file exists, `run_experiment_file` or `veyra run <file>`.
6. Quote checks, metrics, and the run id. If a check failed, stop and explain the failed assumption.

## Preferred tools

- Status: `lab_status`, `start_laboratory`
- Equations: `solve_equation`, `simplify_expression`, `differentiate`, `integrate`, `math_console`
- Dynamics: `simulate_motion`, `simulate_orbit`, `simulate_collision`, `simulate_heat`, `simulate_rc`, `simulate_rl`, `simulate_lc`, `simulate_oscillator`, `simulate_shm`, `simulate_cooling`, `simulate_decay`, `simulate_atwood`, `simulate_freefall`, `simulate_kepler`, `simulate_lens`, `simulate_escape`, `simulate_doppler`, `simulate_circular`, `simulate_range_table`, `sweep_model`
- Catalog: `catalog_models`, `init_experiment`, then `veyra physics <id> --params '{...}'`
- Measurement: `analyze_measurement` (CSV path or text, fit, catalog overlay on the source series, residual, units)
- Integrity: `validate_units`, `verify_model`, `inspect_expression`, `inspect_file`, `convert_quantity`
- Geometry: `geometry_measure`, `geometry_intersect`

Never claim the science checks out unless Veyra returned PASS. Full FEA is out of scope.
