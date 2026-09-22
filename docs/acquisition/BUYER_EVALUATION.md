# Buyer evaluation â€” See installed models and their metadata

## Goal

In 15â€“45 minutes, verify the Product builds or runs as documented and that proprietary notices are present.

## Steps

1. Confirm root `LICENSE` is proprietary and `ACQUISITION.md` exists.
2. Skim `README.md` install/run claims.
3. Execute:

```
```text
Cursor / CLI / MCP / Workbench
             Ã¢â€â€š
             Ã¢â€“Â¼
        Veyra Python kernel
             Ã¢â€â€š
     Ã¢â€Å’Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â¼Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â
     Ã¢â€“Â¼       Ã¢â€“Â¼        Ã¢â€“Â¼
  models   solvers  verification
     Ã¢â€â€š       Ã¢â€â€š        Ã¢â€â€š
     Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â´Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Ëœ
             Ã¢â€â€š
             Ã¢â€“Â¼
     structured run evidence
```
```yaml
name: Damped oscillator baseline
model: damped_oscillator
parameters:
  mass: 1.0
  spring_constant: 12.0
  damping: 0.4
  initial_displacement: 0.1
  initial_velocity: 0.0
expect:
  - metric: final_displacement
    operator: abs_lt
    value: 0.02
```
```powershell
git clone https://github.com/theworker02/veyra-scientific.git
cd veyra-scientific
python -m pip install -e ".[dev]"
veyra doctor
```
```powershell
py -3 -m pip install -e ".[dev]"
py -3 -m veyra doctor
```
```powershell
```

4. Run tests if present (`npm test`, `pytest`, `cargo test`, `go test ./...`, etc.).
5. Record README vs observed behavior gaps in workpapers.

## Pass criteria

- [ ] Clone succeeds
- [ ] Documented happy path works **or** failure is explained
- [ ] Minimal path needs no surprise secrets
- [ ] License notices intact

*Updated: 2026-09-22*
