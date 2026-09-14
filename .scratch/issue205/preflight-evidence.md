# #205 T1 Preflight Evidence

[當前角色：T1 實作者]

Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
Branch: `refactor/issue205-state-ownership-20260914`

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md

READ_SKILL: UI設計與去AI味
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / Branch-First / dispatch / closure gates

T1-specific constraints carried forward:
- static/AST evidence alone cannot declare SAFE;
- line-count reduction is not an architecture acceptance criterion;
- module seams must preserve engineering semantic identity and authoritative ownership;
- no second authoritative state store, geometry source, 2D state, 3D state, or event bus is introduced in T1;
- validation/test/screenshot/golden data only judge correctness and cannot become production calculation authority;
- T1 is analysis-only and cannot move production symbols.
