# T14 Reopen — Side/Back Formed-Depth Oracle

Task: T18 Xvfb durable gate found stale T14 side/back UI oracle
Owning issue: #15
Source run: 34029041802
Source artifact: 9988091629
Single RED:
- tests/test_phase6_box_body_structure.py::test_real_side_back_structure_shows_readonly_formed_depth_d

READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_REFERENCE: docs/superpowers/specs/2026-09-06-box-body-child-input-sections.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md

Diagnosis:
- Pre-T14 UI showed one shared label "側板成型深度 D：...".
- T14 made each authoritative physical piece own its own child input section.
- Current side sections box_body:left_side / box_body:right_side each show "成型深度 D：... mm".
- Current box_body:back section shows "成型寬：... mm".
- The old test is checking the retired shared presentation seam, not a missing product capability.

Correction boundary:
- test-only
- no production change
- assert formed information inside authoritative child sections and stable-id ownership

RESULT: DIAGNOSED / READY FOR ORACLE CORRECTION


ORACLE CORRECTION:
- tests/test_phase6_box_body_structure.py
- production changes: 0

REMOTE QA RUN: 34029609787
REMOTE QA HEAD: 1bc83840f272f2aa37fef955d72a4b4fb42da30a
REMOTE QA: 34 PASS / 0 FAIL (25 + 9)
CONFIG SHA256 BEFORE/AFTER:
980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67

RESULT: GREEN / READY TO RECLOSE T14
