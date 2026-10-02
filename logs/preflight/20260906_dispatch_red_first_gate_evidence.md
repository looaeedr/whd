# Dispatch / To-Tickets RED-first Gate Evidence

- task: 修改拆解任務工單與派工 Skill，強制需求級 RED 先於任何 ticket breakdown；使用者逐條論證與核准後才能拆單，工單拆法另有第二次核准。
- backup: backup-20260906-123951
- source_head: d36068cc1fde21d3ca6350caac99148ae14e9ef7

phase6-release-packaging
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: release_required_artifacts.json

## User-approved contract
1. 先按 Requirement 寫可執行 RED，不先命名 T11/T12 或猜 ticket boundary。
2. 實際執行 RED，只有抵達正確 behavior seam 且因需求未滿足而失敗才算有效 RED。
3. 與使用者逐條論證 Requirement ↔ RED evidence；使用者核准前不得拆工單、不得建立 issue/local ticket、不得轉 Worker。
4. RED 核准後，才依根因耦合與依賴決定 ticket boundary；ticket breakdown 本身需第二次使用者核准。
5. 每張 ticket 必須綁定 Approved RED IDs。
6. RED 已是 GREEN 時，不得硬造修復工單；先重新確認 seam / existing implementation / reported path。

## RED
Command:
`python -m pytest -q tests/test_to_tickets_red_first_contract.py`

Before Skill changes:
- 6 failed / 0 passed.
- Failures were missing RED Gate, requirement evidence matrix, fail-closed wording, dispatch bypass guard, already-GREEN handling, and Approved RED IDs binding.

## GREEN
Command:
`python -m pytest -q tests/test_to_tickets_red_first_contract.py`

After minimal Skill changes:
- 6 passed / 0 failed.

Regression command:
`python -m pytest -q tests/test_to_tickets_red_first_contract.py tests/test_dispatching_skill_timeout_contract.py tests/test_phase6_skill_preflight_gate.py tests/test_phase6_release_packaging_policy.py tests/test_release_integrity_gate.py`

Result:
- 45 passed / 0 failed.

## Scope guard
- No production code changed.
- No product T11-T20 tickets were created or published.
