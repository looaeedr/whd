---
whd_doc_role: REFERENCE
whd_contract: issue-comment-intervention-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 2026-10-08 #1412 — 不能把監控事件當工單介入證據

**事故型態**：scheduler 曾用 runtime END、heartbeat expiry、lease expiry、owner moved、child/family liveness 判定 foreign ownership 是否 stale。不同執行者見到的資料源不同，有機會出現搶單、重複確認與長時間無進度。

**CURRENT 改法**：取得 Flow v2 claim 後立即於同 GitHub 工單留言身份，每 10 分鐘留言真實進度；後來者只用可信 Issue comment server created_at + exact native record owner/generation/branch/HEAD 判定。<=600 秒不得介入，>600 秒才可進 CAS 交接。留言缺失、身份不明一律 fail closed。接手者自己發 TAKEOVER 留言並繼續 next_action。

**不得回長**：不得恢復 420 秒 heartbeat freshness、600 秒 durable progress、active Actions run、owner END 或多 Issue family liveness 作為介入 eligibility；保留這些資訊的監控功能不等於可以重新用它們決定接手。永久機器基準在 `tools/issue_comment_progress.py`，文件在 `docs/governance/issue_comment_intervention_policy.md`，canonical Skill 在 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

**重要區別**：10 分鐘時間判定只有一個，**原子 owner/CAS/單寫者安全防線不能刪**。不應把「只查工單」誤寫成「不檢查 GitHub 原子變更衝突」。
