---
name: ask-matt
description: Ask which skill or flow fits the current situation. Routes to the real filesystem skills in this repo and uses Chinese canonical identities for Chinese-named skill folders.
disable-model-invocation: true
---

# Ask Matt

這是 repo Skill router。Filesystem `.agents/skills/**/SKILL.md` 只提供 **inventory evidence**；`.agents/skills/skill_catalog.json` 是 active **classification** authority，只有 `canonical` 預設是 WHD active Skill。README 只是導覽，Registry 是 Preflight route；`reference/upstream-beta/tool-specific/retired` 不得因檔案存在就自動成為 current routing owner。

## Main flow：idea → ship

1. **拷問邊建立文件** — 有 repository/workspace 時先用深度質詢把 design tree 問清楚，並同步 `CONTEXT.md` / ADR。
   - canonical path：`.agents/skills/engineering/拷問邊建立文件/SKILL.md`
   - 若沒有 working directory、只想純訪談，可直接用 **深度質詢**。
2. **需要 runnable answer 的 design question** — 可用 `prototype` 做 throwaway experiment；跨 session/harness 時可配 `handoff`。
3. **多 session build**：
   - **寫成規格書** → 將 grounded conversation/code/AI Library 收成 spec。
   - **拆解任務工單** → Requirement RED-first + 使用者核准後拆 tickets。
   - **執行開發任務** → 每票依 TDD/派工/QA gate 施工。
4. **小而已明確的 build**：可直接進 **執行開發任務**，但仍服從專案 Preflight/branch/QA 規則。

WHD ticketed work 的 PM → Implementer → QA 狀態機由 **派工** 擁有；不能因 router 判定「下一步是實作」就繞過 owning Issue、checkpoint、remote QA。

## On-ramps

### Incoming bugs / failures

先用 `diagnosing-bugs` 建 tight RED loop；修正用 `tdd`。若根因是缺乏穩定 seam，再交給 **掃描深模組** / **程式碼庫設計**。

### Architecture health

- **掃描深模組**：找 shallow-module/deepening candidates，先回讀既有 DM baseline。
  - `.agents/skills/engineering/掃描深模組/SKILL.md`
- **程式碼庫設計**：真正設計 module/interface/seam 的 vocabulary layer。
  - `.agents/skills/engineering/程式碼庫設計/SKILL.md`
- 深入 candidate 時用 **深度質詢**；domain term settle 時用 **領域建模**。

### Domain language

- **領域建模**：修改 `CONTEXT.md` terminology、澄清 overloaded terms、符合 gate 時寫 ADR。
  - `.agents/skills/engineering/領域建模/SKILL.md`
- **深度質詢**：design tree/frontier interview primitive。
  - `.agents/skills/productivity/深度質詢/SKILL.md`

## Verification / delivery

- 受影響的是 physical parts / 2D / 3D / DXF / Save→Reload → **驗證板件與DXF**。
- 建立 remote GitHub Actions / CI QA run → `monitoring-remote-qa`，鎖 `run_id + head_sha` 到 terminal。
- 正式 FULL/UPDATE packaging → `phase6-release-packaging`。
- 一般 diff review → `code-review`（存在且 runtime 可用時）；否則 inline review，不假裝背景 reviewer。

## Skill authoring

建立或修改 Skill → **寫技能**：

`.agents/skills/engineering/寫技能/SKILL.md`

中文資料夾 Skill 的 canonical identity 固定採 parent folder basename。使用者明確改名時要同步 frontmatter、README/router、Registry/tests/docs。

## Phase boundaries

在 phase boundary 依實際 runtime 能力選：continue、handoff、compact/新 session、或真正存在的 Subagent。不要把某個產品的 slash command 當成所有環境都必備。

- 有真正 Subagent Runtime 才委派 isolated task。
- 沒有就由同一執行者 inline 完成，不宣稱「已派出去」。
- 跨回合必要狀態落到 file/Issue/checkpoint/journal，不只靠聊天記憶。

## Canonical Chinese Skill map

```text
拷問邊建立文件 -> engineering/拷問邊建立文件
寫成規格書     -> engineering/寫成規格書
拆解任務工單   -> engineering/拆解任務工單
執行開發任務   -> engineering/執行開發任務
掃描深模組     -> engineering/掃描深模組
程式碼庫設計   -> engineering/程式碼庫設計
領域建模       -> engineering/領域建模
寫技能         -> engineering/寫技能
派工           -> engineering/派工
驗證板件與DXF  -> engineering/驗證板件與DXF
深度質詢       -> productivity/深度質詢
```

舊英文名稱可以出現在歷史文件或 migration 說明，但不能再作為上述中文資料夾的 canonical routing target。
