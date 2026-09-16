---
name: executable-continuity-controller
description: Use for long-running WHD execution, remote QA, recovery, checkpoint persistence, resume after runtime cuts, and any workflow finalization decision that must be enforced by executable state rather than prose alone.
whd_doc_role: CURRENT
whd_contract: continuous-execution-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Executable Continuity Controller

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

Workflow/issue/acceptance closure MUST call the executable finalization guard, not infer completion from prose markers.

Python:

```python
from tools.continuity_controller import load_checkpoint, assert_finalizable

checkpoint = load_checkpoint(path)
assert_finalizable(checkpoint)
```

CLI:

```bash
python -m tools.continuity_controller assert-finalizable path/to/checkpoint.json
```

Any non-terminal state MUST exit nonzero / raise `FinalizationBlocked`. Phrase matches such as `final 禁止`, `使用者不是 scheduler`, or `STALE_WAIT_WATCHDOG` remain documentation compatibility guards only; they are not executable enforcement.

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

On terminal success, transition out of `WAITING_REMOTE`; if acceptance/cleanup remains, use `RUNNING` with the next exact action. Only after all required acceptance/invariant/cleanup/closure gates are satisfied may the workflow transition to `TERMINAL_SUCCESS` and pass `assert-finalizable`.

On terminal failure, use `RECOVERING` with the concrete evidence/root-cause action. Only a genuine irrecoverable/authoritative failure that ends the workflow may become `TERMINAL_FAILURE`.

## Behavior-test authority

`tests/process/test_continuity_controller.py` is the primary machine guard. It must directly import and execute the controller and prove at least:

- non-terminal `next_action` fail-closed behavior;
- `WAITING_REMOTE` exact identity requirement;
- atomic save/load and runtime-cut resume preservation;
- version rejection;
- non-terminal finalization rejection;
- terminal-only finalization;
- terminal transition lock;
- remote ownership/evidence preservation.

Documentation marker tests may remain, but they MUST NOT be treated as proof that runtime continuity is enforced.

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
- `BLOCKED`：允許結束目前 turn，因為它代表真正需要外部 authority/capability；但它仍是 non-terminal，`assert_finalizable` 必須失敗。
- `TERMINAL_SUCCESS / TERMINAL_FAILURE`：允許 turn exit；是否可宣告 workflow 完成仍由 `assert_finalizable` 與 owning closure gate 判定。

`assert_turn_exitable` 與 `assert_finalizable` 不得互相取代。前者回答「目前 assistant response 能不能停」，後者回答「workflow/issue 能不能被宣告 terminal」。

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
