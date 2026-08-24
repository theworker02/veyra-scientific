# Contributing to Veyra Scientific

This repository is a computational laboratory. Numeric results come from the kernel. Do not invent them in a pull request description.

Default branch is `main`.

## Local laboratory

1. Open this folder in Cursor.
2. `python hooks/bootstrap.py --dev` (kernel + Workbench extension).
3. MCP `start_laboratory` or Command Palette → **Veyra: Open Laboratory**.
4. `python -m pytest` and `python -m veyra test examples`.

After editing `skills/`, `agents/`, `commands/`, or `rules/`, run:

```text
python scripts/sync_plugin.py
```

CI runs that script with `--check`. Do not edit only the `.cursor/` copies.

Scientific model edits must run the kernel (`veyra test`, `veyra verify`, or the matching MCP tool) and report failed checks.

## Publishing

The owner publishes `theworker02/veyra-scientific` on `main`. Before submitting to a directory:

1. Run `python scripts/package_extension.py`, `python -m pytest`, and `python -m veyra test examples`.
2. Commit and push `main` to GitHub.
3. GitHub → Settings → Pages → select **GitHub Actions**. The included `.github/workflows/pages.yml` deploys `docs/`.
4. Confirm the Actions workflow published `https://theworker02.github.io/veyra-scientific/`.
5. Submit the GitHub URL at [Cursor Directory](https://cursor.directory/plugins/new).
6. Submit the same URL at [Cursor Marketplace](https://cursor.com/marketplace/publish).

`hooks/bootstrap.py` generates the small, dependency-free Workbench VSIX if it is absent, then installs it when Cursor or VS Code is available. The generated `dist/` artifact remains untracked; it does not need to be committed for local plugin installation.

Repository funding is configured in `.github/FUNDING.yml` for GitHub Sponsors (`theworker02`) and Thanks.dev (`u/gh/theworker02`).

Listing copy: *A computational laboratory inside Cursor. Don't guess the science. Run it.* License MIT. Logo `assets/logo.svg`.

## Design

See [DESIGN.md](DESIGN.md). Inter, hairlines, teal `#10a37f` only. No chat composer. Full FEA is out of scope.
