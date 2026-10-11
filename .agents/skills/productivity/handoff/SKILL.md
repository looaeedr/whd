---
name: handoff
description: Compact current work into a durable handoff so another session or agent can continue without relying on hidden conversation state.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: handoff
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Handoff

## RUNTIME_CAPABILITY_FALLBACK

Prefer durable project state that the next executor can actually read: owning Issue/PR, checkpoint/journal, spec, ADR, commit/branch, and repo-local handoff when the project requires one. An OS temporary directory is only an optional ephemeral **inline fallback**, not a hard requirement.

Write a concise handoff that summarizes only context not already captured elsewhere. Reference existing artifacts by path/URL instead of duplicating specs, plans, ADRs, issues, commits or diffs.

Include a `Suggested Skills` section only when useful. Name each Skill by its **canonical identity** and path/classification where known; do not instruct the next agent to use a generic product-specific loader. The next runtime decides how to load or apply it. For WHD, active status comes from `.agents/skills/skill_catalog.json` and only `canonical` is active by default.

If the runtime provides native compaction/handoff support, it may be used. Otherwise the same executor writes the handoff inline. Never claim a fresh/background agent was started unless the runtime actually started one.

Redact secrets, credentials, account identifiers, and unnecessary personal information. If the user supplied a next-session focus, make that the resume target and include the exact next safe action, blockers, branch/HEAD and active remote QA lock when relevant.

## WHD 上下文風險交接（`WHD_CONTEXT_RISK_CHECKPOINT_V1`）

優先遵循正式 X 的 `AGENTS.md`：只按可觀察的資訊完整性區分 `NORMAL / WATCH / HIGH`，**不要宣稱知道剩餘 Token 或壓縮倒數**。使用者說 `/上下文` 時回報分級與依據；說 `/交接` 時直接產生下列交接，不以必要資料已在當前對話為由拖延。兩者是約定用語，不是平台自動註冊的工具／排程。

```text
【WHD_CONTEXT_CHECKPOINT_V1】
風險：NORMAL | WATCH | HIGH（附可觀察原因）
repo / Issue / PR：
執行者與接取狀態：
來源分支 → 目標分支 / 最新已核實 head_sha：
已完成與證據（commit / PR / CI）：
當前步驟 / run_id / 長日誌 cursor（適用時）：
阻塞、未完成事項：
下一個精確動作：
授權界線（含 /推推 是否已於當次核准）：
來源連結 / Asia/Taipei 日期：
```

只新增此次需要的狀態，不重貼完整 log、規格或歷史摘要；未查核項目明寫「未核實」。已有 owner Issue 且允許寫入時，用該 Issue 的 `【WHD_CONTEXT_CHECKPOINT_V1】` 留言，並回讀確認；不可新建第二張工單或把交接當作施工完成。無 GitHub 寫入權限就 inline 交付並註明未持久化。新對話先讀交接再核對**最新 GitHub**，不能用過期 SHA 直接發布。風險檢查結束繼續原工作；不得增加新門檻、假裝背景自動提醒或變更 DC／localX／X 授權。
