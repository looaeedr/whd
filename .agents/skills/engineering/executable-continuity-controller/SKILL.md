---
name: executable-continuity-controller
description: Use for long-running WHD execution, remote QA, recovery, checkpoint persistence, resume after runtime cuts, and any workflow finalization decision that must be enforced by executable state rather than prose alone.
whd_doc_role: CURRENT
whd_contract: continuous-execution-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Executable Continuity Controller

## EXECUTION_SCOPE_AUTHORITY_GATE_V1

Continuity is allowed to continue **only inside an already-authorized execution scope**. It must never create authority for a new phase, architecture, ownership boundary, or task chain.

### Authorized execution scope

Autonomous implementation may proceed only when all applicable authority exists and is fresh-read from durable project sources:

- an **accepted specification** or other explicitly approved implementation contract;
- the concrete owning issue/task/work order;
- the approved task boundary and predecessor/base;
- required protected scope / invariants / acceptance gates;
- for resumed work, a valid owning checkpoint with an exact `next_action`.

When these exist, user commands such as `繼續`, `GO`, or `輪` mean: **continue the current authorized scope**. They do not expand scope.

### Specification-required boundary

The following are specification-authority changes and MUST fail closed into specification/planning work when no accepted spec already authorizes them:

- starting a new Phase / milestone / architecture program;
- inventing or changing an ownership boundary;
- inventing a new task chain or predecessor chain;
- choosing a new extraction/decomposition strategy after the prior accepted chain is complete;
- changing protected surfaces, acceptance gates, or cumulative baseline rules;
- converting exploratory analysis into production implementation.

In this state, the assistant MAY:

- inspect/read current production;
- perform non-mutating census/analysis;
- draft or revise a specification;
- identify candidate task boundaries and risks for review.

Until the spec is accepted, the assistant MUST NOT:

- create implementation issues/tickets as if approved;
- create implementation branches/worktrees;
- add RED/GREEN implementation tests for the proposed new scope;
- modify product/runtime code;
- merge any proposed implementation or QA bootstrap into production;
- treat exploratory GREEN evidence as accepted task evidence.

### Continuity precedence

`continuity != authority expansion`.

The "do not stop", turn-exit, polling, scheduled re-entry, and exact-next-action rules apply **after** execution authority is established. They cannot be used to bypass this gate.

If the current authorized chain reaches completion and the apparent next action would begin a new, unspecified phase, the exact next action becomes:

```text
SPECIFICATION_REQUIRED
→ inspect current state
→ draft/revise spec
→ obtain accepted spec/task graph
→ only then enter implementation continuity
```

Do not ask the user to repeatedly say `繼續` to advance already-authorized work. Conversely, do not interpret `繼續` as approval of a new architecture or phase that has not been specified.

## SCHEDULED_WAKEUP_CONTINUITY_CONTRACT

This Skill is the unique operations/semantic CURRENT authority for scheduled wake-up continuity. An automation or schedule is only a wake-up trigger; it never becomes the execution owner. Canonical shorthand: `wake-up trigger != execution owner`.

On every scheduled wake-up, first restore and live-verify the owning issue/checkpoint/branch/current concrete RUN identity, then continue the owning plan rather than producing a status-only response.

- Concrete RUN exists: lock exact `run_id + head_sha`, poll to terminal, read jobs/logs/evidence, then execute the next autonomous step. `terminal => continue next autonomous step`.
- No concrete RUN exists when one is required: classify `RUN_NOT_CREATED`; do not wait or poll. Immediately execute/fix the prerequisite or trigger that should create the RUN.
- GREEN is not an exit reason; advance to the next unfinished gate/slice.
- RED is not an exit reason; inspect exact failure evidence, classify it, apply the smallest valid TDD repair, and revalidate.
- A progress/status report is observation only: `status update != exit`.
- Schedule cadence is wake-up cadence, not execution cadence. Once awake, continue execution/polling inside the available turn.

### WATCHDOG_FALLBACK_ONLY_CONTRACT

Scheduled automation/watchdog is a resilience layer, not a substitute executor.

