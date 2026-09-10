# 2026-09-10 中文 Skill Identity / Content Audit Evidence

Task: 掃描 `.agents/skills/**` 全樹；所有中文資料夾 Skill 的 frontmatter `name` 必須等於資料夾 basename，並檢查/修復內容中的 stale identity、斷掉路由、不存在工具或背景 Subagent 假設，以及已 superseded 的 WHD authority。

User scope correction during the same task: **`修改DXF` 不是 WHD／本專案 Skill**。WHD 的 `驗證板件與DXF` 只負責驗證／驗收，不得取代或冒充外部 `修改DXF` 編輯能力。

Baseline branch/head: `chore/repair-dispatching-skill-20260910 @ ae5bf1dfd7bd1909323e411716fdb3e6ff47e21a`
Work branch: `chore/normalize-chinese-skill-names-20260910`

## Skills read / applied

- 寫技能
- tdd
- diagnosing-bugs
- phase6-release-packaging
- 掃描深模組
- 驗證板件與DXF
- monitoring-remote-qa
- verification-before-completion

## Required references read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: release_required_artifacts.json

## Audited Chinese Skill folders

Engineering:
- 執行開發任務 — baseline name `implement` → `執行開發任務`
- 寫成規格書 — baseline name `to-spec` → `寫成規格書`
- 寫技能 — baseline/current `寫技能`
- 拆解任務工單 — baseline name `to-tickets` → `拆解任務工單`
- 拷問邊建立文件 — baseline name `grill-with-docs` → `拷問邊建立文件`
- 掃描深模組 — baseline name `improve-codebase-architecture` → `掃描深模組`
- 派工 — baseline/current `派工`
- 程式碼庫設計 — baseline name `codebase-design` → `程式碼庫設計`
- 領域建模 — baseline name `domain-modeling` → `領域建模`
- 驗證板件與DXF — baseline/current `驗證板件與DXF`

Productivity:
- 深度質詢 — baseline name `grilling` → `深度質詢`

Total: **11 Chinese Skill folders; 8 identity mismatches corrected; 3 already matched.**

## Content findings and corrections

1. `拷問邊建立文件/SKILL.md` baseline 只有一句舊 Skill-tool 指令；已重寫成 capability-adaptive `深度質詢 + 領域建模` durable workflow，且完全移除舊 literal runtime 指令。
2. `深度質詢/SKILL.md` baseline 無條件要求 background sub-agent；已改成只有真正 Subagent Runtime 存在才委派，否則同一執行者 inline 查 fact，不等待不存在的回報。
3. `程式碼庫設計/DESIGN-IT-TWICE.md` baseline 無條件要求 3+ parallel sub-agents；已加入 no-Subagent sequential/inline 3+ independent designs fallback，禁止假裝平行 agent。
4. `掃描深模組/SKILL.md` 已把 canonical dependencies 改為真實中文路徑：`程式碼庫設計`、`深度質詢`、`領域建模`；舊英文名稱只作 legacy alias/history。
5. `engineering/README.md`、`productivity/README.md` 與 `ask-matt/SKILL.md` 已改用中文 canonical identity/path，不再導向不存在的 `./to-spec/`、`./implement/`、`./grilling/` 等路徑。
6. `驗證板件與DXF` 的 Receiving Divider authority 已更正為 `CROSS（十字截角）＋參數` / Certified Registry + approved reference DXF；collision/backprojection 僅 shadow verification，不得覆蓋 Registry HIT。
7. `執行開發任務` 不再把 `/tdd`、`/code-review` 當普遍存在的硬命令，改成使用實際可用 Skill/工具並保留 WHD gate。
8. `掃描深模組` 精簡內容時曾移除既有 language checker 所要求的三個精確 gate 標題；final matrix 抓到後已恢復 `語言規則（最高優先，強制）`、`啟動前語言自檢（強制）`、`輸出前語言閘門（強制）`。
9. `修改DXF` 專案邊界：Registry 本來就沒有把它列為 WHD Skill；已在 `驗證板件與DXF` 與 AI Library 明寫「不是本專案 Skill／只負責驗證驗收／不得取代」，並新增 machine guard `tests/test_dxf_skill_scope_contract.py`。
10. `release_required_artifacts.json` 已保留 `tests/test_chinese_skill_identity_contract.py` 與 `tests/test_dxf_skill_scope_contract.py`，避免 UPDATE 丟掉永久防線。

## RED evidence

### RED 1 — 中文 identity/content baseline

- run: `34495048622`
- head: `b213a493f7058ffb306f7d0889c3f921fa487616`
- Preflight: all required Skills / references GREEN
- pytest: **8 failed / 1 passed**
- Valid requirement RED: eight frontmatter identity mismatches plus content/routing assertions; no setup/import/harness failure.

### RED 2 — `修改DXF` scope correction + residual content

- run: `34497691667`
- head: `bba84ca42e53334a5b886c23c477ffb4954c21f9`
- Preflight: GREEN
- pytest: **2 failed / 9 passed**
- Failures:
  - `拷問邊建立文件` still contained the old literal runtime phrase inside a negative sentence.
  - `驗證板件與DXF` had not yet explicitly stated that `修改DXF` is external/not a WHD project Skill.
- Both were contract/content failures, not harness failures.

### Integration regression discovery

- run: `34498015811`
- head: `29f4a4be02b6458e6873183b347a0f445e84f81b`
- Preflight: GREEN
- matrix: **68 passed / 1 failed**
- Single failure: existing `掃描深模組` source-language checker required three exact language-gate headings that had been shortened during cleanup.
- Corrective action: restore the exact required headings without reverting the new Chinese identity/content improvements.

## Final GREEN evidence

- run: `34498315183`
- tested head: `469387d9aa2479df6201902d099f9175aa8466cc`
- terminal conclusion: **SUCCESS**
- Knowledge Preflight: all required Skills/references ✓
- final regression matrix: **69 passed / 0 failed** in 0.63s
- matrix included:
  - `tests/test_chinese_skill_identity_contract.py`
  - `tests/test_dxf_skill_scope_contract.py`
  - writing Skill contract + Preflight route
  - dispatching timeout contract
  - deep-scan source/report language gates
  - Phase6 Skill Preflight gate
  - release packaging policy
  - release integrity gate

## Cleanup / drift audit

One-shot workflow cleanup is required after this GREEN. Final acceptance is only valid after `.github/workflows/chinese-skill-identity-check-20260910.yml` is deleted and tested-head → cleaned-head compare confirms no Skill/test/Registry/release-policy drift; only this evidence update and workflow cleanup are allowed after the tested head.
