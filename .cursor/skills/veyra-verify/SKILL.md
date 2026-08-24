---
name: veyra-verify
description: >-
  Run Veyra Proof after editing scientific models. Use when asked to verify a
  model, check units, conservation, numerical stability, or scientific assertions.
---

# Veyra Verify

After scientific edits:

1. Run `verify_model` on the file.
2. Run `inspect_expression` on any changed governing equation.
3. Run matching `.veyra` experiments (`python -m veyra run` or `python -m veyra test examples`).
4. Never claim "the science checks out" unless Veyra returned PASS.
5. Full FEA is out of scope; do not treat geometry helpers as structural FEA.

Treat `@veyra assert ...` comments as required constraints.