- `watchdog/schedule presence != permission to stop`.
- 當前 Runtime 仍可執行時，必須繼續目前施工／polling／recovery；「已有下一次排程」不是 `assert_turn_exitable` 的新理由，也不能把 non-terminal checkpoint 視為可退出。
- `watchdog wake-up → restore owner → continue exact next action`。每次喚醒都先載入 durable checkpoint、驗 issue/branch/HEAD/run identity，再執行保存的 next action；禁止 `status-only watchdog response` 後退出。
- Watchdog frequency only bounds interruption-recovery latency. It does not throttle or replace active execution inside a live Runtime.
- Watchdog shutdown is owned by the same chain: `owning chain COMPLETE/closed + final acceptance/cleanup finished`。在此之前 watchdog 保留作為 fallback；條件成立後必須 **disable the watchdog**，避免 chain 結束後仍持續輪詢。
- Child-task completion、單一 terminal RUN、GREEN、checkpoint 或 progress report 都不是 watchdog shutdown condition。
- If the platform/tool forces the turn to end, persist `checkpoint before forced turn end`: owning issue, branch, HEAD, RUN identity/status, last accepted gate, next exact action, and prohibitions. The next wake-up resumes from that checkpoint.
- Project-specific automation prompts may add owner/scope/prohibition data but must reference this contract rather than define a second continuity authority.

## EXECUTABLE_CONTINUITY_CONTROLLER_V1

Canonical executable authority: `tools/continuity_controller.py`.

This Skill is the unique operations/semantic CURRENT authority for using that executable controller. It does not replace domain Skills. It provides the operational contract that `執行開發任務`, `monitoring-remote-qa`, and closure/finalization gates must delegate to.

## Required states

- `RUNNING`
- `WAITING_REMOTE`
- `RECOVERING`
- `BLOCKED`
- `TERMINAL_SUCCESS`
- `TERMINAL_FAILURE`

`RUNNING`, `WAITING_REMOTE`, `RECOVERING`, and `BLOCKED` are non-terminal. Every non-terminal checkpoint MUST contain a nonblank `next_action`.

`WAITING_REMOTE` additionally MUST contain the exact positive `run_id` and nonblank `head_sha`; when known, persist `job_id`, `log_cursor`, and accepted evidence too.

Terminal checkpoints MUST have `next_action = null`. A terminal checkpoint cannot transition back into an active state; new work starts from a new checkpoint lineage/branch as required by Branch-First.

## Durable checkpoint contract

Use the Python API or CLI in `tools/continuity_controller.py` to validate and persist state. Checkpoints are versioned JSON and are written atomically in the same directory before `os.replace` promotes them to the authoritative path.

Runtime interruption therefore means:

1. Reload the authoritative checkpoint.
2. Verify branch/HEAD and exact remote identity against GitHub.
3. If identity has not drifted, execute the stored `next_action` exactly.
4. If identity drifted, classify the drift and revalidate only the affected scope.
5. Never restart completed phases merely because the chat/runtime restarted.

## Finalization gate

`assert_finalizable(checkpoint)` is a **state-only predicate**. It remains valid for controller internals and legacy behavior tests, but it is **not sufficient closure authorization**.

Workflow/issue/acceptance closure MUST use the owned finalization guard below and must not infer completion from prose markers, a terminal-looking JSON file, chat text, or a remembered prior guard result.

### OWNING_FINALIZATION_GUARD_V2

Immediately before an irreversible closure action, bind the durable checkpoint to the exact current owner identity:

- exact issue / workflow identity;
- exact owning branch;
- fresh exact owning HEAD SHA.

CLI authorization:

```bash
python -m tools.continuity_controller authorize-finalization path/to/checkpoint.json \
  --issue '#291' \
  --branch fix/example \
  --head-sha <fresh-40-char-head> \
  --proof-out path/to/finalization-proof.json
```

The command MUST fail closed when:

- owning checkpoint is missing, malformed, or non-terminal;
- expected issue, branch, or HEAD is missing;
- checkpoint issue, branch, or HEAD does not exactly match the expected current owner;
- any other state-only finalization condition fails.

