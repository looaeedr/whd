# T11 Reopen — Box Body GUI Stale Oracle Evidence

Task: T18 Xvfb gate found stale T11 family-preset test oracles
Owning issue: #11
Source run: 34024938119
Artifact: 9986793184

READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_REFERENCE: docs/superpowers/specs/2026-09-06-family-preset-switching.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md

RED 1:
tests/test_box_body_gui.py::test_box_body_face_editor_receives_direct_whd_reference_guide_and_baseline_status
- old sequence: edit W/H/D, then explicitly select known family Vault
- T11 contract: known-family selection reapplies target canonical preset
- observed W=400 is therefore correct; old 500 expectation belongs after the family selection, not before it

RED 2:
tests/test_box_body_gui.py::test_box_body_baseline_selection_does_not_override_stripfold_formula_parameters
- old expectation preserved manual 11/22/13/24/5 through explicit Vault selection
- T11 contract requires canonical Vault preset 15/20/15/20/2
- get_stretched_box_body_data remains forbidden as structural oracle

Boundary:
- test-only correction
- no production change
- rerun both stale tests + T11 family switching guards before reclosing #11

RESULT: DIAGNOSED / READY FOR TEST ORACLE CORRECTION
