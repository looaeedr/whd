# T9 Final QA Evidence

phase6-corner-3d-model-integrity
phase6-release-packaging
diagnosing-bugs
tdd
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: release_required_artifacts.json

- Issue: #9 TOP/BOTTOM/LEFT/RIGHT Selector 窄化
- Source HEAD: 920521bfe35f5981ca55df0f6e9d76706a649b57
- Fresh Xvfb targeted: 3 passed, 0 failed.
- Direct relevant assertion: test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics PASS.
- Selector width contract: width=7; all four directions remain selectable; selection does not alter geometry semantics.
- Correction: prior T9 release-regression checkpoint mapping was wrong and is superseded by corrected T9 state.
- Production changes in finalization: none.