A successful call emits `FINALIZATION_GUARD_PASS` and an atomic `FinalizationProof` bound to the exact checkpoint fingerprint. The receipt is process-integrity evidence against accidental bypass/stale state; it is not a cryptographic signature against a malicious writer.

Immediately before the actual close/finalize mutation, verify the proof again:

```bash
python -m tools.continuity_controller verify-finalization-proof \
  path/to/checkpoint.json \
  path/to/finalization-proof.json \
  --issue '#291' \
  --branch fix/example \
  --head-sha <fresh-40-char-head>
```

The closure boundary MUST fail closed when:

- no proof exists;
- proof is malformed or has the wrong version;
- proof owner differs from the current expected issue/branch/HEAD;
- checkpoint changed after guard invocation, including evidence mutation;
- someone only states that the guard ran without presenting a current proof that verifies.

No proof may be reused across issue, branch, HEAD, or checkpoint mutation. If any of those changes, rerun authorization and produce a new proof.

Python API:

```python
from tools.continuity_controller import (
    load_checkpoint,
    authorize_finalization,
    assert_finalization_proof,
)

checkpoint = load_checkpoint(path)
proof = authorize_finalization(
    checkpoint,
    expected_issue=issue,
    expected_branch=branch,
    expected_head_sha=head_sha,
)
assert_finalization_proof(
    checkpoint,
    proof,
    expected_issue=issue,
    expected_branch=branch,
    expected_head_sha=head_sha,
)
```

Bare `assert_finalizable(checkpoint)` must never be cited as proof that issue closure or workflow finalization was actually authorized.

## TERMINAL_CLOSURE_TRANSACTION_HARD_GATE_V1

A terminal child checkpoint records acceptance outcome; it does **not** by itself mean process closure is complete. Canonical machine authority is the `ClosureState` carried by `tools/continuity_controller.py`:

```text
FINALIZATION_PENDING
→ ISSUE_CLOSE_PENDING
→ RELEASE_HANDOFF_PENDING
→ CLOSED
```

Contract:

- canonical nonterminal → terminal transition automatically enters `FINALIZATION_PENDING` with a durable `closure_next_action`;
- a persisted legacy terminal checkpoint missing closure metadata is recovered as `FINALIZATION_PENDING`, never silently treated as closed;
- `assert_finalizable` remains a terminal-only state predicate, but `authorize-finalization` MUST additionally require `closure_state=ISSUE_CLOSE_PENDING`; proof cannot be minted in `FINALIZATION_PENDING`;
- `advance_closure(...)` is terminal-only and adjacent/monotonic; backward transitions, skipping stages, or advancing an already `CLOSED` transaction fail closed;
- `assert_turn_exitable` rejects every terminal checkpoint whose `closure_state != CLOSED` and surfaces its exact `closure_next_action`;
- CLI `resume` returns `closure_next_action` before any Master successor handoff while closure remains pending;
- first advance `FINALIZATION_PENDING → ISSUE_CLOSE_PENDING`; then authorize + verify the bound proof on that exact checkpoint and do not mutate the checkpoint again before Issue close; after Issue close + fresh `closed/completed` readback, advance to `RELEASE_HANDOFF_PENDING`;
- the final coordination mutation MUST atomically persist all three facts: checkpoint `closure_state=CLOSED`, execution claim `phase=RELEASED`, and successor/chain handoff. This avoids an impossible post-release checkpoint write and closes the half-terminal gap.
- `CLOSED` only completes the current child closure. Existing `MASTER_CHAIN_TURN_EXIT_HARD_GATE_V1` still rejects exit when `chain_state=NEXT_CHILD_EXECUTABLE`.

Turn-exit proof payloads bind `closure_state` in addition to owner/master/checkpoint digest. Finalization proof also binds the complete checkpoint fingerprint: enter `ISSUE_CLOSE_PENDING` first, mint/verify proof second, then keep that checkpoint byte-for-byte unchanged until the irreversible Issue close + readback boundary.

## Resume gate

For a persisted non-terminal checkpoint:

```bash
python -m tools.continuity_controller resume path/to/checkpoint.json
```

