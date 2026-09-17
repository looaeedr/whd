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

On every scheduled wake-up, the first action is to restore the owning issue/checkpoint/branch/current concrete RUN identity and verify it live. Then continue the owning plan rather than producing a status-only response.

- Concrete RUN exists: lock its exact `run_id + head_sha`, poll it to terminal, read jobs/logs/evidence, then execute the next autonomous step. `terminal => continue next autonomous step`.
- No concrete RUN exists when the owning plan requires one: classify `RUN_NOT_CREATED`. Do not wait or poll. Immediately identify and execute/fix the prerequisite or trigger that should create the RUN.
- GREEN is not an exit reason: advance to the next unfinished gate/slice.
- RED is not an exit reason: inspect exact failure evidence, classify it, perform the smallest valid TDD repair, and revalidate.
- A progress/status report is observation only: `status update != exit`.
- Schedule cadence is wake-up cadence, not execution cadence. Once awake, continue execution/polling inside the available turn; do not deliberately end each step merely because another scheduled wake-up exists.
- Only a genuine external-authority/capability blocker may stop autonomous progress.
- If the platform/tool forces the turn to end, persist `checkpoint before forced turn end`: owning issue, branch, HEAD, RUN identity/status, last accepted gate, next exact action, and prohibitions. The next wake-up resumes from that checkpoint.
- Project-specific automation prompts must reference this contract and may add owner/scope/prohibition data, but must not define a second continuity authority.

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

The command MUST fail closed when owning checkpoint is missing/malformed/non-terminal, expected owner identity is missing/mismatched, or any state-only finalization condition fails. A successful call emits `FINALIZATION_GUARD_PASS` and an atomic proof bound to the exact checkpoint fingerprint. Immediately before actual closure, verify that proof; any owner/checkpoint mutation invalidates it.

Bare `assert_finalizable(checkpoint)` must never be cited as proof that issue closure or workflow finalization was actually authorized.

## Resume gate

For a persisted non-terminal checkpoint:

```bash
python -m tools.continuity_controller resume path/to/checkpoint.json
```

The returned action is the exact durable next action. `WAITING_REMOTE` delegates polling mechanics and cadence to `monitoring-remote-qa`; this controller owns durable state integrity and finalization enforcement.

## Remote QA bridge

When remote QA is submitted, persist `WAITING_REMOTE` with exact `run_id + head_sha`, optional `job_id/log_cursor/evidence`, and `next_action = poll same locked run`. On terminal success, if acceptance/cleanup remains, transition to `RUNNING` with the next exact action. On terminal failure, use `RECOVERING` with concrete evidence/root-cause action.

## ASSISTANT_TURN_EXIT_GATE_V1

`RUNNING`, `WAITING_REMOTE`, and `RECOVERING` reject turn exit. `BLOCKED` may end the current turn but remains non-terminal and non-finalizable. Terminal states may exit; workflow/issue closure still requires the owned finalization proof.

Remote run terminal only releases the remote QA lock. If counts, invariants, cleanup, tested-to-closing drift, AI writeback, or closure remain, transition to `RUNNING(next_acceptance_action)` and continue.

## ASSISTANT_TURN_EXIT_HARD_GATE_V2

Turn exit requires a valid owning checkpoint (`issue + branch + head_sha`) and actual invocation of canonical `assert_turn_exitable(checkpoint)` with a current bound guard-invocation proof. Fail closed on `NO_VALID_OWNING_CHECKPOINT`, `NO_ACTUAL_GUARD_INVOCATION`, `NO_CURRENT_GUARD_INVOCATION_PROOF`, or `STALE_OR_OWNER_MISMATCHED_PROOF`. Checkpoint mutation invalidates old proof.

## Behavior-test authority

`tests/process/test_continuity_controller.py`, `tests/process/test_finalization_owner_guard.py`, `tests/process/test_issue321_turn_exit_enforcement.py`, and scheduled-wakeup contract regressions are machine/documentation guards for their respective scopes. Marker tests do not replace runtime behavior enforcement.
