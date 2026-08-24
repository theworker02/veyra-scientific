---
name: agent-experiment
description: Run a user-requested catalog experiment through the local Veyra kernel
---

Use the Veyra Experiment Runner workflow for the user's current request.

Call `catalog_models` if the model is ambiguous. Then call
`agent_run_experiment` with the user's stated request, a supported model id,
numeric parameter overrides in catalog units, and only relevant result
assertions. Return Veyra's run id, metrics, pass/fail checks, and assumptions.

Do not run an experiment that was not requested. Do not execute shell commands
or create files as part of this command. Never invent numeric results.
