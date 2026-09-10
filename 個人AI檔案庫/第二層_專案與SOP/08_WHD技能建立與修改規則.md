# WHD 技能建立與修改規則

> 目的：讓所有後續 AI 在建立或修改 `.agents/skills/**` 時，不再把特定模型、特定 CLI、背景 Subagent、viewer 或 TodoList 當成普遍存在的能力，並維持 Skill 資料夾、frontmatter、路由與引用的一致 identity。

## Authority

1. 使用者本輪明確核准規格最高。
2. `AGENTS.md`、Phase6 Knowledge Preflight、WHD 專案 Skill/Registry/AI Library/Source of Truth 次之。
3. 通用 skill-writing 慣例只能補充，不能繞過 WHD gate。

## 必守規則

- 修改 Skill 前先反讀 target HEAD，依 WHD `branch-first` 建新 branch；不得直接改 `cleanup/2d-3d-sync` / `main`。
- 依 `AGENTS.md` 跑 Preflight；changed files 已知後重新帶 `--changed-file` 驗一次。
- 既有 Skill 修改先保留可追溯 baseline snapshot（原始 SHA/commit/ref/內容）。
- 客觀流程型 Skill 要有 RED-capable contract，再最小修改到 GREEN。
- **驗證只能判定對不對，不能反過來成為 production / domain 規則的計算來源。**
- Skill 只能要求目前環境真的具備的能力；沒有背景 Subagent / viewer / package / CI 時要退化成可執行替代方案，**不得假裝工具存在，也不得等待不存在的第三方回報**。
- reviewer/viewer 是可選 review surface，不是完成 Skill 的唯一途徑。
- 若使用者明確要求改 Skill 名稱，使用者指示優先；要同步 frontmatter、目錄/路徑（如需要）、Registry、tests、docs 與其他引用。沒有明確要求則預設保留原名。
- 使用者指出可重複錯誤後，主動同步直接相關 Skill、AI Library/踩坑規則與 Registry，不再等使用者逐次提醒。
- 修改完成後一定遠端 re-read，不能只相信 write API 回傳。

## 中文 Skill identity 永久 invariant

對 `.agents/skills/**` 下**資料夾 basename 含中文，且該資料夾包含 `SKILL.md`** 的 Skill：

1. frontmatter `name` **必須與 parent folder basename 完全相同**。
2. H1/title 與使用者可見 canonical 名稱也應使用該中文名稱；英文技術術語可留在 body，但不能繼續冒充 Skill identity。
3. README/router/Registry/其他 Skill 若指向該 Skill，canonical target 必須使用真實中文 path/name。
4. 舊英文 identity 只可留在 migration/history/legacy alias 說明，不可作新的 canonical routing target。
5. rename 時同步 frontmatter、README/router、Registry（若有 route）、tests、docs/AI Library、release policy（若需要）。
6. machine guard 固定使用 `tests/test_chinese_skill_identity_contract.py` 自動遞迴掃描；未來新增中文 Skill 也會自動納入，不靠人工清單才發現 mismatch。

此 invariant 是對「既有 Skill 預設保留名稱」的專案級特例：**中文資料夾已是使用者指定的 canonical identity 時，`name` 要跟資料夾走。**

## WHD 標準入口

正式 Skill 撰寫/修改規則：

`.agents/skills/engineering/寫技能/SKILL.md`

機器可讀路由：

`.agents/skills/skill_registry.json`

中文 identity contract：

`tests/test_chinese_skill_identity_contract.py`

全域踩坑庫：

`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`

## 常見反模式

- 從 Claude/Cowork 範例直接複製成 WHD 必備流程。
- 說「已派 subagent，等它回來」但實際沒有 subagent runtime。
- 強制一定要 HTML viewer 才能 review，導致沒有 viewer 的環境停工。
- 為既有 Skill 隨意加 `v2`，造成舊引用與新 identity 分裂。
- 中文資料夾叫 `寫成規格書`，frontmatter 卻仍叫 `to-spec`；資料夾與 `name` split identity。
- README/router 還連 `./to-spec/`、`./grilling/` 之類不存在路徑，即使 SKILL.md 本身已改名仍造成 discovery 斷鏈。
- 使用者明確要求改名，卻被「永遠保留原名」規則擋住。
- 只改 Skill 文字，沒有 contract test / Registry / AI Library durable writeback。
- 看到測試 expected value 就把差值回灌 production。

## 派工技能特別注意

`.agents/skills/engineering/派工/SKILL.md` 是流程型 Skill，**canonical frontmatter identity 固定為 `name: 派工`**；舊 `name: dispatching` 已 superseded，不得再恢復。

修改時至少驗：

- frontmatter `name: 派工` 與目錄 `派工/` 一致；
- PM → Implementer → QA 狀態機；
- owning Issue / AI Library / checkpoint / journal；
- process-group timeout 分類與 resume；
- remote QA monitoring；
- 不虛構背景工程師、不把聊天 runtime 當 scheduler；
- 章節順序與自我檢查不互相矛盾。

## 2026-09-10 中文 Skill 全樹清理

本次以 `.agents/skills/**/SKILL.md` 實體 tree 盤點到 11 個中文 Skill 資料夾；其中 8 個仍保留英文 frontmatter identity。永久修正不是「把那 8 個名字寫死」，而是把上述 basename invariant + 全樹 contract 納入專案，避免未來同類 drift 再發生。
