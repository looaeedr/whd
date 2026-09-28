"""Pure legacy-to-native bootstrap planning for WHD Flow v2.

The planner never writes durable state and never derives machine action kind or
arguments from legacy prose. Active legacy records need an explicit structured
action supplied by the migration caller. During shadow migration the human
``display`` text must remain equal to the legacy text; changing visible meaning
is a separate legacy reconciliation transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_record import (
    ActionSpec,
    ExecutionRecord,
    execution_record_fingerprint,
    execution_record_from_legacy,
)


@dataclass(frozen=True)
class BootstrapPlan:
    status: str
    reasons: tuple[str, ...]
    legacy_fingerprint: str
    candidate: ExecutionRecord | None


def _is_structured(action: ActionSpec | None) -> bool:
    if not isinstance(action, ActionSpec):
        return False
    try:
        validate_execution_action(action)
    except ActionContractError:
        return False
    return True


def plan_legacy_bootstrap(
    claim: Mapping[str, object],
    checkpoint: Mapping[str, object],
    *,
    structured_next_action: ActionSpec | None = None,
    structured_chain_next_action: ActionSpec | None = None,
) -> BootstrapPlan:
    """Plan a native V2 bootstrap without inferring semantics from prose."""
    legacy = execution_record_from_legacy(claim, checkpoint)
    legacy_fp = execution_record_fingerprint(legacy)
    reasons: list[str] = []

    next_action = legacy.next_action
    if legacy.state != "DONE":
        if not _is_structured(structured_next_action):
            reasons.append("active bootstrap requires explicit structured next_action mapping")
        elif next_action is None:
            reasons.append("active legacy record is missing next_action")
        elif structured_next_action.display != next_action.display:
            reasons.append(
                "structured next_action display differs from legacy display; "
                "legacy reconciliation required before shadow bootstrap"
            )

    legacy_chain_action = legacy.chain.next_action
    if legacy_chain_action is not None:
        if not _is_structured(structured_chain_next_action):
            reasons.append("chain bootstrap requires explicit structured chain next_action mapping")
        elif structured_chain_next_action.display != legacy_chain_action.display:
            reasons.append(
                "structured chain next_action display differs from legacy display; "
                "legacy reconciliation required before shadow bootstrap"
            )

    if reasons:
        if any("display differs" in reason for reason in reasons):
            status = "REQUIRES_LEGACY_RECONCILIATION"
        else:
            status = "REQUIRES_ACTION_MAPPING"
        return BootstrapPlan(
            status=status,
            reasons=tuple(reasons),
            legacy_fingerprint=legacy_fp,
            candidate=None,
        )

    if legacy.state == "DONE":
        candidate = legacy
    else:
        assert structured_next_action is not None
        chain = legacy.chain
        if legacy_chain_action is not None:
            assert structured_chain_next_action is not None
            chain = replace(chain, next_action=structured_chain_next_action)
        candidate = replace(
            legacy,
            next_action=structured_next_action,
            chain=chain,
        )

    return BootstrapPlan(
        status="CANDIDATE_READY",
        reasons=(),
        legacy_fingerprint=legacy_fp,
        candidate=candidate,
    )
