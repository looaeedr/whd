---
whd_doc_role: REFERENCE
whd_contract: ai-library-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
whd_doc_id: WHD-SOP-SPEC-SKILL-GROUNDING
---

# WHD 規格書 Skill 前置與 Grounding 規則

日期：2026-09-21

> **REFERENCE／非執行權威**。2026-09-21 當時的 Skill 公告與 Phase6 Preflight 步驟已退役；本文僅保留事故教訓與 grounding 方法。正式流程以最新 X 的 `AGENTS.md` 及 `.agents/skills/engineering/寫成規格書/SKILL.md` 為準。

## Grounding 參考

只要任務是建立、重寫、精修、更新、定稿或交付 WHD 工程／產品規格，**聊天記憶不能代替當次必需的 source grounding**。

現行參考順序：

1. 明確以正式 X `cleanup/2d-3d-sync` 作 CURRENT 基準，讀取 `寫成規格書` Skill（不從 GitHub 預設 `main` 猜測現行規則）。
2. 按該 CURRENT Skill 的 pre-spec grounding 閱讀 owning production code、相關 AI Library/SOP、既有 spec/design note、tests 及存在的 fixture/baseline/certified data。
3. 把使用者已確認的產品規則、current implementation、test oracle、probe 與 unresolved 分開，不將診斷值寫成規格真值。
4. 適用時檢查跨 Family、2D/3D、DXF、Save→Reload 與其他實體板件邊界。
5. 定稿依 CURRENT Skill 的 `DOWNLOADABLE_MD_DELIVERY_GATE` 實際交付 UTF-8 Markdown；如寫回 GitHub，仍按 `AGENTS.md` 的治理／產品分流與當次授權。
6. 不要求舊版 Skill 首行公告、Phase6 Preflight receipt、`READ_REFERENCE` 交易憑證或 `GIT_WRITE_UNLOCKED` 作為執行前置；來源必須真正讀過，並保留實際驗證與回讀。


## 這次事故

2026-09-21「板件接合定位打標」v1.3 精修時，AI 先人工修改規格，之後才 fresh-read `寫成規格書/SKILL.md`。

根本原因：

> 把「前面聊天已經知道這個 Skill／大概知道內容」誤當成「本次 invocation 已完成 canonical Skill read」。

永久判定：

> **KNOWING_IS_NOT_READING** — 知道、記得、摘要過、上一輪讀過，都不能取代本次 fresh-read。

## Authority

1. `AGENTS.md`（**正式 X**）：執行權限、治理／產品路由及 GitHub 交付規則。
2. `.agents/skills/engineering/寫成規格書/SKILL.md`：規格 grounding、Evidence classification 與 Markdown artifact 交付的唯一 CURRENT Skill。
3. `.agents/skills/skill_registry.json`：技能／參考路由資料，不授予 DC／本機施工權限，也不恢復已退役 Preflight receipt。
4. `docs/governance/WHD_規格書Skill前置與Grounding規則.md`：MIRROR 導覽，不能蓋過 CURRENT Skill。
5. 本 REFERENCE 文件：僅提供 2026-09-21 事故與 grounding 踩坑，不是額外啟動門檻。

## 禁止

- 「我記得 Skill 內容，所以不用再讀」。
- 「上一輪讀過，所以這一輪算已讀」。
- 先開始寫正文，再事後補一句「使用 Skill」。
- 只宣稱使用 Skill，卻沒有讀取實際相關的規格／程式／測試證據。
- 只跑形式檢查，沒有讀取 CURRENT domain authority。
- 用 current implementation、passing test、probe 或聊天推測替代產品 authority。
- 修改完只口頭說已同步，沒有遠端反讀。

## Source of Truth

- `.agents/skills/engineering/寫成規格書/SKILL.md`
- `AGENTS.md`
- `docs/governance/WHD_規格書Skill前置與Grounding規則.md`
