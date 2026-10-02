---
whd_doc_role: REFERENCE
whd_contract: issue527-b2-workspace-shell-decision
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #527 / B2 — Workspace Shell Deletion-Test

- Prior decision: `NO_EXTRACTION` (#447)
- Final decision: **`B2_EXTRACT_DEEP_SHELL_OWNER`**
- Supersedes: **#447 location/NO_EXTRACTION decision only**
- Deep owner: `phase6_workspace_shell.py::WorkspaceShellOwner`
- Tested GREEN head: `d370d5d155feff0ee06af7402d774a8b5b36faa2`

## Evidence

- DT characterization RUN `35782285637 @ abf990193d7e5edb8a82dbb2f09bbdbf129f5ab8` — SUCCESS.
- Variant K expanded shell responsibility: **391 LOC** returned to caller.
- Variant E: forbidden imports **0**, full-app dependency **false**, Xvfb single-slot **GREEN**.
- Replacement RED RUN `35782822918 @ 864b67455365e6c489563a66e1a9e31fd8b5e675` — expected RED confirmed (**4 failed / 1 skipped**).
- GREEN RUN `35783183790 @ d370d5d155feff0ee06af7402d774a8b5b36faa2` — **34 passed / 4 skipped headless; 6 passed Xvfb**.
- Bridge LOC: **7796 → 7539** (**-257** from Stage A).
- Max retained shell compatibility wrapper: **10 LOC**.
- `REVERSE_IMPORT_BRIDGE=0`.

## Preserved invariants

- `ACTIVE_MODE_SURFACE_COUNT=1`.
- No second Assembly region.
- No second Corner Data region.
- Shared content surfaces remain direct siblings.
- No duplicate keyboard binding loop.
- No full-app dependency in the shell owner.
- No manufacturing/geometry ownership moved into shell.

## Supersession rule

`docs/superpowers/checkpoints/issue447-t5-workspace-shell-census.md` remains historical provenance. Its `DECISION=NO_EXTRACTION` is no longer CURRENT after user-approved Phase 6 v1.4 + this formal Deletion-Test. The replacement machine guard is `tests/test_issue447_workspace_shell_owner.py`.

