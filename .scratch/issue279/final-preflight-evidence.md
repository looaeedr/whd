# Issue #279 / T4 final post-retirement QA preflight evidence

TASK: TEST cleanup GUI characterization retirement final acceptance, pytest, remote QA, UI contract, architecture contract, issue closure preparation

READ_SKILL: Python測試實務
READ_SKILL: UI設計與去AI味
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: phase6-corner-3d-model-integrity

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

BOUNDARY:
- Exact final candidate is 84ae70954967b476227f7e11bcbcf15624e8e013.
- The migration-era tests/test_issue206_gui_modularization_characterization.py must be absent.
- Permanent replacements tests/test_gui_drawing_contract.py and tests/test_gui_toolbar_contract.py must remain GREEN together with issue210/issue211 permanent contracts.
- No production source, geometry, DXF, persistence, schema, runtime identity, or renderer ownership mutation is authorized.
- No skip/xfail masking, broad deselection, or assertion weakening is allowed.
- The corner/3D skill and relief references are guardrails only; they do not authorize geometry changes.
