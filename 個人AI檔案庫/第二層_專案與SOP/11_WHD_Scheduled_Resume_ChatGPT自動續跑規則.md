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

## Scheduled progress heartbeat

使用者必須能區分「ChatGPT 正常靜默工作」與「Runtime/remote work 已卡住」。因此 Scheduled Resume 的長期可見性規則是：

- 只要本輪偵測到 active work，scheduled ChatGPT invocation 結束前就必須主動回報，不可完全靜默。
- 第一行狀態固定投影為 `WORKING / WAITING_REMOTE / RECOVERING / BLOCKED / COMPLETE` 之一。
- 至少帶 owning issue、branch、HEAD、必要的 run_id、exact next_action，以及 `正常工作中 / 正常等待既有 RUN / 正在復原 / 真 blocker / 已完成` 判斷。
- `WAITING_REMOTE` 必須帶 exact run identity 與 current step/status；長時間無 remote 更新要明示 `疑似卡住` 並服從既有 stale-recovery policy。
- shared lease 被另一個合法 Runtime 持有時，safe no-op 仍要回報 `WORKING — 另一 runtime 持有有效 lease`，讓使用者知道 mutual exclusion 正常運作。
- **沒有 active work** 時才允許保持安靜。
- heartbeat 只做 visibility projection，不建立第二套 state machine，也不取代 durable checkpoint。
- heartbeat 不是 execution cadence：目前 Runtime 還能繼續時，回報後仍繼續做；live remote-QA 約 30 秒 cadence 仍由 monitoring-remote-qa 負責。

Canonical executable owner：`.agents/skills/engineering/executable-continuity-controller/SKILL.md::SCHEDULED_RESUME_PROGRESS_HEARTBEAT`。

## Immediate terminal progress report

當 Scheduled Resume 或 live Runtime 已取得 evidence-backed PASS / FAIL / COMPLETE terminal evidence，必須**立即**讓使用者看到結果；不得先做 secondary readback、額外 evidence collection、cleanup 或其他非必要核對，導致使用者誤以為 Runtime 卡住。

- 只接受 live terminal evidence，不允許預測式成功／失敗宣告。
- 先報 owning issue / branch / HEAD / run_id / terminal result / next action。
- 有收尾時，回報後仍繼續 cleanup / invariant / writeback / closure；立即回報不是停工。
- failure 可修復時，回報後立刻進 recovery。
- 這是 heartbeat/visibility 優先序，不建立第二套 execution state machine。

## Polling is observation-only

**輪詢只能看進度，不能產生進度。** Scheduled Resume 只有在 real progress producer 已存在時才能維持 WAITING_REMOTE。

- real progress producer 例：exact GitHub Actions run、已提交的 remote job、其他已啟動 executor。
- no executor / no active run / no producer：立即離開 waiting，回 RUNNING 或 RECOVERING 執行 prerequisite / trigger / repair。
- RUN_NOT_CREATED 不是等待狀態；它要求建立或修正真正的 producer。
- terminal run 只代表觀測到結果；下一步仍必須由 executor 執行。
- 反覆 poll 同一靜止狀態不算 progress。
- 使用者不是 scheduler，不應靠「輪／繼續」來製造進度。

<!-- ISSUE646_SCHEDULED_RESUME_V1 -->
## #646 scheduled resume canonical usage

Wake-up不是 owner。每輪 fresh reconstruct，依序處理 Guard transaction、drift、delegated/helper/proof、helper dedupe、stale evaluator、Guard single-use mutation、readback、turn-exit。EXPIRED_UNCONSUMED 不得重播舊 GREEN，只能 fresh recovery Guard。

Scheduler provenance 必須 lane + invocation identity，machine owner 仍是 `tools/scheduler_runtime_liveness.py`。Interactive ChatGPT provenance 已由 `tools/interactive_runtime_liveness.py` 擁有，marker 為 `WHD_INTERACTIVE_RUNTIME_LIVENESS_V1 / WHD_INTERACTIVE_RUNTIME_END_V1`，必須保存 exact slot + worker + conversation/chat identity + invocation identity + claim blob + branch + HEAD。Interactive 與 Scheduler liveness 是兩個獨立 namespace；不得以 generic `chatgpt_interactive` / `executor_source` 或 Scheduler heartbeat 冒充 interactive exact provenance。

<!-- ISSUE680_PLANNED_HANDOFF_SCHEDULER_READINESS_V1 -->
## Planned executor handoff vs stale takeover

`WHD_WORK_EXECUTOR_HANDOFF_V1` is a planned ownership transfer, not stale recovery. When an interactive executor deliberately hands the current checkpoint / exact `next_action` to Scheduler A or B, the sender must use the canonical guarded `claim-handoff` transaction to CAS the shared claim to the exact target lane. The handoff identity binds old worker, target scheduler worker, handoff generation, claim blob, branch, HEAD, canonical checkpoint fingerprint, and current `next_action`.

Receiver order is fixed: fresh-read the handoff transaction + shared claim/checkpoint/branch HEAD; verify `to_worker == scheduler.<exact-lane>`, generation, claim blob, branch, HEAD, checkpoint fingerprint and `next_action`; fresh-read that the shared claim owner is already the target lane; then resume the same checkpoint / exact `next_action`. A completed planned handoff must not run the stale evaluator, wait for stale TTL, or invoke `claim-takeover` again.

`claim-takeover` remains recovery-only: it requires a foreign stale/orphaned owner, no active exact run, an actionable canonical stale classification, and Guard GREEN. Planned handoff and stale takeover are not substitutes for one another.

Scheduler-readiness owner boundary:
- ownership transfer / claim CAS / exact identity: Dispatch Skill + canonical Guard;
- `claim-handoff` executable enforcement: `tools/execution_claim_guard.py` + trusted Remote Guard workflow;
- checkpoint / `next_action` continuity: `tools/continuity_controller.py`;
- scheduler liveness: `tools/scheduler_runtime_liveness.py`;
- scheduler prompts/entrypoints perform routing/receive only and do not own a second continuity state machine.

Any identity drift, unverifiable readiness, or failed post-CAS owner readback is fail-closed. Chat titles, memory, or merely observing an open Issue cannot substitute for durable evidence.
