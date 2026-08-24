# Veyra Instrument

Veyra’s visual language is original. It is calibrated to the same discipline OpenAI uses in public product: quiet technology, editorial type, a single accent, and almost no chrome.

It is **not** affiliated with OpenAI. OpenAI Sans and Signifier are not loaded. Inter is the public analogue so the laboratory can ship.

## Type

| Role | Face | Why |
|---|---|---|
| UI / body / display | **Inter** 400 / 500 / 600 | Public analogue of OpenAI Sans: humanist grotesque, tabular figures, tight display tracking |
| Machine truth | Tabular Inter / system mono | Run IDs, fingerprints, solvers |

Display tracking −0.02em. Body leading 1.6. Labels 12px / 500 / 0.08em uppercase. Data uses `tabular-nums`.

## Color

Light: canvas `#ffffff`, ink `#0d0d0d`, graphite `#3c3c3c`, slate `#6e6e6e`, hairline `#e5e5e5`, placeholder `#9b9b9b`.

Dark: canvas `#0d0d0d`, ink inverted to `#ffffff`, hairline `#262626`.

The only saturated hue is **teal `#10a37f`** — primary Run, active tab, ready state, pass. Focus ring `0 0 0 3px rgba(16,163,127,0.12)`. Nothing else is colored.

## Geometry & motion

- Full-width sections, hairline rules, whitespace as divider
- No card stacks, nested cards, gradients, orbs, or drop shadows
- Buttons 12px radius (or pill for catalog actions); Run is teal, secondary is ink
- Skeletons, not spinners
- 180ms `cubic-bezier(0.25, 0.1, 0.25, 1)`

## Frontend

The Workbench is React 18 + TypeScript + Tailwind CSS 4 + lucide-react, built to `workbench/dist` and served by `veyra serve`. The Python kernel remains the source of numeric truth.

The chrome is a ChatGPT-quiet laboratory control room, not a chat box. `#f9f9f9` / `#171717` rail, New run, a search palette, a header model picker, time-grouped runs, and a workspace row. The Dashboard greets, offers model chips, sets conditions, Plays or Sweeps the kernel, and shows methods on the output. Catalog, Instruments, Compare, and Notebook stay full-width sections. Instrument results join the notebook. Runs can be pinned, forked, reproduced, renamed, or deleted. No agent prompt. Teal is Play, pass, and the selected model. The circular header Play is the send-button analogue.

## Mark

The Veyra mark is an ink V, a teal reading at the apex, and a short baseline. No enclosing tile in product chrome. The favicon is the same V on an ink rounded square so it holds at 16px. Canonical SVG: `assets/logo.svg`. Distribute with `python scripts/render_brand.py`. Do not add gradients, shadows, or extra hues.
