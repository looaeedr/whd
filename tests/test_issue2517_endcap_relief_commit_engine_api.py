"""#2517: verified or certified Head/Tail relief commit belongs to Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, endcap_relief_solution_committable
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
