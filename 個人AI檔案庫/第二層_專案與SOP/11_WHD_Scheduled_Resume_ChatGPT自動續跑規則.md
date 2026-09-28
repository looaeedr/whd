---
whd_doc_role: MIRROR
whd_contract: whd-chatgpt-scheduled-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# WHD Scheduled Resume / ChatGPT 自動續跑規則

<!-- FLOW_V2_SCHEDULED_RESUME_V1 -->

本文件是 Scheduled Resume 的 AI Library mirror/reference；execution machine authority只在 `flow-v2-execution` 與 executable tools。

Recurring A/B wake → fresh-read `coord/execution-v2` → same-lane native ExecutionRecord first → lease acquire/reacquire → structured next_action → exact remote run polling → atomic terminal transaction/readback → DONE、genuine BLOCKED 或 YIELD。

Durable state是 `coord/execution-v2` + `.dispatch/execution/issue-<N>.json`；ready-index固定 `DERIVED_CACHE_ONLY`。open Issue或prompt prose不是state authority。

live lease退讓；expired lease依owner/lane contract atomic reacquire；沒有current record才讀ready-index；empty才是NO_EXECUTABLE_WORK。task未DONE而host invocation需要結束時必須YIELD。

Remote QA只追 record.active_run exact run/head；active不重送。重疊runtime使用execution generation fencing；舊generation失去authority但成果可donor salvage。

A/B不得自行disable/delete/complete/reschedule自己或sibling。2026-09-28前的舊execution coordination與separate exit/finalization語意只作歷史evidence。
