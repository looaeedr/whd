---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# GUI Layout Presentation Move Implementation Plan

> **For agentic workers:** execute inline, one independently verifiable slice at a time.

**Goal:** Extract only the already-characterized pure toolbar presentation contract from `gui.py` into `gui_modules/layout.py` with zero operator-visible behavior change.

**Architecture:** `gui.py` remains the application orchestrator and compatibility surface. `gui_modules/layout.py` owns pure stateless presentation data only and must not import `gui.py`, create widgets, own callbacks, or read/write application state.

**Tech Stack:** Python 3.12, Tkinter/ttk, pytest, Xvfb, GitHub Actions.

**Spec:** #203 master / #208 T4, plus accepted #207 T3 lineage.

## Global Constraints
- strict Move-Only for `_project_toolbar_presentation`;
- exact current dict values/order/text/padding preserved;
- no operator-facing UI change;
- no geometry/state/persistence/topology/DXF authority change;
- no Event Bus, Store, Mixin split, or second state owner;
- existing characterization expected values are validation-only.

---

### Task 1: Preflight
**Files:** `.scratch/issue208/preflight-evidence.md`, `.scratch/issue208-t4-checkpoint.md`
- [ ] Run Phase6 changed-file preflight for `gui.py` and planned `gui_modules/layout.py`.
- [ ] Require UI-design + part/DXF + remote-QA evidence GREEN.

### Task 2: Exact Move-Only Extraction
**Files:**
- Create: `gui_modules/layout.py`
- Modify: `gui.py`

**Produces:** `_project_toolbar_presentation()` with the exact existing signature/body, imported into `gui.py` as compatibility surface.

- [ ] Copy the exact function body from `gui.py` into `gui_modules/layout.py`.
- [ ] Delete only the old top-level body from `gui.py`.
- [ ] Add `from gui_modules.layout import _project_toolbar_presentation` to `gui.py`.
- [ ] Do not move or modify frame/selector/scrollbar/panel construction in this slice.

### Task 3: Verification
**Tests:**
- `tests/test_issue206_gui_modularization_characterization.py`
- focused existing UI regression suite chosen by current source seam.

- [ ] AST source-contract check: moved body exactly equals accepted parent body.
- [ ] Import-direction check: importing `gui_modules.layout` must not import `gui`.
- [ ] Compatibility check: `gui._project_toolbar_presentation` remains callable.
- [ ] Run characterization and focused UI regression under Xvfb.
- [ ] Verify `config.ini` and protected baseline hashes before/after.
- [ ] Remove temporary QA workflow and audit allowed diff only.

### Task 4: Closure
- [ ] Record run_id, tested head, PASS/FAIL, invariants and cleaned head in checkpoint/issue.
- [ ] Close T4 only on terminal GREEN; otherwise classify RED before any fix.