The returned action is the exact durable next action. `WAITING_REMOTE` still delegates polling mechanics and cadence to `monitoring-remote-qa`; this controller owns only durable state integrity and finalization enforcement.

## Remote QA bridge

When remote QA is submitted, transition and persist:

- state = `WAITING_REMOTE`
- exact `run_id + head_sha`
- `job_id` when available
- bounded `log_cursor`/step cursor when available
- `next_action = poll same locked run`

The remote runner itself must continue independently to terminal. Chat polling is observation, not the scheduler. A runtime cut must not create a new run merely to recover context.

On terminal success, transition out of `WAITING_REMOTE`; if acceptance/cleanup remains, use `RUNNING` with the next exact action. Only after required acceptance/invariant/cleanup gates are satisfied may the child acceptance checkpoint transition to `TERMINAL_SUCCESS`. Process closure then continues through the terminal `ClosureState` lifecycle; terminal acceptance never skips finalization proof, Issue close/readback, claim release, or successor handoff.

On terminal failure, use `RECOVERING` with the concrete evidence/root-cause action. Only a genuine irrecoverable/authoritative failure that ends the workflow may become `TERMINAL_FAILURE`.

## Behavior-test authority

`tests/process/test_continuity_controller.py` and `tests/process/test_finalization_owner_guard.py` are the primary machine guards. Together they must directly import and execute the controller and prove at least:

- non-terminal `next_action` fail-closed behavior;
- `WAITING_REMOTE` exact identity requirement;
- atomic save/load and runtime-cut resume preservation;
- version rejection;
- non-terminal finalization rejection;
- terminal-only state finalization;
- terminal transition lock;
- remote ownership/evidence preservation;
- missing or mismatched owning checkpoint rejection;
- missing guard-invocation proof rejection;
- stale proof rejection after checkpoint mutation;
- CLI authorization + verification path.

Documentation marker tests may remain, but they MUST NOT be treated as proof that runtime continuity or closure authorization is enforced.

## ASSISTANT_TURN_EXIT_GATE_V1

Workflow finalization 與 assistant turn exit 是兩個不同 machine gate。Canonical executable authority 仍是 `tools/continuity_controller.py`：

```python
from tools.continuity_controller import load_checkpoint, assert_turn_exitable

checkpoint = load_checkpoint(path)
assert_turn_exitable(
    checkpoint,
    expected_master_issue=expected_master_issue,
    claim_state=fresh_claim,
    transaction_state=fresh_guard_transaction,
)
```

CLI：

```bash
python -m tools.continuity_controller assert-turn-exitable path/to/checkpoint.json
```

Turn-exit state contract：

- `RUNNING`：**拒絕 turn exit**；立即執行 `next_action`。
- `WAITING_REMOTE`：**拒絕 turn exit**；維持 exact run/head lock 並 poll。
- `RECOVERING`：**拒絕 turn exit**；沿 evidence → root cause → fix → retry。
- `BLOCKED`：允許結束目前 turn，因為它代表真正需要外部 authority/capability；但它仍是 non-terminal，state-only `assert_finalizable` 與 owned finalization guard 都必須失敗。
- `TERMINAL_SUCCESS / TERMINAL_FAILURE`：允許 turn exit；workflow/issue 是否可真正 closure 仍要求 owned finalization guard + current proof + owning closure gate。

`assert_turn_exitable` 與 finalization authorization 不得互相取代。前者回答「目前 assistant response 能不能停」，後者回答「workflow/issue 能不能被宣告 terminal／執行 closure」。

### Remote-terminal → closing handoff

Remote run terminal 只解除 `REMOTE_QA_ACTIVE_LOCK`。只要 counts、invariant、cleanup、tested→closing drift、AI writeback 或 issue/Master closure 尚有工作，checkpoint 必須轉成 `RUNNING(next_acceptance_action)`；此時 `ASSISTANT_TURN_EXIT_GATE_V1` 立即接手，禁止在「QA PASS／code integrated／process incomplete」等進度回報後結束 turn。

