---
name: executable-continuity-controller
description: Use for long-running WHD execution, remote QA, recovery, checkpoint persistence, resume after runtime cuts, and any workflow finalization decision that must be enforced by executable state rather than prose alone.
---

# Executable Continuity Controller

## EXECUTABLE_CONTINUITY_CONTROLLER_V1

Canonical executable authority: `tools/continuity_controller.py`.

This Skill does not replace domain Skills. It provides the machine-enforced continuity layer that `執行開發任務`, `monitoring-remote-qa`, and closure/finalization gates must delegate to.

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
