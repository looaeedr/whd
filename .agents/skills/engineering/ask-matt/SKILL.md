---
name: ask-matt
description: Ask which skill or flow fits the current situation. Routes to the real filesystem skills in this repo and uses Chinese canonical identities for Chinese-named skill folders.
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: ask-matt
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Ask Matt

這是 repo Skill router。Filesystem `.agents/skills/**/SKILL.md` 只提供 **inventory evidence**；`.agents/skills/skill_catalog.json` 是 active **classification** authority，只有 `canonical` 預設是 WHD active Skill。README 只是導覽，Registry 是技能／必要參考資料的路由資訊，**不是已退役 Phase6 Preflight receipt 或施工授權**；`reference/upstream-beta/tool-specific/retired` 不得因檔案存在就自動成為 current routing owner。**CURRENT 施工規則只能從 GitHub `ref=localX` exact HEAD 讀取**，正式 `ref=cleanup/2d-3d-sync` 只作當次 `/推推` 發布及受信任 X gate 查核；GitHub 預設 `main` 只作歷史參考。

## Main flow：idea → ship

1. **拷問邊建立文件** — 有 repository/workspace 時先用深度質詢把 design tree 問清楚，並同步 `CONTEXT.md` / ADR。
   - canonical path：`.agents/skills/engineering/拷問邊建立文件/SKILL.md`
   - 若沒有 working directory、只想純訪談，可直接用 **深度質詢**。
2. **需要 runnable answer 的 design question** — 可用 `prototype` 做 throwaway experiment；跨 session/harness 時可配 `handoff`。
3. **多 session build**：
   - **寫成規格書** → 將 grounded conversation/code/AI Library 收成 spec。
   - **拆解任務工單** → 已核准規格直接使用 `APPROVED_REQUIREMENT_FAST_PATH` 拆 tickets；僅真正未定案需求才進 requirement discovery。
   - **執行開發任務** → 只提供實作方法：`/派工` 的產品施工／測試／提交須由真正 GitHub／雲端執行器完成，當次明確 `/接手` 才可經 RC 施工；遵守適用 TDD／QA／`localX` 驗收及 `/推推` 發布規則。
4. **小而已明確的 build**：可直接讀 **執行開發任務** 的方法，但讀取 Skill **不等於取得施工、DC 或發布權限**；先依 GitHub `ref=localX` 的 CURRENT `AGENTS.md` 核對原 Issue／scope。**純治理與產品均先經 GitHub／雲端工作分支、適用 CI、PR 合併 `localX`**；正式 X 不論治理或產品，均須使用者當次 `/推推`（即驗收／發布決定）及受信任 X gate，Windows 人工 UAT 不另作發布前置。`/派工` 依原範圍施工，只有當次明確 `/接手` 可選 RC；不得以找技能或路由結果自行授權 DC。


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
- **已退役** `WHD_EXECUTION_RECORD_V2`、claim／lease／工作槽等交易前置不得恢復，也不得拿聊天摘要當執行證據。跨回合只能依最新 GitHub Issue／PR／exact SHA／CI 和當次工具結果回讀實際狀態；沒有真實排程或執行器時，不得假裝會背景續作、已派工或已有 worker 施工。

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