`tests/process/test_continuity_controller.py` 是 turn-exit machine behavior authority；它必須保留 `WAITING_REMOTE → RUNNING(cleanup)` 後 turn exit 被拒絕的 regression。`tests/process/test_issue286_turn_exit_bridge_contract.py` 只保護各入口 Skill/踩坑 bridge 不漂移，不能取代 behavior test。

## ASSISTANT_TURN_EXIT_HARD_GATE_V2

V1 的 state guard 不足以證明「這次 turn 真的跑過 guard」。V2 把 owning checkpoint 與 actual guard invocation 都變成必要條件。

### Valid owning checkpoint

Turn-exit boundary 不得只接受「有 checkpoint」或「JSON 可讀」。它必須驗證 active execution context 的 exact owner：

- `issue`
- `branch`
- `head_sha`

缺檔、壞檔、owner 不符、stale branch/head 都視為 **missing / unreadable checkpoint** 的同一 fail-closed 類別；foreign/stale checkpoint 絕不是可退出授權。

### Actual guard invocation

Canonical path boundary `assert_turn_exitable_path(...)` 必須在載入與 ownership 驗證後，**實際呼叫** canonical `assert_turn_exitable(checkpoint, expected_master_issue=..., claim_state=..., transaction_state=...)`，並傳入當輪 fresh machine context。禁止：

- 只讀 state 後自行複製判斷；
- 只看到 checkpoint valid 就放行；
- 只靠文件 marker 或聊天文字宣稱 guard 已執行。

成功 guard invocation 必須產生 machine-verifiable **guard invocation proof**，綁定 owning identity 與該次 checkpoint 內容 digest。外層 boundary 再以 `assert_turn_exit_permitted(...)` 驗證 proof。

以下任何一項都必須 fail closed：

```text
NO_VALID_OWNING_CHECKPOINT
NO_ACTUAL_GUARD_INVOCATION
NO_CURRENT_GUARD_INVOCATION_PROOF
STALE_OR_OWNER_MISMATCHED_PROOF
```

checkpoint 在 guard 後只要被改寫，先前 proof 立即失效。`BLOCKED` 或 terminal state 也不能因 state 本身而繞過 owning-checkpoint / proof gate。

### Required behavior tests

`tests/process/test_issue321_turn_exit_enforcement.py` 必須至少證明：

- missing / malformed checkpoint fail closed；
- valid JSON 但 non-owning checkpoint fail closed；
- `RUNNING` 不 mint proof；
- path boundary 確實呼叫 canonical `assert_turn_exitable`；
- valid owning checkpoint 但沒有 guard invocation proof 仍 fail closed；
- successful guard invocation 產生 bound proof；
- checkpoint 改寫後 proof stale 並 fail closed。

## MASTER_CHAIN_TURN_EXIT_HARD_GATE_V1

Checkpoint 的 `TERMINAL_SUCCESS / TERMINAL_FAILURE` 只描述**目前 child**。若 child 屬於仍未完成的 Master/work-order chain，還必須攜帶 structured continuation：

`master_issue + chain_state + next_issue + chain_next_action/chain_reason`

Canonical `ChainContinuationState`：

- `NEXT_CHILD_EXECUTABLE`：`assert_turn_exitable` 必須拒絕；`scheduled_resume_action` 回 `EXECUTE_NEXT_ACTION`；CLI `resume` 回 `chain_next_action`。
- `NEXT_CHILD_BLOCKED`：僅 genuine external authority/capability wait；必須有 `chain_reason`。
- `CHAIN_COMPLETE`：Master chain 已真正完成，child terminal 才可作 turn-exit terminal。
- `USER_STOPPED`：使用者明確停止／取消 chain，必須有 `chain_reason`。

當外層 execution context fresh 知道 Master identity，必須以 `expected_master_issue` 呼叫 turn-exit guard。checkpoint 缺 `master_issue`、Master 不符、或 handoff metadata 不完整時 **fail closed**；不得因 child 本身 terminal 而 mint turn-exit proof。

Primary machine regression：`tests/process/test_issue473_master_chain_turn_exit_gate.py`。這個 gate 專門防止「#467 已關 → #468 可做，但 assistant 把 child terminal 當 Master terminal 而停工」類事故。

## SCHEDULED_STALE_CLAIM_TAKEOVER_V1

