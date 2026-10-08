---
whd_doc_role: REFERENCE
whd_contract: flow-v2-compact-context
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD Flow v2 唯讀精簡執行上下文（試行）

WHD_FLOW_V2_COMPACT_CONTEXT_V1 只整理現有 ExecutionRecord 執行必要欄位；不是另一個流程狀態機、不是執行證據，也不儲存聊天推理。實作：tools/flow_v2_compact_context.py。

- Scheduler 呼叫 build_scheduler_view(..., context_mode="COMPACT") 可取得 SchedulerView.compact_context；不指定時維持 LEGACY 且 compact_context is None。兩種模式的 decision、owner、lease 與 transaction 欄位必須完全一致。
- 其他執行器可直接呼叫 build_compact_execution_context(record, ...)；來源必須是 fresh canonical coord/execution-v2 的原生紀錄。精簡物件不得提交為另一筆 ExecutionRecord，也不得覆寫 existing record。
- Context 帶 fingerprint/generation/HEAD/owner/QA/next_action、lease 是否存在及期限，不包含 lease token。缺 Issue/PR 回讀時顯示 NOT_INCLUDED_MUST_FRESH_READ_BEFORE_EFFECT。缺留言 feed 為 UNKNOWN_NOT_FETCHED；有 feed 才委託既有 evaluate_issue_comment_intervention 以 server time 驗證。
- GitHub Issue/PR、CI、ACQUIRE、HANDOFF、MERGE、FINALIZE、SYNC_TARGET 都必須由既有受信任執行器 fresh readback + native CAS；精簡 context 的介入候選不是接手授權，也不代表 QA/required checks 已 GREEN。
- 本方案不會自動清除宿主 LLM 對話歷史，不會自動持續執行或每 10 分鐘留言，也不更動 recurring scheduler 設定。
- 效能評估分別記錄：決策等價、安全攔截、輸入字元量、模型實際延遲。JSON microbenchmark 不得當作模型端加速證據。

回退只需移除 context_mode="COMPACT"，不得移除 Flow v2 硬閘門。
