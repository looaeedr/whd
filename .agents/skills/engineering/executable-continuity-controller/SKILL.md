---
name: executable-continuity-controller
description: Use for long-running WHD execution, remote QA, recovery, checkpoint persistence, resume after runtime cuts, and any workflow finalization decision that must be enforced by executable state rather than prose alone.
whd_doc_role: CURRENT
whd_contract: continuous-execution-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Executable Continuity Controller

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

On terminal success, transition out of `WAITING_REMOTE`; if acceptance/cleanup remains, use `RUNNING` with the next exact action. Only after all required acceptance/invariant/cleanup/closure gates are satisfied may the workflow transition to `TERMINAL_SUCCESS` and pass the owned finalization authorization flow above.

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
assert_turn_exitable(checkpoint)
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

Canonical path boundary `assert_turn_exitable_path(...)` 必須在載入與 ownership 驗證後，**實際呼叫** canonical `assert_turn_exitable(checkpoint)`。禁止：

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

