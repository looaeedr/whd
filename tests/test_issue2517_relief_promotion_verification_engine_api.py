"""#2517 Relief promotion eligibility is the original public Engine decision."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import certified_relief_registry as owner
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
from gui_modules.application.fold_designer_composition_assembly_corner import (
    create_relief_promotion_candidates,
)


def _solution(*, verified=True, trust_level="PROVISIONAL_3D"):
    return SimpleNamespace(
        verified=verified, trust_level=trust_level, corner_reliefs=(),
    )


def _candidate(solution):
    return api.build_relief_promotion_candidate(
        solution, cabinet_family="金庫型", part_role="head",
        joint_face="TOP", assembly_intent="INSERT", source_signature={"t": 2.0},
    )


def _controller(solutions):
    registry = Phase6RegistryDiagnosticsController()
    prior = deepcopy(solutions)
    manifests = registry.build_promotion_candidates(
        solutions=solutions, snapshot={"t": 2.0},
        assembly_intent="INSERT", cabinet_family="金庫型",
        builder=api.build_relief_promotion_candidate,
    )
    assert solutions == prior
    return registry, manifests


def test_root_and_public_facade_share_exact_engine_registry_owner():
    assert api.operator_relief_promotion_candidate_eligible is (
        owner.operator_relief_promotion_candidate_eligible
    )
    assert ae_engine.operator_relief_promotion_candidate_eligible is (
        owner.operator_relief_promotion_candidate_eligible
    )
    assert "operator_relief_promotion_candidate_eligible" in ae_engine.__all__


def test_real_provisional_verified_source_builds_detached_manifest_without_registry_write():
    head = _solution()
    tail = _solution(verified=False)
    source = {"head": head, "tail": tail}
    registry, manifests = _controller(source)
    assert set(manifests) == {"head"}
    assert manifests["head"]["status"] == "PROMOTION_CANDIDATE"
    assert manifests["head"]["mutates_registry"] is False
    assert manifests["head"]["part_role"] == "head"
    assert registry.promotion_candidates == manifests
    assert api.operator_relief_promotion_candidate_eligible(head) is True
    assert api.operator_relief_promotion_candidate_eligible(tail) is False
    assert json.loads(json.dumps({"verified": head.verified})) == {"verified": True}


@pytest.mark.parametrize("verified", [
    "false", "true", "0", "1", 0, 1, 1.0, 0.0,
    None, [], {},
])
def test_corrupted_solver_verified_cannot_build_candidate_or_change_gui_state(verified):
    registry = Phase6RegistryDiagnosticsController()
    accepted = registry.build_promotion_candidates(
        solutions={"head": _solution()}, snapshot={},
        assembly_intent="INSERT", cabinet_family="金庫型",
        builder=api.build_relief_promotion_candidate,
    )
    prior = registry.promotion_candidates
    source = _solution(verified=verified)
    with pytest.raises(ValueError, match="RELIEF_PROMOTION_VERIFIED_BOOLEAN_REQUIRED"):
        api.operator_relief_promotion_candidate_eligible(source)
    with pytest.raises(ValueError, match="RELIEF_PROMOTION_VERIFIED_BOOLEAN_REQUIRED"):
        _candidate(source)
    with pytest.raises(ValueError, match="RELIEF_PROMOTION_VERIFIED_BOOLEAN_REQUIRED"):
        registry.build_promotion_candidates(
            solutions={"head": source}, snapshot={}, assembly_intent="INSERT",
            cabinet_family="金庫型", builder=api.build_relief_promotion_candidate,
        )
    assert registry.promotion_candidates == prior == accepted


@pytest.mark.parametrize("trust", ["CERTIFIED", "UNVERIFIED", "", None])
def test_verified_but_not_provisional_is_not_a_promotion_candidate(trust):
    source = _solution(trust_level=trust)
    assert api.operator_relief_promotion_candidate_eligible(source) is False
    assert _controller({"head": source})[1] == {}
    with pytest.raises(ValueError, match="只有 PROVISIONAL_3D"):
        _candidate(source)


def test_missing_and_unverified_proof_do_not_enter_gui_candidate_list():
    assert api.operator_relief_promotion_candidate_eligible(None) is False
    assert api.operator_relief_promotion_candidate_eligible(_solution(verified=False)) is False
    assert _controller({"head": _solution(verified=False)})[1] == {}
    with pytest.raises(ValueError, match="未通過 3D 驗證"):
        _candidate(_solution(verified=False))


def test_gui_promotion_uses_engine_source_gate_not_local_verification_rules():
    body = inspect.getsource(Phase6RegistryDiagnosticsController.build_promotion_candidates)
    assert "manufacturing_api.operator_relief_promotion_candidate_eligible(" in body
    assert 'bool(getattr(solution, "verified"' not in body
    assert '!= "PROVISIONAL_3D"' not in body
    request = inspect.getsource(create_relief_promotion_candidates)
    assert "manufacturing_api.build_relief_promotion_candidate" in request
