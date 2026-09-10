# WHD 技能建立與修改規則

> 目的：讓所有後續 AI 在建立或修改 `.agents/skills/**` 時，不再把特定模型、特定 CLI、背景 Subagent、viewer 或 TodoList 當成普遍存在的能力。

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

## WHD 標準入口

正式 Skill 撰寫/修改規則：

`.agents/skills/engineering/寫技能/SKILL.md`

機器可讀路由：

`.agents/skills/skill_registry.json`

全域踩坑庫仍為：

`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`

## 常見反模式

- 從 Claude/Cowork 範例直接複製成 WHD 必備流程。
- 說「已派 subagent，等它回來」但實際沒有 subagent runtime。
- 強制一定要 HTML viewer 才能 review，導致沒有 viewer 的環境停工。
- 為既有 Skill 隨意加 `v2`，造成舊引用與新 identity 分裂。
- 使用者明確要求改名，卻被「永遠保留原名」規則擋住。
- 只改 Skill 文字，沒有 contract test / Registry / AI Library durable writeback。
- 看到測試 expected value 就把差值回灌 production。

## 派工技能特別注意

`.agents/skills/engineering/派工/SKILL.md` 是流程型 Skill。修改時至少驗：

- frontmatter identity 與使用者指定名稱；
- PM → Implementer → QA 狀態機；
- owning Issue / AI Library / checkpoint / journal；
- process-group timeout 分類與 resume；
- remote QA monitoring；
- 不虛構背景工程師、不把聊天 runtime 當 scheduler；
- 章節順序與自我檢查不互相矛盾。
