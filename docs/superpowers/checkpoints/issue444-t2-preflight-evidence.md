# Issue #444 T2 — Phase6 Knowledge Preflight evidence

[轉移至：實作者]
[當前角色：T2 實作者]

Task: #444 Extract BendingUI owner + symmetry/profile compatibility seam
Work-order branch: `refactor/issue444-t2-bending-ui-owner-20260920`
Authoritative parent/base: `76661e3908894d29c2e2704e646e68ea5ac638e0`
Production target is drift/integration authority only; no production merge/rebase is authorized.

READ_SKILL: 派工
READ_SKILL: 執行開發任務
READ_SKILL: monitoring-remote-qa
READ_SKILL: issue-closure-gate
READ_SKILL: executable-continuity-controller
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: 驗證板件與DXF
READ_SKILL: Python測試實務
READ_SKILL: tdd
READ_SKILL: long-log-context-safe-execution

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md

Changed-file preflight scope:
- phase6_bending_ui.py
- fold_designer_bridge.py
- the two approved stale source-test migrations from #444

Lineage recovery:
- #443 accepted HEAD is the sole #444 parent.
- `refactor/issue444-t2-bending-ui-owner-fresh-20260921` is non-canonical divergent evidence only.
- useful R2/R3 implementation must be transplanted onto this canonical branch without merging newer production.

Next: recover the useful extraction diff onto this branch, then establish/run focused R2/R3 validation.

## T2 implementation / QA acceptance evidence

[轉移至：總控審查]
[當前角色：總控審查]

- owning Issue: #444
- authoritative parent: `76661e3908894d29c2e2704e646e68ea5ac638e0` (#443 accepted HEAD)
- tested HEAD: `a992b2d637dfef58ec2a94c99e65b433aef12916`
- remote QA: RUN `35544127302`, job `106166915891`, terminal SUCCESS
- pytest terminal summary: `8 passed in 1.88s`
- cleaned HEAD after one-shot workflow removal: `d266b3b13a2d530badb789ea0d9d99fae3caf890`
- tested→cleaned drift: exactly one removed file, `.github/workflows/qa-issue444-t2-focused-20260921.yml`; production/test source drift = 0
- BENDING_UI_OWNER: `phase6_bending_ui.py`
- BENDING_UI_DEFINED_IN_BRIDGE: 0
- bridge-owned profile/symmetry implementation defs removed: 0 remaining for `_phase6_resolve_profile_key`, `_phase6_box_symmetry_allowed`, `_phase6_apply_box_symmetry_policy`
- reverse import `phase6_bending_ui -> fold_designer_bridge`: 0
- profile compatibility re-export: GREEN
- `_phase6_on_box_symmetry_changed` remains bridge transaction delegate and calls `commit_symmetry`: GREEN
- `Phase6BendingUI.__init__(parent, state, update_cb)`: unchanged 3-argument seam
- owner instance action installed before predecessor `MainApp.__init__`: GREEN
- temporary `original.BendingUI` monkey patch normal restore: GREEN
- injected-exception restore: GREEN
- stale source-test migrations: 2
- facade binding count: predecessor 69 → candidate 69; growth = 0
- invariant weakening found in reviewed #444 diff: 0
- code-review Standards axis: no blocking finding in the #444 ownership-move/test-migration diff
- code-review Spec axis: no missing #444 acceptance item in the reviewed diff

Pending closing actions:
1. final closing-head drift audit after this evidence-only commit;
2. write terminal acceptance evidence to Issue #444;
3. close validation PR #455 without merging into production;
4. close Issue #444 completed;
5. release/terminalize shared claim only after remote readback;
6. hand off the resulting accepted HEAD as the only legal #445 parent.
