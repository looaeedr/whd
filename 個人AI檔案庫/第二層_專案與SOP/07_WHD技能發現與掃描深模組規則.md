# WHD 技能發現與「掃描深模組」規則

## 目的

避免 AI 因只讀 `skill_registry.json`、README 或少量目錄，就錯誤宣稱某個 WHD Skill 不存在；並確保中文 Skill 的資料夾、frontmatter、router 使用同一 canonical identity。

## 強制技能發現規則

1. WHD 專案技能的完整存在性判定，以實際掃描 `.agents/skills/**/SKILL.md` 為準。
2. `skill_registry.json` 是 Preflight 路由表，不是完整 Skill 清單。
3. 各分類 README 是導覽入口，不是完整存在性證據；README 漏列時仍掃實際 `SKILL.md`。
4. 使用者明確指定 Skill 名稱時，優先精確名稱，禁止以名稱相近/語意相似 Skill 代替。
5. 使用者說「一定有」或糾正 Skill 判斷時，改用完整 tree 驗證，不能重複同一 registry/code-search 結論。
6. 中文資料夾 Skill 的 canonical identity = folder basename；frontmatter `name`、README/router/Registry canonical target 必須一致。

## 「掃描深模組」正式位置

- Skill 名稱：`掃描深模組`
- 正式路徑：`.agents/skills/engineering/掃描深模組/SKILL.md`
- 同目錄支援：`HTML-REPORT.md`、`check_zh_tw_report.py`、`agents/openai.yaml`、`tests/test_check_zh_tw_report.py`、`tests/test_skill_sources_zh_tw.py`

## Canonical supporting Skills

`掃描深模組` 的輔助能力正式 identity / path：

- `程式碼庫設計` → `.agents/skills/engineering/程式碼庫設計/SKILL.md`
- `深度質詢` → `.agents/skills/productivity/深度質詢/SKILL.md`
- `領域建模` → `.agents/skills/engineering/領域建模/SKILL.md`

舊英文 `codebase-design / grilling / domain-modeling / improve-codebase-architecture` 只作 legacy alias/history，不得取代上述 canonical Skill。

## 觸發規則

使用者輸入/要求 `掃描深模組`、`深模組掃描`、`掃描模組`，或要求 WHD 深層架構/耦合/module boundary 掃描時，直接載入 `掃描深模組`。

不得以 `setup-ts-deep-modules`、legacy `improve-codebase-architecture`、legacy `codebase-design` 或其他名稱含 deep modules 的 Skill 取代使用者點名的主 Skill。輔助能力只能依主 Skill 要求被讀取。

## 既有深掃描 baseline 回讀

每次再執行前先確認前一輪做到哪裡，不能以聊天上下文代替 project state。

最低 evidence：

1. target branch / HEAD + recent deep-module commits；
2. `.scratch/dm*/checkpoint.md`、journal/state；
3. owning Issues、Combined Acceptance、integration/remote readback；
4. `CONTEXT.md`、ADR、AI Library durable contract。

DM1…DMn 已 ACCEPTED/整合時，下一輪預設從 DM(n+1) 增量探索；除非使用者明確要求重掃，不得重跑完成 DM 或把 closed candidate 當新候選。

## 輔助能力缺失不得自動 BLOCKED

找不到專用 Skill loader 時：

1. 先查實體 `.agents/skills/**/SKILL.md`，避免 catalog/registry 漏列。
2. 再查 project-local Skill rules、AI Library、`CONTEXT.md`、ADR、existing DM evidence。
3. 有 safe fallback 就 inline 執行並記 execution-environment difference。
4. 只有不可替代 + fallback 全失敗 + 可指出 invariant 三條同時成立才可 BLOCK。
5. BLOCKED 必須列 exact missing capability、attempted fallback、violated invariant。

沒有真正 Subagent Runtime 時，`深度質詢` / `程式碼庫設計` 的 fact-finding/design alternatives 必須使用其 inline fallback；不得虛構背景 agent。

## 糾偏紀錄

### 2026-09-08：把路由表當完整技能目錄

曾因只讀 Registry/部分 README 而錯誤宣稱 `掃描深模組` 不存在，甚至用相似 Skill 代替。永久修正：Skill existence 以實體 `SKILL.md` tree 為最終 evidence；使用者精確點名時禁止相似 Skill 代答。

### 2026-09-09：把 supporting Skill loader 缺失當硬阻塞

曾看到 supporting architecture Skill 無法直接載入就宣告整個深掃描 BLOCKED，且漏讀既有 DM completion chain。永久修正：先建立 latest completed DM baseline，再找 project-local authority/fallback；只有「不可替代 + fallback 全失敗 + invariant」才可 BLOCK。

### 2026-09-10：中文資料夾與英文 frontmatter split identity

盤點發現多個中文 Skill folder 仍使用英文 `name`，README/router 也指向不存在的英文路徑。永久修正：中文 folder basename 是 canonical Skill identity；`tests/test_chinese_skill_identity_contract.py` 全樹自動檢查，不再靠人工名稱清單。
