"""Headless-agent routing for Scheduled Resume Bridge.

This module does not execute Claude Code. It emits a bounded, exact-owner prompt
only for wake dispositions that require autonomous engineering work.
"""

from __future__ import annotations

from tools.continuity_controller import CheckpointError
from tools.execution_entry_contract import prepend_startup_declaration
from tools.scheduled_resume_runtime import (
    ScheduledWakeDisposition,
    ScheduledWakeEvaluation,
)


_AGENT_DISPOSITIONS = frozenset(
    {
        ScheduledWakeDisposition.EXECUTE_NEXT_ACTION,
        ScheduledWakeDisposition.CONTINUE_RECOVERY,
        ScheduledWakeDisposition.CLOSING_HANDOFF,
    }
)


def should_invoke_headless_agent(evaluation: ScheduledWakeEvaluation) -> bool:
    return evaluation.disposition in _AGENT_DISPOSITIONS


def build_headless_agent_prompt(evaluation: ScheduledWakeEvaluation) -> str:
    if not should_invoke_headless_agent(evaluation):
        raise CheckpointError(
            f"headless agent is not allowed for disposition {evaluation.disposition.value}"
        )

    checkpoint = evaluation.checkpoint
    run_id = "none" if checkpoint.run_id is None else str(checkpoint.run_id)

    if evaluation.disposition is ScheduledWakeDisposition.CLOSING_HANDOFF:
        action = (
            "Run the existing issue-closure-gate closing chain for this terminal "
            "checkpoint. Verify current proof/owner, required cleanup and durable "
            "writeback before closing anything; then remove scheduled-resume "
            "eligibility only after closure is complete."
        )
    else:
        action = evaluation.next_action or checkpoint.next_action
        if not action:
            raise CheckpointError("headless agent action must be nonblank")

    body = f"""WHD Scheduled Resume Bridge autonomous execution.

Exact durable owner:
- issue={checkpoint.issue}
- branch={checkpoint.branch}
- head_sha={checkpoint.head_sha}
- run_id={run_id}
- state={checkpoint.state.value}

Exact next action:
{action}

Execution contract:
1. fresh-read GitHub issue, branch, HEAD and any run_id before mutating.
2. If identity drifted, classify only the affected drift; do not replay accepted phases.
3. Follow repository Branch-First rules. Do not write directly to production unless the owning accepted closing/integration contract explicitly requires it.
4. Never force push.
5. Validation is judge-only; never feed expected/reference values back into production calculations.
6. Keep durable checkpoint/issue evidence current after each accepted boundary.
7. A PASS/FAIL/status update is not a stopping reason while a valid autonomous next action remains.
8. For remote QA, retain the exact run_id + head_sha lock; do not create a replacement run merely because this runtime restarted.
9. When the task is terminal, invoke issue-closure-gate and complete cleanup before removing scheduled-resume eligibility.
"""
    purpose = f"Scheduled Resume for Issue #{checkpoint.issue}: {action}"
    return prepend_startup_declaration(body=body, purpose=purpose)