<!-- SCHEDULED_STALE_CLAIM_TAKEOVER_V1 -->

scheduled re-entry 遇到 foreign/manual/chat active claim 時，不得把「claim 未 RELEASE」當成永久 no-op authority，也不得自行用 prompt 猜 stale。

Canonical executable authority：`tools/stale_claim_takeover.py`。

固定流程：

```text
fresh claim/blob + live branch HEAD/commit time + exact remote run
→ same lane: direct durable resume（不 takeover）
→ foreign scheduler: fresh owner-authored runtime liveness lease
→ RUN_LIVE / valid lease = wait
→ missing/expired lease + >=90s grace = ORPHANED_SCHEDULER_OWNER actionable
→ ordinary foreign owner >=600s, no active run = EXECUTOR_STUCK actionable
→ Remote Guard action=claim-takeover
→ exact GREEN receipt
→ CAS shared claim to executor_source=scheduler + stale_takeover evidence
→ continue stored/recomputed exact next_action
```

這個 **600 秒 claim-owner stale threshold** 仍保留給一般 foreign owner；foreign scheduler 另有 runtime-liveness orphan path，canonical grace 為 90 秒。兩者都不能繞過 active exact run：只要 exact remote run 還 active，就先服從 `RUN_LIVE`。scheduler lane 是 durable owner key，不等於上一輪 invocation 還活著；same-lane 新 invocation直接 resume，foreign sibling則以 owner-authored短效 lease判斷 runtime liveness。

Machine behavior authority：`tests/process/test_issue540_stale_claim_takeover.py`。9m59s 必須 wait，10m00s 才可 `EXECUTOR_STUCK`；active exact run 永遠先阻擋 takeover。

## CHATGPT_SCHEDULED_REENTRY_V1

WHD 的 primary autonomous resume executor 是 **ChatGPT scheduled re-entry**。Hourly ChatGPT Automation 只負責重新喚醒新的 ChatGPT Runtime；被喚醒後仍必須回到本 Skill 與 `tools/continuity_controller.py` 的 canonical durable state。

固定流程：

```text
ChatGPT Automation wake
→ fresh GitHub issue / branch / HEAD / run_id readback
→ shared GitHub TTL lease
→ canonical checkpoint load
→ exact state routing / next_action
```

硬規則：

- ChatGPT Automation 是 primary wake/executor；GitHub Actions `schedule:` 僅可作 watchdog / lease / remote-state safety net，不能拿第三方 agent 的執行當成「ChatGPT 已續跑」證據。
- 每次 scheduled re-entry 都是 fresh runtime；不得用聊天記憶補 owner。必須 fresh-read issue / branch / HEAD / run_id / checkpoint。
- scheduled/manual actor 共用同一個 GitHub-backed TTL lease。有效 lease 存在時另一 actor 必須 safe no-op；過期才能重新取得。
- `RUNNING → execute exact next_action`；`WAITING_REMOTE → 保持 exact run_id + head_sha lock`；`RECOVERING → evidence → root cause → minimal fix → validation → retry`。
- scheduler 對 `WAITING_REMOTE` 使用小時級 stale 判斷；canonical default 為 2 小時。這與 active Runtime 內約 30 秒 polling 不同。
- `BLOCKED` durable metadata 使用 `blocked_count` 與 notification backoff；canonical default 為第 3 次才通知、之後至少 6 小時再提醒。離開 BLOCKED 時 metadata 歸零。
- Terminal checkpoint 進 issue-closure-gate handoff，不是永久 NO_OP；完成 cleanup/closure 後才移除 scheduled-resume eligibility。
- 目前 Runtime 還可執行時，**已有下一次排程絕不是停工理由**。Schedule 只保證 hard-cut 後重入，不節流 live Runtime。
- 使用者不是 scheduler；不得要求使用者再輸入「繼續／輪／GO」來推進已知 next action。

## SCHEDULED_RESUME_PROGRESS_HEARTBEAT

Scheduled Resume 的 **heartbeat 是 user-visible visibility projection，不是第二套 state machine**。Durable execution state 仍只由本 Skill + `tools/continuity_controller.py` 的 canonical checkpoint 決定；heartbeat 不得自行創造、改寫或取代 `RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED / TERMINAL_*`。

