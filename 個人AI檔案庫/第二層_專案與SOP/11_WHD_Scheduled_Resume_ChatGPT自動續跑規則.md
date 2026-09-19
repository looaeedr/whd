---
whd_doc_role: CURRENT
whd_contract: whd-chatgpt-scheduled-resume
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD Scheduled Resume / ChatGPT 自動續跑規則

## Authority

本文件是 WHD「ChatGPT 被 execution-window hard-cut 後如何自動重新接手」的 AI Library CURRENT owner。

Executable state authority 仍是：
- `tools/continuity_controller.py`
- `.agents/skills/engineering/executable-continuity-controller/SKILL.md`

本文件負責跨 runtime / scheduler architecture 與長期判斷背景，不建立第二套 state machine。

## Canonical architecture

```text
Hourly ChatGPT Automation
→ fresh ChatGPT Runtime
→ fresh GitHub live readback
→ shared GitHub TTL lease
→ canonical continuity checkpoint
→ exact next_action execution
```

GitHub Actions `schedule:` 只能作 watchdog / lease / remote-run safety net；Claude/Codex/其他 headless agent 不是 primary executor，也不能當成「ChatGPT 自己續跑」的驗收證據。

## Durable owner / lease

每次 scheduled/manual resume 都必須 fresh-read：
- issue
- branch
- HEAD SHA
- checkpoint
- run_id/head_sha（若 WAITING_REMOTE）

共用 GitHub-backed TTL lease，至少包含：
- `holder`
- `acquired_at`
- `ttl_seconds`

有效 lease 存在時其他 actor safe no-op；lease 過期才可重新取得。Runner-local receipt 只能當 idempotency evidence，不能當跨 runtime lease authority。

## State routing

- `RUNNING`：直接執行 durable `next_action`。
- `WAITING_REMOTE`：只追 exact locked `run_id + head_sha`；active/non-stale 不建新 RUN。
- `RECOVERING`：evidence → root cause → minimal fix → validation → retry。
- `BLOCKED`：保留 genuine blocker；durable `blocked_count` 預設第 3 次才通知，後續至少 6 小時 backoff。
- `TERMINAL_SUCCESS / TERMINAL_FAILURE`：進 issue-closure-gate handoff；cleanup/closure 完成後才移除 scheduled-resume eligibility。

Scheduled WAITING_REMOTE stale threshold canonical default = 2 hours；live Runtime 內 remote-QA polling 仍約 30 秒，兩者不可混用。

## Active Runtime rule

**已有 hourly automation 不代表目前 Runtime 可以停。**

只要目前 Runtime 還能自主執行、poll、repair、acceptance、cleanup 或 closure，就必須在同一 runtime 繼續。Automation 的唯一目的，是平台 hard-cut 後自動重入；它不是 live execution throttle。

## Human agency / scheduler rule

使用者不是 scheduler。已知 next action 時不得要求使用者再輸入「繼續／輪／GO」才能推進。

## Validation boundary

Validation 只判定 implementation 是否符合 authority，不得反過來成為 production 計算來源。Scheduled Resume 也不得因測試方便而複製第二套 state machine、remote-run truth 或 lease authority。

## Acceptance evidence

正式 Scheduled Resume acceptance 必須至少證明：
- enabled hourly ChatGPT automation；
- 真實 scheduled invocation；
- fresh GitHub readback；
- shared lease semantics；
- duplicate mutation = 0；
- duplicate remote run = 0；
- stale wait recovery；
- continuity controller remains canonical；
- third-party agent not required；
- no user message required to wake.
