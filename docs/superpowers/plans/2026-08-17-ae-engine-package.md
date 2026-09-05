# AE Engine Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make `ae_engine/` the single directly replaceable manufacturing core used by both GUI AE and automatic split projects.

**Architecture:** Move/copy authoritative core implementations into a real package with relative imports and host-root resource lookup. Retain legacy module names only as aliases to `ae_engine` so old consumers share module/class identity while production callers switch to the package.

**Tech Stack:** Python 3, dataclasses, ezdxf, pytest, Tk/Xvfb.

## Global Constraints
- Finished-face Feature remains the only automatic machining coordinate contract.
- GUI behavior and current legacy-unfolded adapter behavior must not change.
- Split ownership/extraction/replacement logic must not move into `ae_engine`.
- `基準檔/開孔/自動開孔替換.csv` must never be included or overwritten by an update package.
- No manufacturing algorithm rewrite in Phase 5.

---

### Task 1: Package boundary and resource root
**Files:** create `ae_engine/*`; tests `tests/test_ae_engine_package.py`.
**Interfaces:** `import ae_engine`; host root is `Path(ae_engine.__file__).parent.parent` for default resources.
- [x] Write RED tests for package imports, relative-module identity, and host-root `config.ini`/`基準檔` lookup.
- [x] Verify RED.
- [x] Copy authoritative core files into `ae_engine/`, convert internal imports to relative imports, add `__init__.py`, and adjust default resource lookup to the package parent.
- [x] Verify GREEN.

### Task 2: AE GUI migration and compatibility aliases
**Files:** modify `gui.py`; replace root core files with aliases; tests `tests/test_ae_engine_package.py` plus existing GUI/API tests.
**Interfaces:** production GUI imports `ae_engine.*`; legacy `import ae`/`import sheetmetal_features` aliases the package module object.
- [x] Write RED source/identity tests.
- [x] Verify RED.
- [x] Switch GUI imports and install thin module aliases.
- [x] Verify GREEN and existing API/GUI regressions.

### Task 3: Split project migration
**Files:** add identical `ae_engine/`; modify automatic bridges; replace split legacy core modules with aliases; tests `tests/test_ae_engine_package_boundary.py` plus automatic regressions.
**Interfaces:** bridges consume `ae_engine.manufacturing_api` and `ae_engine.contracts`; all legacy module feature/geometry imports resolve to package identities.
- [x] Write RED boundary/identity tests.
- [x] Verify RED.
- [x] Copy exact package, switch bridge imports, install module aliases.
- [x] Verify GREEN and automatic regressions.

### Task 4: Cabinet-type registry / RO extension point
**Files:** create `ae_engine/cabinet_types/{__init__,registry,vault,ro}.py`; tests `tests/test_cabinet_type_registry.py`.
**Interfaces:** `resolve_cabinet_type(name)` returns one canonical registration; aliases `金庫型/VAULT` resolve to Vault and `RO/落地盤` resolve to the RO registration. RO is explicitly marked not yet cabinet-orchestration implemented; no geometry is invented in Phase 5.
- [x] Write RED registry/alias tests.
- [x] Verify RED.
- [x] Implement minimal registry and export it from `ae_engine`.
- [x] Copy the identical registry tree into the split `ae_engine/`.
- [x] Verify GREEN and package-tree identity.

### Task 5: Split-owned hole catalog boundary
**Files:** restore/retain split `modules/hole_catalog.py`; modify `tests/test_ae_engine_package_boundary.py`.
**Interfaces:** split automatic replacement/catalog functions remain split-owned; Feature/geometry/core modules remain exact aliases to `ae_engine`.
- [x] Write RED boundary test proving `modules.hole_catalog` is not the AE catalog alias and retains replacement APIs.
- [x] Verify RED.
- [x] Restore the Phase-4 split catalog and keep it out of the replaceable engine tree.
- [x] Verify GREEN and automatic replacement regressions.

### Task 6: Fresh overlay and real DXF verification
**Files:** docs, update ZIP, complete verification ZIP, patches.
- [x] Compile production modules.
- [x] Run AE tests in stable groups when Tk teardown requires process isolation.
- [x] Run split tests per file/process as needed for existing capture isolation.
- [x] Run real Door/EndCap/direct-indicator/indicator-box DXF readback smoke.
- [x] Overlay Phase-5 split update onto untouched Phase-4 validation package and repeat focused tests/smoke.
- [x] Verify AE and split `ae_engine/` trees are byte-identical and update package excludes live CSV/log/cache.