每次 ChatGPT scheduled re-entry 結束前，只要偵測到 **active work**，就**不得靜默**。必須主動送出一則精簡 heartbeat，第一行固定投影為下列其中一種：

- `WORKING`：canonical `RUNNING`，正常工作中。
- `WAITING_REMOTE`：已有 exact locked remote run，正常等待既有 RUN。
- `RECOVERING`：正在 evidence → root cause → minimal fix → validation → retry。
- `BLOCKED`：genuine blocker，依 durable blocked_count/backoff 管理。
- `COMPLETE`：只有 evidence-backed terminal + applicable closure/cleanup 完成後才可使用。

Heartbeat 至少包含：
- owning issue / work order；
- branch；
- HEAD（可短 SHA）；
- `run_id`（若有）；
- durable exact `next_action`；
- 一句人類可判讀結論：`正常工作中`、`正常等待既有 RUN`、`正在復原`、`真 blocker`、`已完成`。

特殊情境：
- 另一個 scheduled/manual runtime 持有有效 shared GitHub TTL lease：本 runtime safe no-op，但仍回報 `WORKING — 另一 runtime 持有有效 lease`，避免使用者把健康 mutual exclusion 誤判成卡死。
- `WAITING_REMOTE`：heartbeat 必須帶 exact `run_id + head_sha` 與目前 step/status；長時間無 step/updated_at 變化時標示 `疑似卡住`，並依 canonical stale policy 進 recovery，不能只沉默。
- 完全沒有 active work：允許保持安靜，不製造空洞狀態訊息。

Heartbeat 是 observation，不是 turn boundary。只要目前 Runtime 仍可自主執行 next action，送出 heartbeat 後仍必須繼續；不得因「已回報進度」停止。Live Runtime 的 remote QA 約 30 秒回報 cadence 仍由 `monitoring-remote-qa` 負責，scheduled heartbeat 不節流也不取代該 loop。

## IMMEDIATE_TERMINAL_PROGRESS_REPORT

一旦取得 **evidence-backed** 的 terminal PASS / FAIL / COMPLETE 事實，必須**立即回報**使用者，不得先埋頭做 secondary readback、cleanup、額外 evidence collection 或其他非必要核對，讓已經有終態證據的工作看起來像卡住。

規則：
- 只有已被 live source 證實的 terminal evidence 才能觸發；不得猜測或提前宣告成功／失敗。
- terminal evidence 一出現，先送出簡短 user-visible observation，至少包含 owning issue、branch/HEAD、run_id（若有）、terminal status/conclusion 與目前 next action。
- 若 terminal 後仍有 cleanup / invariant / writeback / closure，回報後必須**繼續**執行；immediate report != exit。
- 若 terminal failure 可修復，先立即回報 exact failure，再轉 RECOVERING 繼續 evidence → root cause → minimal fix → validation → retry。
- 若 terminal success 仍有 acceptance 收尾，先立即回報 PASS，再轉 RUNNING(next_acceptance_action)；不得把 PASS 當 COMPLETE。
- 本規則只管可見性優先序，不改 checkpoint state machine、finalization gate 或 closure authority。

## POLLING_OBSERVATION_ONLY

**輪詢只能看進度，不能產生進度。** Polling is observation-only; it is never a progress producer.

WAITING_REMOTE 只有在存在一個可獨立於目前 ChatGPT Runtime 持續推進工作的 **real progress producer** 時才合法，例如 exact GitHub Actions run、已提交且仍執行中的 remote job、或其他已具體啟動的 executor。

硬規則：
- concrete external progress producer 存在且 active：可以 WAITING_REMOTE，鎖 exact run_id + head_sha 並輪詢。
- no executor / no active run / no producer：不得維持 WAITING_REMOTE。立即回 RUNNING 或 RECOVERING，執行會真正產生下一個 state change 的 prerequisite / trigger / implementation / repair。
- RUN_NOT_CREATED 代表要去建立/修正 run producer，不是等。
- exact run terminal 立即離開 WAITING_REMOTE；輪詢 terminal 狀態本身不會產生下一步。
- status-only loop、反覆 refresh 同一靜止狀態、等待使用者再輸入「輪／繼續」都屬 continuity regression。
- 使用者不是 scheduler，也不是 progress producer。

