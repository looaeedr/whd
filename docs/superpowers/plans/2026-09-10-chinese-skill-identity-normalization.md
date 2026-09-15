# 中文技能名稱一致化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 `.agents/skills/**` 內所有中文資料夾的 Skill frontmatter `name` 統一為資料夾名稱，並修復檢查中發現的 identity、引用、能力假設與現行 authority 漂移。

**Architecture:** 以「資料夾名稱 = canonical Skill identity」作單一契約，新增全樹自動探索 contract，避免未來新增中文 Skill 又出現英文 frontmatter。內容修正限於本次逐檔檢查確認的真問題：斷掉的 README/router 路徑、不存在工具/背景 subagent 假設、跨 Skill 舊英文 identity，以及 Receiving Divider 已 superseded 的驗證 authority。

**Tech Stack:** Markdown Skill files, JSON Registry/Release policy, Python/pytest contracts, GitHub Actions one-shot QA.

**Spec:** 使用者本輪明確要求 + `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`

## Global Constraints

- 每個新修改任務先開新 work branch；本輪 branch 為 `chore/normalize-chinese-skill-names-20260910`。
- 中文 Skill 的 canonical identity = 含 `SKILL.md` 的中文資料夾 basename。
- 使用者本輪明確要求改名，因此 rename 可覆蓋「既有 Skill 預設保留名稱」。
- 不改英文資料夾 Skill 的 identity，除非為修復中文 Skill 的引用鏈所必要。
- 不假裝存在背景 Subagent、Skill tool、viewer 或其他 runtime；有能力才用，沒有就 inline fallback。
- 驗證只能判定，不得反向成為 production/domain authority。
- Receiving Divider 現行製造 authority 是 `CROSS（十字截角）＋參數`；3D collision/backprojection 僅作 shadow/penetration verification。
- Remote QA 一旦建立 run，鎖定 `run_id + head_sha` 監控至 terminal；GREEN 後刪 one-shot workflow並做 drift audit。

---

### Task 1: 建立全樹中文 Skill identity RED contract

**Files:**
- Create: `tests/test_chinese_skill_identity_contract.py`
- Create: `docs/superpowers/verification/2026-09-10-chinese-skill-identity-preflight.md`

**Interfaces:**
- Consumes: `.agents/skills/**/SKILL.md`
- Produces: 自動探索中文資料夾並檢查 `frontmatter name == folder basename` 的 repository contract。

- [ ] **Step 1: 寫 failing test**
  - 遞迴搜尋 `.agents/skills/**/SKILL.md`。
  - parent folder basename 含 CJK 字元時納入檢查。
  - 解析第一段 YAML frontmatter 的 `name:`，逐一 assert 與 basename 完全相同。
  - 同一 test 回報所有 mismatch，而不是第一個就停止。

- [ ] **Step 2: 加內容契約**
  - `拷問邊建立文件` 必須引用 canonical `深度質詢` + `領域建模`，不得只寫 `Call the Skill tool twice`。
  - `深度質詢` 必須具備沒有 Subagent 時的 inline fact-finding fallback。
  - `程式碼庫設計/DESIGN-IT-TWICE.md` 必須具備無平行 Subagent 時的 sequential/inline fallback。
  - `掃描深模組` 必須以中文 canonical Skill identity 引用 `程式碼庫設計 / 深度質詢 / 領域建模`。
  - `驗證板件與DXF` 必須鎖 Receiving Divider `CROSS＋參數` authority 與 collision shadow-only 邊界。
  - Engineering/Productivity README 與 `ask-matt` 不得指向不存在的舊英文中文-Skill 路徑。

- [ ] **Step 3: 跑 RED**
  - Remote one-shot QA 執行 `python -m pytest -q tests/test_chinese_skill_identity_contract.py`。
  - Expected: baseline 至少因 8 個 frontmatter mismatch 與內容/引用問題 RED；harness/import/preflight failure 不算 requirement RED。

### Task 2: 一致化 8 個 frontmatter identity

**Files:**
- Modify: `.agents/skills/engineering/執行開發任務/SKILL.md`
- Modify: `.agents/skills/engineering/寫成規格書/SKILL.md`
- Modify: `.agents/skills/engineering/拆解任務工單/SKILL.md`
- Modify: `.agents/skills/engineering/拷問邊建立文件/SKILL.md`
- Modify: `.agents/skills/engineering/掃描深模組/SKILL.md`
- Modify: `.agents/skills/engineering/程式碼庫設計/SKILL.md`
- Modify: `.agents/skills/engineering/領域建模/SKILL.md`
- Modify: `.agents/skills/productivity/深度質詢/SKILL.md`

**Interfaces:**
- Consumes: parent folder basename.
- Produces: exact matching frontmatter `name` and Chinese H1/description where stale English identity was the visible title.

