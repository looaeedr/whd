---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #280 T5 Permanent TEST Rename / Move — Acceptance Evidence

Date: 2026-09-16 (Asia/Taipei)

## Accepted candidate

- Branch: `test-cleanup/issue280-permanent-move-20260916`
- Exact tested HEAD: `b50d477b1473ef034cff9e4cac26d460dded262a`
- Reconciliation / manifest ancestor: `c549e631d9999aceb5f7204f9fd693fda405e90f`
- Accepted T2 ancestor: `eb967e92c951cec8fde9c76d171a9685232a3ea2`
- Accepted T3 ancestor: `e1d484c247af5b7f384a8883d31357efb7820049`
- Accepted T4 ancestor: `0eabb64a8308f74b9c8b66f982626d2907f00646`

## Final acceptance run

- Workflow: `Issue280 T5 Post-Move Acceptance`
- Run ID: `35033697856`
- Head SHA: `b50d477b1473ef034cff9e4cac26d460dded262a`
- Result: `SUCCESS`

Fresh terminal evidence from the run:

- `ANCESTRY_GATE=GREEN`
- fail-closed skill preflight: PASS
- `MOVE_CONTENT_EQUIVALENCE=GREEN`
- `COLLECTION_EQUIVALENCE=42`
- taxonomy relocation guard: `9 passed`
- focused post-move Xvfb acceptance: `42 passed, 0 failed`
- `OUTCOME_CONTROL_DRIFT=0`
- `PRODUCTION_SOURCE_DRIFT=0`
- `CONFIG_DXF_INVARIANTS=GREEN`
- `TRACKED_WORKTREE_CLEAN=GREEN`
- `ISSUE280_POST_MOVE_ACCEPTANCE=GREEN`

## Authorized permanent moves

Whole-file moves retained their contract/content:

1. `tests/test_phase6_semantic_doc_status.py` → `tests/governance/test_semantic_doc_status.py`
2. `tests/test_issue76_box_body_subtabs_2d_3d.py` → `tests/ui/test_box_body_physical_child_navigation.py`
3. `tests/test_box_body_single_source_t3.py` → `tests/architecture/test_box_body_single_source.py`
4. `tests/test_issue209_part_panel_projection.py` → `tests/projection/test_part_panel_projection.py`
5. `tests/test_gui_drawing_contract.py` → `tests/ui/test_gui_drawing_contract.py`
6. `tests/test_gui_toolbar_contract.py` → `tests/ui/test_gui_toolbar_contract.py`
7. `tests/test_issue210_project_actions_move_contract.py` → `tests/architecture/test_project_actions_ownership.py`

The semantic-doc test required exactly one relocation-only harness adaptation because the file moved one directory deeper:

- before: `ROOT = Path(__file__).resolve().parents[1]`
- after: `ROOT = Path(__file__).resolve().parents[2]`

The acceptance gate permits exactly that one line and still rejects any other content/assertion drift.

## #211 split

`tests/test_issue211_renderer_dependency_gate.py` was split by approved permanent responsibility without changing the six approved test function ASTs:

- behavior/projection → `tests/projection/test_renderer_behavior.py`
- architecture/ownership → `tests/architecture/test_renderer_ownership.py`

The acceptance gate proved the exact six approved nodes are present once each with AST equivalence and no duplicates.

## Failed-run root cause and correction

Previous run `35032965165 @ ffb020db7ffb2189bcfd9a00bf1119ca20ddde5d` failed only in the move-equivalence QA harness because strict byte identity also rejected the mandatory repo-root path-depth adaptation above. No production/test-contract regression was observed. Commit `b50d477b1473ef034cff9e4cac26d460dded262a` narrowed the QA gate to allow only that exact relocation adapter while preserving strict identity for every other whole-file move and strict AST identity for the #211 split.

## Protected boundaries

- No production/runtime source changes were accepted by this T5 move.
- No geometry authority changed.
- No DXF authority changed.
- No runtime physical-part identity authority changed.
- No new `skip` / `xfail` outcome masking was introduced.
- Protected `config.ini` and DXF hashes were unchanged through acceptance.

## Decision

`T5_ACCEPTANCE=ACCEPTED`

#280 is qualified to hand off to #281 / T6 Full Lane Validation. This record is documentation-only and does not itself replace the exact tested HEAD above.