## TRUSTED_REMOTE_FINALIZATION_EXECUTOR_V1

`OWNING_FINALIZATION_GUARD_V2` 的 remote execution 唯一允許窄路徑：`.github/workflows/whd-remote-finalization.yml`。它必須 checkout exact trusted authority，fresh 驗 owning work HEAD 與 coordination checkpoint/claim blob，執行 canonical `tools/continuity_controller.py authorize-finalization`，立即執行 `verify-finalization-proof`，並上傳 bound proof + `WHD_REMOTE_FINALIZATION_RECEIPT_V1` artifact。

只有 machine receipt `result=GREEN / reason=FINALIZATION_PROOF_VALID` 且 artifact identity exact match，才可把 proof帶到不可逆 closure boundary。Issue marker、stdout 摘錄、聊天聲明、人工計算 fingerprint 全部不是 proof execution authority。


## SCHEDULER_INVOCATION_LIVENESS_LEASE_V1

Scheduled wake每一輪都是 fresh AI execution runtime；`scheduler.<lane>`只表示 durable lane owner。當該 invocation實際持有 active claim時，必須建立/刷新 owner-authored `WHD_SCHEDULER_RUNTIME_LIVENESS_V1` short lease，綁 exact issue、lane、invocation identity、claim blob、branch、HEAD與可選 active run。

- canonical lease TTL <=300秒；orphan grace=90秒。
- same-lane cross-cycle resume忽略上一 invocation lease是否過期，直接讀 durable next_action。
- foreign sibling + valid lease：backoff；foreign sibling + active exact run：絕對 backoff。
- foreign sibling + no active run + missing/expired lease + grace satisfied：交給 `tools/stale_claim_takeover.py`分類 `ORPHANED_SCHEDULER_OWNER`，仍須 Remote Guard GREEN → single-use CAS → same-invocation first substantive action。
- platform runtime hard-cut時不得留下長達600秒的假 liveness；停止刷新即可讓 lease自然失效。

<!-- ISSUE646_MACHINE_ALIGNMENT_V1 -->
## ISSUE646_MACHINE_ALIGNMENT_V1

Turn-exit 必須帶 fresh durable context：expected_master_issue（屬 Master 時）、fresh claim_state、fresh Guard transaction_state。PENDING / MUTATION_DONE_RECONCILE_ONLY / EXPIRED_UNCONSUMED / AMBIGUOUS 都必須 fail closed；expired receipt 永久不可 consume，只能 fresh reconcile 後 mint fresh recovery Guard；durable mutation 已發生時只允許 reconciliation-only。

Equivalent duplicate GREEN 只有 mutation-relevant identity 完全一致才 dedupe；canonical representative 取最早 issued_at、同時取最小 run_id；shadow receipt 不得獨立 consume，任何 identity mismatch 仍 AMBIGUOUS → FAIL_CLOSED。

### #641 checkpoint fingerprint normalization
禁止 raw checkpoint JSON hash。只允許 load_checkpoint(path) → checkpoint_fingerprint(checkpoint)，或 authorize-finalization。#641 run 36051135751 因 raw JSON fingerprint 與 canonical normalization 不同而 FAIL；run 36051265277 使用 canonical fingerprint 後 GREEN；next_issue integer 642 會 normalize 成 string "642"。

### INTERACTIVE_RUNTIME_LIVENESS_AND_PROVENANCE_REQUIREMENT_V1
這是 required governance follow-up，不得假稱 machine 已完成：chatgpt_interactive active owner 必須補可機讀 heartbeat/liveness；durable provenance 必須辨識 interactive 的 specific conversation/chat identity + invocation identity，以及 scheduler 的 scheduler_lane + invocation_identity。generic executor_source 只能表示類型，不能取代 exact provenance；heartbeat 也不能取代 claim/checkpoint/Guard authority。
