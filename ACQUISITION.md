# Acquisition Brief â€” See installed models and their metadata

**Date:** 2026-09-22  
**Repository:** https://github.com/theworker02/veyra-scientific  
**Default branch:** `main`  
**Primary language:** Python  
**Status:** Diligence briefing only. **No acquisition has occurred** by virtue of this file.  
**License:** Proprietary â€” sale, written commercial license, or completed asset transfer required (see root `LICENSE`).  
**Valuation:** Not stated.  
**Contact:** GitHub [@theworker02](https://github.com/theworker02) Â· [thanks.dev/u/gh/theworker02](https://thanks.dev/u/gh/theworker02)

> Cloning or forking this repository does **not** grant production, redistribution, SaaS, OEM, or commercial rights.

---

## 1. Executive thesis

<img src="assets/logo.svg" width="88" alt="Veyra logo" /> <p align="center"><strong>Don't guess the science. Run it.</strong></p> <a href="https://github.com/theworker02/veyra-scientific/actions/workflows/ci.yml"><img src="https://github.com/theworker02/veyra-scientific/actions/workflows/ci.yml/badge.svg" alt="Science CI" /></a>

**Why a buyer cares:** See installed models and their metadata packages transferable product IP â€” source, docs, in-repo brand assets, and a diligence room under `docs/acquisition/` â€” under a clear proprietary posture so diligence can proceed without mistaking the repo for open source.

---

## 2. Product snapshot

| Item | Detail |
|------|--------|
| Product | See installed models and their metadata |
| Repo | `theworker02/veyra-scientific` |
| Language | Python |
| Open source? | **No** â€” proprietary |
| Rightsholder | theworker02 |
| Diligence pack | `docs/acquisition/` |

### Capability highlights (from current materials)

- **Dashboard** Ã¢â‚¬â€ recent runs, kernel status, model health, and verification activity.
- **Catalog** Ã¢â‚¬â€ available computational models and their supported parameters.
- **Instruments** Ã¢â‚¬â€ focused controls for configuring and running experiments.
- **Compare** Ã¢â‚¬â€ side-by-side result inspection and run-to-run deltas.
- **Notebook** Ã¢â‚¬â€ a traceable record of runs, notes, and exported evidence.
- classical mechanics and orbital dynamics;
- oscillators, wave motion, and signal analysis;
- heat transfer and diffusion;
- fluid and transport approximations;
- electricity, circuits, and electromagnetism;
- optics and spectral calculations;
- probability, statistics, regression, and uncertainty analysis;

---

## 3. Problem / opportunity

Teams evaluating See installed models and their metadata typically need either (a) a commercial right to run or embed it, or (b) outright ownership of the Product IP for strategic build-out. Public GitHub visibility without a proprietary license creates false assumptions about free production use. This brief and the linked data room make the commercial path explicit.

---

## 4. What ships today

Honest maturity: treat repository contents, README claims, tests, and release tags as the source of truth. Do not assume production customers, ARR, filed patents, or SLAs unless separately evidenced in diligence.

Typical transferable surfaces:

- Source tree and build/test scripts present in-repo
- Documentation and design notes
- Acquisition / diligence markdown under `docs/acquisition/`
- Branding assets committed to the repository (if any)

---

## 5. Demo / evaluation path (buyer)

Minimal path (no secrets required unless README says otherwise):

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

Extended evaluation: `docs/acquisition/BUYER_EVALUATION.md`. Written NDA / evaluation grants may be required for private materials.

---

## 6. What a transaction typically includes

Subject to definitive schedules:

| Included (typical) | Excluded (typical) |
|--------------------|--------------------|
| Repo materials + asserted original IP | Seller personal accounts / unrelated repos |
| Docs + diligence room at closing | Third-party dependency source under separate licenses |
| In-repo brand marks as assigned | Secrets without rotation plan |
| Know-how captured in docs | Fabricated revenue, user, or adoption metrics |

---

## 7. Suggested deal structures

| Structure | When it fits |
|-----------|--------------|
| Non-exclusive commercial license | Deploy/run under seat or environment terms |
| Exclusive field-of-use license | Buyer wants exclusivity; seller may retain entity |
| Asset / IP assignment | Buyer wants ownership of Materials outright |
| OEM / redistribution | Separate agreement â€” not implied here |

Commercial terms (price, earnouts, escrow) are negotiated under NDA with counsel.

---

## 8. Buyer diligence checklist

- [ ] Confirm Rightsholder identity and authority to sell/license
- [ ] Inventory Materials (`docs/acquisition/ASSET_INVENTORY.md`)
- [ ] Review IP posture (`IP_PROVENANCE.md`) and dependencies (`DEPENDENCY_INVENTORY.md`)
- [ ] Run evaluation script (`BUYER_EVALUATION.md`)
- [ ] Review risks (`RISK_REGISTER.md`)
- [ ] Agree transfer scope (`TRANSFER_MANIFEST.md`) and handoff (`HANDOFF_CHECKLIST.md`)
- [ ] Supersede root `LICENSE` at closing via definitive agreement

---

## 9. Related documents

| Document | Purpose |
|----------|---------|
| `LICENSE` | Proprietary â€” no default grant |
| `docs/acquisition/README.md` | Data-room index |
| `docs/acquisition/EXECUTIVE_SUMMARY.md` | One-page thesis |
| `README.md` | Product overview |
| `SECURITY.md` | Vulnerability reporting |
| `COMMERCIAL.md` | Licensing contact path |
| `.github/FUNDING.yml` | Sponsors / thanks.dev |

---

## 10. Disclaimer

This package is informational and **does not** create a binding offer, grant of rights, or investment advice. Engage counsel for any transaction.

---

*Document version: 2.0.0 / 2026-09-22 Â· Classification: acquisition briefing*
