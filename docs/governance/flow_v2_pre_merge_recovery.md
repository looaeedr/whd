---
whd_doc_role: REFERENCE
whd_contract: flow-v2-pre-merge-recovery
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Flow v2 — 已交付、未合併、漏接取的正式接入

## 入口與禁止事項

正常流程固定 **先完成正式 native DISPATCH_READY → ACQUIRE / owner 留言 → 實作 → QA → PR → MERGE → FINALIZE**。Phase6 Preflight／CI GREEN／開 PR 不是 ACQUIRE，也不能建立 ExecutionRecord。不得把接取入口擺到施工／PR 之後。

若歷史意外已經產生可信的 **OPEN、未合併的 PR**，同一 Issue 的 ExecutionRecord 卻不存在，這才是 `RECOVER_PRE_MERGE` 的窄範圍 repair condition（不是正常發包或 shortcut）。

- 工作成果、現有 PR、原有 CI 不得刪除重做。受信任的 push-transaction ingress 在 fresh startup／Phase6 Preflight 後呼叫 production executor；只允許 `authority_kind=USER_EXPLICIT`，不得宣稱早已 ACQUIRE。
- executor fresh-read owning Issue 必須 OPEN、不是 PR；PR 必須 OPEN / merged=false / mergeable=true、同 repository、base `cleanup/2d-3d-sync`，PR body 以 exact closing keyword 綁 Issue；HEAD／production TARGET 與 caller supplied expected SHA 必須完全一致；目標 branch 的 required checks 必須全部 SUCCESS。
- `coord/execution-v2` exact Issue record **必須不存在**；create-only、fresh coord expected HEAD、non-force CAS，只能在其他 Issue 的 coord race 中重試；same-Issue 出現即 fail-closed。
- 正式結果僅有 **generation 1 / READY / UNCLAIMED**；`qa` 清空、`lease` 空、`active_run` 空；proof 標 `historical_acquire_reconstructed=false`、`qa_history_reconstructed=false`。禁止輸入舊 owner／QA／lease 以倒填歷史。
- 綁定 `ACQUIRE.post_acquire=START_QA`，其 args 保存 exact `pr_number`，表示取得當前正式 owner 後才能在相同 HEAD 讀取 CI、走原生 `CONSUME_QA`；舊 CI 若滿足 `completed/success`、workflow/head，便可原生 consume，而**不是**偽造之前的 QA 交易。失效才重跑測試。
- QA acceptance（產生 `next_action=MERGE`）後依既有可信 `MERGE → FINALIZE → close readback → RELEASED/DONE`；RECOVER_PRE_MERGE 不含 merge、副作用及進度留言。
- 取得 owner 後應立即於 exact Issue 留 `WHD_ISSUE_OWNER_PROGRESS_V1` 並每 10 分鐘報進度。此 recovery 產生 READY 本身 **不建立**留言介入時間，不宣稱 owner。
- 新 route 與既有 `RECOVER_POST_DELIVERY` 分開：後者僅供 PR 已合併且缺 record；此路徑僅供 PR 未合併。

若 startup evidence／owner lane／native transaction capability 不可用，依現有權限 fail-closed 並保留 PR，不准直接以 GitHub connector merge 代替 Flow v2。
