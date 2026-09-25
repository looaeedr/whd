---
whd_doc_role: REFERENCE
whd_contract: ai-library-reference
whd_canonical: ".agents/skills/engineering/寫成規格書/SKILL.md"
whd_schema: WHD_DOC_META_V1
---

# WHD 規格書 Skill 前置與 Grounding 規則

日期：2026-09-21

## 永久規則

只要任務是建立、重寫、精修、更新、定稿或交付 WHD 工程／產品規格，**聊天記憶不能算 Skill read**。

固定流程：

1. 第一個 user-visible 內容先公告：`使用「寫成規格書」技能。`
2. 本次 invocation fresh-read `.agents/skills/engineering/寫成規格書/SKILL.md`。
3. 執行 `tools/phase6_skill_preflight.py`，取得 required Skills / required references。
4. required references 必須逐一實讀並留下 `READ_REFERENCE: <path>` evidence。
5. 依 Skill mandatory pre-spec gate 交叉讀 owning production code、AI Library/SOP、既有 spec/design note、tests，以及存在時的 fixture/baseline/certified data。
6. 以上完成前不得開始 normative spec drafting。
7. 若先寫後讀，先前內容只能標為 **NON-CANONICAL / PRE-GATE DRAFT**；事後補讀不能回溯洗白。
8. 使用者更正、可重複踩坑或新的永久 AI 行為規則，必須同步 durable 文檔、AI Library 與必要的全域踩坑庫，最後遠端反讀。
9. 最終規格必須依 `DOWNLOADABLE_MD_DELIVERY_GATE` 提供實際可下載 UTF-8 Markdown artifact。

## 這次事故

2026-09-21「板件接合定位打標」v1.3 精修時，AI 先人工修改規格，之後才 fresh-read `寫成規格書/SKILL.md`。

根本原因：

> 把「前面聊天已經知道這個 Skill／大概知道內容」誤當成「本次 invocation 已完成 canonical Skill read」。

永久判定：

> **KNOWING_IS_NOT_READING** — 知道、記得、摘要過、上一輪讀過，都不能取代本次 fresh-read。

## Authority

1. `AGENTS.md`：公告、Preflight、durable writeback、branch-first。
2. `.agents/skills/engineering/寫成規格書/SKILL.md`：grounded spec authoring canonical workflow。
3. `.agents/skills/skill_registry.json` + `tools/phase6_skill_preflight.py`：machine route / required references。
4. `docs/governance/WHD_規格書Skill前置與Grounding規則.md`：本條永久治理說明。
5. 本 AI Library 文件：讓後續 Agent 在知識預載階段能直接命中此踩坑。

## 禁止

- 「我記得 Skill 內容，所以不用再讀」。
- 「上一輪讀過，所以這一輪算已讀」。
- 先開始寫正文，再事後補一句「使用 Skill」。
- 只公告 Skill 名稱，沒有真的讀 Skill / Preflight。
- 只跑 Preflight，沒有讀 required references。
- 用 current implementation、passing test、probe 或聊天推測替代產品 authority。
- 修改完只口頭說已同步，沒有遠端反讀。

## Source of Truth

- `.agents/skills/engineering/寫成規格書/SKILL.md`
- `AGENTS.md`
- `docs/governance/WHD_規格書Skill前置與Grounding規則.md`
