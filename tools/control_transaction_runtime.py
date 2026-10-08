"""Stateless DM8 plan/effect boundary; control_transaction owns all semantics."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from tools.control_transaction import (
    ControlTransactionConflict, ControlTransactionPlan, validate_exact_plan,
)
from tools.execution_record import ExecutionRecord

PRE_TRANSITION_EXTERNAL_MUTATION_PATHS = frozenset(
    {"MERGE", "SYNC_TARGET", "FINALIZE", "RELEASE_PATHS"}
)


class RuntimeMode(str, Enum):
    MUTATION_ALLOWED = "MUTATION_ALLOWED"
    READBACK_ONLY = "READBACK_ONLY"


class RuntimePathClass(str, Enum):
    READBACK_ONLY = "READBACK_ONLY"
    PRE_TRANSITION_EXTERNAL_MUTATION = "PRE_TRANSITION_EXTERNAL_MUTATION"


class RuntimeMutationFenceError(RuntimeError):
    """A classified provider mutation requires a capability absent in this mode."""


class RuntimePostEffectConflict(ControlTransactionConflict):
    """A resolved or uncertain provider outcome must never authorize replay."""
    retryable = False

    def __init__(self, conflict_class: str, diagnostics: Mapping[str, object]):
        self.conflict_class = conflict_class
        self.diagnostics = dict(diagnostics, authority="NON_AUTHORITY")
        super().__init__(f"{conflict_class}: current Issue changed or provider outcome requires readback/repair")


class RuntimeProviderError(RuntimeError):
    """The runtime provider could not resolve the requested transport operation."""


@dataclass(frozen=True)
class RuntimeEffectEnvelope:
    effect: Mapping[str, object]
    path_class: RuntimePathClass
    provider_mutation_performed: bool


class RuntimeProvider(Protocol):
    def read_state(self) -> tuple[str, str, dict[int, ExecutionRecord]]: ...

    def resolve_effect(
        self, record: ExecutionRecord, plan: ControlTransactionPlan,
        supplied_effect: Mapping[str, object], *,
        records: dict[int, ExecutionRecord],
        before_mutation: Callable[[str, str], None],
    ) -> dict[str, object]: ...


def resolve_runtime_effect(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    mode: RuntimeMode,
    provider: RuntimeProvider,
    supplied_effect: Mapping[str, object],
) -> RuntimeEffectEnvelope:
    """Validate fresh exact identity, then resolve one effect without transitioning.

    READBACK_ONLY still admits existing idempotent readback paths. The provider
    calls the capability fence only at an actual PUT/POST/PATCH/DELETE branch.
    Neither this function nor its envelope owns coord writes, retry or state.
    """
    validate_exact_plan(record, plan)
    if plan.kind not in PRE_TRANSITION_EXTERNAL_MUTATION_PATHS:
        raise RuntimeProviderError(f"transaction outside runtime effect scope: {plan.kind}")
    mode = RuntimeMode(mode)
    _, _, records = provider.read_state()
    fresh = records.get(plan.issue)
    if fresh is None:
        raise ControlTransactionConflict(f"native ExecutionRecord missing for issue {plan.issue}")
    validate_exact_plan(fresh, plan)
    mutation_performed = False

    def before_mutation(method: str, path: str) -> None:
        nonlocal mutation_performed
        if mode == RuntimeMode.READBACK_ONLY:
            raise RuntimeMutationFenceError(f"READBACK_ONLY blocked {method} {path}")
        mutation_performed = True

    try:
        effect = provider.resolve_effect(
            fresh, plan, supplied_effect, records=records,
            before_mutation=before_mutation,
        )
    except Exception as exc:
        if mutation_performed:
            raise RuntimePostEffectConflict("POST_EFFECT_PROVIDER_OUTCOME_UNPROVEN", {
                "issue": fresh.issue, "kind": plan.kind,
                "pre_generation": fresh.generation,
                "provider_mutation_may_have_occurred": True,
                "work_branch": fresh.work_branch, "work_head": fresh.head_sha,
                "target_branch": fresh.target_branch, "target_head": fresh.target_sha,
            }) from exc
        raise
    return RuntimeEffectEnvelope(
        effect=MappingProxyType(dict(effect)),
        path_class=(RuntimePathClass.PRE_TRANSITION_EXTERNAL_MUTATION
                    if mutation_performed else RuntimePathClass.READBACK_ONLY),
        provider_mutation_performed=mutation_performed,
    )


def production_provider(repo: str, token: str, coord_branch: str = "coord/execution-v2"):
    """Construct the production transport adapter without importing private helpers."""
    from tools.control_transaction_production_executor import build_runtime_provider
    return build_runtime_provider(repo, token, coord_branch)
