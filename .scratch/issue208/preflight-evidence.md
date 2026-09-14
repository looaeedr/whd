# #208 T4 Preflight Evidence

[當前角色：T4 實作者]

Parent: #203
Depends on: #207 CLOSED / completed
Accepted parent head: `2c3185ca863adf0cd9861ad5e04f594185c95ced`
Branch: `refactor/issue208-layout-presentation-20260914`

READ_SKILL: UI設計與去AI味
READ_SKILL: 程式碼庫設計
READ_SKILL: Python測試實務
READ_SKILL: tdd
READ_SKILL: 驗證板件與DXF
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / Branch-First / issue closure
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md

Long-log execution constraint reread from current branch:
- running QA monitoring uses structured run/job/step state and bounded failure context rather than repeatedly injecting full raw logs;
- execution-window interruption does not mean remote-job failure; resume from run/HEAD/evidence state;
- terminal evidence is consolidated after completion, and raw log remains a durable source rather than a repeated chat payload.

T4 slice contract:
- move only `_project_toolbar_presentation` from `gui.py` to `gui_modules/layout.py`;
- preserve the function body byte-for-byte at the AST source-segment level;
- `gui.py` retains compatibility import/re-export;
- no operator-facing UI behavior, text, ordering, spacing, callbacks, state ownership, geometry, DXF, persistence, or topology changes;
- frame/selector/scrollbar/panel construction remain in place unless a later independently characterized slice proves them SAFE;
- no Mixin, Event Bus, Store, or second authoritative state;
- existing #206 characterization test is the validation contract; expected values remain validation-only and do not feed production;
- Xvfb UI regression is required before T4 acceptance.
