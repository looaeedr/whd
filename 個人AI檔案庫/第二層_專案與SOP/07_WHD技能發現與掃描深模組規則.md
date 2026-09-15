# WHD 技能發現與「掃描深模組」規則

## 目的

避免 AI 把「檔案存在」「README 有列」「Registry 可路由」「目前 Runtime 可正式使用」混成同一件事，並確保中文 Skill identity、Skill classification 與 WHD routing authority 一致。

## CURRENT — Skill inventory 與 active classification 分離

### 1. Inventory evidence

- `.agents/skills/**/SKILL.md` 的 filesystem 掃描只回答：**這個 Skill 檔案是否存在於 repository inventory**。
- `skill_registry.json` 是 Phase6 Preflight route，不是完整 inventory，也不是 active classification authority。
- README 是 navigation / human index，不是 existence 或 active status authority；README 漏列時不能因此宣告 Skill 不存在。

### 2. Active classification authority

正式 classification 由：

`.agents/skills/skill_catalog.json`

決定。支援分類固定為：

- `canonical`：WHD active canonical；可成為 current routing / workflow owner。
- `reference`：可讀取的參考來源，但不能形成第二套 WHD governance authority。
- `upstream-beta`：上游 Beta / in-progress，存在不代表 WHD active，可改變或消失。
- `tool-specific`：特定工具／runtime helper；沒有明確 WHD override 時不是 project canonical。
- `retired`：已退役／被取代，不得再競爭 current routing。

**檔案存在不等於 active canonical。**

`tools/skill_catalog.py` 提供 repository-local machine scan：先做 inventory，再依 `skill_catalog.json` classification 判 active canonical；遇到未分類 `SKILL.md` 必須 fail closed。

### 3. Bucket hard rules

- `.agents/skills/in-progress/**` 預設 `upstream-beta`。
- `.agents/skills/deprecated/**` 預設 `retired`。
- `.agents/skills/misc/**` 預設 `tool-specific`；只有 catalog 明確 override 才能升格，例如 `git-remote-sync-fallback` 是 WHD canonical。
- `.agents/skills/engineering/**`、`.agents/skills/productivity/**` 的 stable bucket 預設可為 canonical，但個別 Skill 仍可被更高優先 catalog rule 降成 `reference` / `retired`。
- `setup-matt-pocock-skills` 只保留 `reference`，不得建立第二套 WHD governance system。

### 4. Legacy alias retirement

已由中文 canonical identity 取代的 legacy alias 不得再留 current invocation wrapper。

- `grill-me` → `深度質詢`
- 舊 `grilling` / `domain-modeling` / `codebase-design` / `improve-codebase-architecture` 只可出現在 migration/history 說明，不得作 canonical routing target。

退役 alias 的 replacement 必須記在 `skill_catalog.json -> retired_aliases`，讓歷史名稱仍可被辨識，但不能再被呼叫為 active Skill。

## 中文 canonical identity

中文資料夾 Skill 的 canonical identity = folder basename；frontmatter `name`、README/router/Registry canonical target 必須一致。使用者精確點名 Skill 時先找 exact canonical identity，不用名稱相近 Skill 代替。

## 「掃描深模組」正式位置

- Skill 名稱：`掃描深模組`
- 正式路徑：`.agents/skills/engineering/掃描深模組/SKILL.md`
- 同目錄支援：`HTML-REPORT.md`、`check_zh_tw_report.py`、`agents/openai.yaml`、`tests/test_check_zh_tw_report.py`、`tests/test_skill_sources_zh_tw.py`

Canonical supporting Skills：

- `程式碼庫設計` → `.agents/skills/engineering/程式碼庫設計/SKILL.md`
- `深度質詢` → `.agents/skills/productivity/深度質詢/SKILL.md`
- `領域建模` → `.agents/skills/engineering/領域建模/SKILL.md`

使用者輸入 `掃描深模組`、`深模組掃描`、`掃描模組`，或要求 WHD 深層架構/module boundary 掃描時，直接載入 `掃描深模組`。不得以 `setup-ts-deep-modules`、legacy `improve-codebase-architecture` 或其他名字含 deep modules 的 Skill 取代。

## 既有深掃描 baseline 回讀

每次再執行前先確認前一輪做到哪裡，不能以聊天上下文代替 project state。最低 evidence：

1. target branch / HEAD + recent deep-module commits；
2. `.scratch/dm*/checkpoint.md`、journal/state；
3. owning Issues、Combined Acceptance、integration/remote readback；
4. `CONTEXT.md`、ADR、AI Library durable contract。

DM1…DMn 已 ACCEPTED/整合時，下一輪預設從 DM(n+1) 增量探索；除非使用者明確要求重掃，不得重跑完成 DM。

## Runtime capability 與 fallback

classification 只回答「WHD 是否把它視為 active canonical」，不保證本回合 runtime 一定具有所有外部能力。Active Skill 啟動後仍必須 capability-check；缺 subagent/background/tool 時走 safe inline fallback，不能虛構能力。

只有「能力不可替代 + fallback 全失敗 + 繼續會違反可指出 invariant」三項同時成立才可 BLOCK。BLOCKED 必須列 exact missing capability、attempted fallback、violated invariant。

## Machine guards

- `tests/knowledge/test_skill_catalog_classification_contract.py`：classification / bucket / retired alias / documentation contract。
- `tests/test_chinese_skill_identity_contract.py`：中文 folder basename / frontmatter canonical identity。
- `tools/skill_catalog.py`：inventory + classification machine scan；未分類 fail closed。

## 糾偏紀錄

### 2026-09-08：把 Registry/README 當完整 inventory

曾因只讀 Registry/部分 README 而錯誤宣稱 `掃描深模組` 不存在。永久修正：filesystem tree 是 inventory evidence；README/Registry 不足以否定存在。

### 2026-09-09：supporting capability 缺失直接宣告 BLOCKED

永久修正：先建立 latest completed DM baseline，再找 project-local authority/fallback；只有不可替代 + fallback 全失敗 + invariant 才 BLOCK。

### 2026-09-10：中文資料夾與英文 frontmatter split identity

永久修正：中文 folder basename 是 canonical Skill identity；全樹 contract 自動檢查。

### 2026-09-13：把 filesystem inventory 誤當 WHD active authority

`in-progress` 本來就明示 Beta，`misc` 也含大量 tool-specific upstream helper，但舊規則仍宣稱「實體 SKILL.md tree 是完整存在性 authority」，導致 Beta / legacy wrapper / tool-specific helper 可能被誤升為 current Skill。永久修正：**filesystem = inventory；`skill_catalog.json` = classification authority；只有 `canonical` 是 active WHD canonical。**