- [ ] **Step 1:** 將 8 個 `name` 分別改成 `執行開發任務 / 寫成規格書 / 拆解任務工單 / 拷問邊建立文件 / 掃描深模組 / 程式碼庫設計 / 領域建模 / 深度質詢`。
- [ ] **Step 2:** H1/description 中若仍以舊英文 identity 當 canonical 名稱，一併改為中文；英文術語可保留作內容術語，不可再冒充 Skill identity。
- [ ] **Step 3:** `寫技能 / 派工 / 驗證板件與DXF` 已符合 identity，只做內容審查，不無故改名。

### Task 3: 修復逐檔內容問題

**Files:**
- Modify: `.agents/skills/engineering/拷問邊建立文件/SKILL.md`
- Modify: `.agents/skills/productivity/深度質詢/SKILL.md`
- Modify: `.agents/skills/engineering/程式碼庫設計/DESIGN-IT-TWICE.md`
- Modify: `.agents/skills/engineering/掃描深模組/SKILL.md`
- Modify: `.agents/skills/engineering/驗證板件與DXF/SKILL.md`
- Modify: `.agents/skills/engineering/執行開發任務/SKILL.md`

**Interfaces:**
- Consumes: current runtime capabilities + WHD authority hierarchy.
- Produces: capability-adaptive workflows and current domain authority wording.

- [ ] **Step 1:** 重寫 `拷問邊建立文件`：先執行/遵循 `深度質詢`，已確認的 domain terms 即時寫 `CONTEXT.md`，符合 ADR 三條件才寫 ADR；沒有專用 Skill loader 時直接讀 canonical SKILL.md 並 inline 執行。
- [ ] **Step 2:** 修改 `深度質詢` fact-finding：能自己查的事先用現有工具查；有真 Subagent 才可 delegate，沒有就 inline 查，不虛構背景等待。
- [ ] **Step 3:** 修改 `DESIGN-IT-TWICE.md`：有平行 Subagent 才並行；無則在同一執行者中以 3+ 個獨立 constraint sequentially 產生方案，明示不是獨立 agent sample。
- [ ] **Step 4:** `掃描深模組` 的 dependent Skill identity 改為中文 canonical 名稱，英文舊名只可標示 legacy alias。
- [ ] **Step 5:** `驗證板件與DXF` 的 Receiving Divider 段加入 `CROSS（十字截角）＋參數` / Certified Registry + reference DXF authority；collision/backprojection 僅 shadow verification，Registry HIT 不得被覆寫。
- [ ] **Step 6:** `執行開發任務` 將 `/tdd`、`/code-review` 的硬命令假設收斂為「使用對應 Skill/可用工具」；WHD 派工/QA 契約保留。

### Task 4: 修復 skill discovery / routing / durable knowledge

**Files:**
- Modify: `.agents/skills/engineering/README.md`
- Modify: `.agents/skills/productivity/README.md`
- Modify: `.agents/skills/engineering/ask-matt/SKILL.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- Modify: `release_required_artifacts.json`

**Interfaces:**
- Consumes: canonical Chinese skill names/paths.
- Produces: future Agent discoverability and package retention.

- [ ] **Step 1:** README links全部指向真實中文資料夾，不再指 `./to-spec/`, `./to-tickets/`, `./implement/`, `./domain-modeling/`, `./codebase-design/`, `./grilling/`, `./grill-with-docs/`, `./improve-codebase-architecture/`。
- [ ] **Step 2:** `ask-matt` 的主流程與 vocabulary routes 改用中文 canonical Skill names；英文 slash 名只在確有現存英文資料夾 Skill 時保留。
- [ ] **Step 3:** AI 規則新增永久 invariant：「任何中文 Skill 資料夾，frontmatter name 必須等於資料夾 basename；rename 同步 README/router/registry/tests。」
- [ ] **Step 4:** release manifest 納入新的全樹 identity contract 與 durable AI rule。

### Task 5: GREEN / Preflight / Remote QA / Cleanup

**Files:**
- Temporary: `.github/workflows/chinese-skill-identity-check-20260910.yml`
- Update: `docs/superpowers/verification/2026-09-10-chinese-skill-identity-preflight.md`

**Interfaces:**
- Consumes: modified skills + routing/docs/contracts.
- Produces: terminal remote evidence and clean closing head.

- [ ] **Step 1:** 帶完整 changed-file 清單跑 `phase6_skill_preflight.py`，確認 required Skills / references 全 ✓。
- [ ] **Step 2:** 跑 `tests/test_chinese_skill_identity_contract.py` + writing/dispatch/preflight regression + `掃描深模組` 自帶來源測試。
- [ ] **Step 3:** 鎖 run_id + head_sha 監控到 terminal；failure 先讀 log 分類，不直接重跑全套。
- [ ] **Step 4:** GREEN 後刪 one-shot workflow並反讀 404/Not Found。
- [ ] **Step 5:** tested-head → cleaned-head compare；只准 workflow cleanup + verification evidence drift，任何 Skill/test/router/AI-rule 漂移都要重跑。
