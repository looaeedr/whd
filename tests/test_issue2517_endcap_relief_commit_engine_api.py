"""#2517: verified or certified Head/Tail relief commit belongs to Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    manufacturing_api, endcap_relief_solution_committable,
    endcap_relief_transaction_committable,
)
from phase6_manufacturing_geometry import _phase6_solution_is_committable as legacy


@pytest.mark.parametrize("verified,rule_id,trust,allowed", [
    (True, None, "", True),
    (True, None, "UNKNOWN", True),
    (False, "certified-rule", "CERTIFIED", True),
    (False, "certified-rule", "CERTIFIED_FROM_3D", True),
    (False, "certified-rule", "ENGINE_CONFLICT", True),
    (False, None, "CERTIFIED", False),
    (False, "", "ENGINE_CONFLICT", False),
    (False, "not-certified", "UNKNOWN", False),
    (False, "not-certified", "UNVERIFIED", False),
    (False, None, "", False),
])
def test_engine_commit_predicate_preserves_verified_and_certified_truth_table(
    verified, rule_id, trust, allowed,
):
    solution = SimpleNamespace(verified=verified, rule_id=rule_id, trust_level=trust)
    assert endcap_relief_solution_committable(solution) is allowed
    assert legacy(solution) is allowed


def test_public_engine_owner_and_phase6_compatibility_only_delegates():
    assert manufacturing_api.endcap_relief_solution_committable is endcap_relief_solution_committable
    source = inspect.getsource(legacy)
    assert "manufacturing_api.endcap_relief_solution_committable(solution)" in source
    assert "rule_id" not in source
    assert "trust_level" not in source
    assert "verified" not in source


def test_actual_solved_endcap_verified_solution_uses_same_public_policy():
    from ae_engine.corner_type_ui import BOX_ASSEMBLY_TYPE_IDS
    from tests.test_phase6_assembly_intent_registry_matrix import _case

    _endcap, solution = _case(BOX_ASSEMBLY_TYPE_IDS[0], "head")
    assert solution.verified is True
    assert endcap_relief_solution_committable(solution) is True
    assert legacy(solution) is True


@pytest.mark.parametrize("required,solution_flags,expected", [
    (("head", "tail"), {"head": True, "tail": True}, True),
    (("head",), {"head": True}, True),
    (("head", "tail"), {"head": True}, False),
    (("head", "tail"), {"head": True, "tail": False}, False),
    (("head",), {"tail": True}, False),
    ((), {}, False),
])
def test_engine_atomic_endcap_transaction_fails_closed(
    required, solution_flags, expected,
):
    solutions = {
        key: SimpleNamespace(verified=value, rule_id=None, trust_level="")
        for key, value in solution_flags.items()
    }
    assert manufacturing_api.endcap_relief_transaction_committable(
        required, solutions,
    ) is expected


def test_engine_atomic_transaction_preserves_certified_conflict_authority():
    head = SimpleNamespace(
        verified=False, rule_id="certified-head", trust_level="ENGINE_CONFLICT",
    )
    tail = SimpleNamespace(
        verified=True, rule_id=None, trust_level="",
    )
    assert manufacturing_api.endcap_relief_transaction_committable(
        ("head", "tail"), {"head": head, "tail": tail},
    ) is True
    tail.trust_level = "UNVERIFIED"
    tail.verified = False
    assert manufacturing_api.endcap_relief_transaction_committable(
        ("head", "tail"), {"head": head, "tail": tail},
    ) is False


def test_phase6_atomic_commit_does_not_repeat_engine_policy():
    import phase6_manufacturing_service as service

    assert callable(manufacturing_api.endcap_relief_transaction_committable)
    assert (
        manufacturing_api.endcap_relief_transaction_committable
        is endcap_relief_transaction_committable
    )
    source = inspect.getsource(service.resolve)
    assert "endcap_relief_transaction_committable(" in source
    assert "atomic_committable = all(" not in source
