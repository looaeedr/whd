---
whd_doc_role: CURRENT
whd_contract: whd-chatgpt-scheduled-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# WHD Scheduled Resume / ChatGPT 自動續跑規則

<!-- FLOW_V2_SCHEDULED_RESUME_V1 -->

本文件是 Scheduled Resume 的 AI Library CURRENT reference；execution machine authority只在 `flow-v2-execution` 與 executable tools。

## Canonical architecture

```text
Recurring A/B wake
→ fresh-read coord/execution-v2
→ same-lane native ExecutionRecord first
→ lease acquire/reacquire
→ execute structured next_action
→ exact remote run polling
→ atomic terminal transaction/readback
→ DONE, genuine BLOCKED, or YIELD
```

Durable state：`coord/execution-v2` + `.dispatch/execution/issue-<N>.json`。ready-index固定 `DERIVED_CACHE_ONLY`。prompt/comment/chat memory不是state authority。

Wake固定 same-lane nonterminal first；live lease退讓；expired lease依owner/lane contract atomic reacquire；沒有current record才讀ready-index；ready-index empty才是NO_EXECUTABLE_WORK；open Issue本身不能自動變工作。

Scheduled automation只是fresh runtime入口，不是task state。task未DONE而host invocation需要結束時必須YIELD。現在runtime還能執行、poll、repair、acceptance或closure時，進度回報後繼續。

Remote QA只追 record.active_run exact run/head。active不重送；terminal後回寫同一record並續structured action。

重疊runtime使用execution generation fencing。舊generation失去authority但成果可當donor；能證明相容就收編，只重做stale/conflict部分。

A/B不得自行disable/delete/complete/reschedule自己或sibling。單一invocation return不等於recurring automation terminal。

2026-09-28起，舊 execution coordination、receipt、heartbeat/end、turn-exit與separate finalization語意只作歷史evidence，不得作Scheduled Resume authority。
