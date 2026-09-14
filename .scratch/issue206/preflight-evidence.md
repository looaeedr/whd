# #206 T2 Preflight Evidence

[當前角色：T2 實作者]

Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
Branch: `test/issue206-characterization-20260914`

READ_SKILL: Python測試實務
READ_SKILL: tdd
READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / Branch-First / remote QA / issue closure
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

T2 constraints:
- tests characterize current observable behavior at the pre-approved seams;
- no production code changes are allowed in T2;
- fixtures/expected values are validation inputs only and never production authority;
- tests must not mutate config.ini, 基準檔/**, production source, or persistent runtime state;
- focused GREEN is only T2 evidence, not final modularization acceptance;
- if characterization disagrees with current behavior, reread the seam/authority before changing either expected values or production.
