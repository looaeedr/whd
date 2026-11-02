"""#2517: Registry candidate 3D shadow solution must be Engine-owned."""
from __future__ import annotations

import inspect
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
import ae_engine.operator_relief_candidate_3d as owner


def _parts():
    def part():
        return SimpleNamespace(material=object())
    return {
        "box_body": (part(), ({"phase6_key": "body", "len": 20.0},), ()),
        "head": (part(), ({"phase6_key": "head", "len": 10.0},), ()),
        "tail": (part(), ({"phase6_key": "tail", "len": 10.0},), ()),
    }


def _call(parts=None, **changes):
    kwargs = dict(
        candidate_id="candidate-proof",
        assembly_intent="INSERT",
        part_inputs=_parts() if parts is None else parts,
        finished_dimensions={"w": 800, "h": 1200, "d": 350},
        sheet_thickness=2.0,
        clearance=0.0,
        box_body_structure_state={"structure_type": "integral"},
        cabinet_family="金庫型",
    )
    kwargs.update(changes)
    return api.validate_operator_relief_registry_candidate_3d(
        {"rule_id": "candidate-proof"}, **kwargs
    )


def test_public_api_invokes_registry_evaluator_and_world_solver_without_writes(monkeypatch):
    monkeypatch.setattr(owner, "_validate_editable_rule_record", lambda _: {
        "rule_id": "candidate-proof", "assembly_intent": "INSERT",
    })
    evaluations, solves = [], []
    ephemeral = object()

    def evaluate(raw, **kwargs):
        evaluations.append((raw, kwargs))
        return ephemeral

    def solve(**kwargs):
        solves.append(kwargs)
        verified = len(solves) == 1
        return SimpleNamespace(
            verified=verified, trust_level="CERTIFIED",
            rule_id="candidate-proof", rule_revision=0,
            residual_projection=SimpleNamespace(pair_count=0 if verified else 1),
        )

    monkeypatch.setattr(owner, "evaluate_editable_endcap_rule_record", evaluate)
    monkeypatch.setattr(owner, "solve_world_backprojected_endcap_relief", solve)
    parts = _parts()
    before = deepcopy({k: (v[1], v[2]) for k, v in parts.items()})
    result = _call(parts)
    assert result["candidate_specific"] is True
    assert result["candidate_id"] == "candidate-proof"
    assert result["validated_parts"] == ["head", "tail"]
    assert result["zero_penetration"] is False
    assert result["solutions"]["head"]["verified"] is True
    assert result["solutions"]["tail"]["residual_pair_count"] == 1
    assert [x["endcap_placement"] for x in solves] == [
        owner.SCENE_ASSEMBLY_PLACEMENTS["head"],
        owner.SCENE_ASSEMBLY_PLACEMENTS["tail"],
    ]
    assert all(x["allow_3d_fallback"] is False for x in solves)
    assert all(x["certified_result_override"] is ephemeral for x in solves)
    assert all(x["cabinet_family"] == "金庫型" for x in solves)
    assert len(evaluations) == 2
    assert {k: (v[1], v[2]) for k, v in parts.items()} == before


def test_fail_closed_for_identity_intent_and_missing_physical_geometry(monkeypatch):
    monkeypatch.setattr(owner, "_validate_editable_rule_record", lambda _: {
        "assembly_intent": "INSERT",
    })
    with pytest.raises(ValueError, match="requires candidate_id"):
        _call(candidate_id=" ")
    with pytest.raises(ValueError, match="does not match"):
        _call(assembly_intent="OVERLAY")
    with pytest.raises(ValueError, match="requires box_body"):
        _call({})
    with pytest.raises(ValueError, match="unknown physical part"):
        _call({**_parts(), "fake": _parts()["head"]})
    broken = _parts()
    broken["head"] = (None, (), ())
    with pytest.raises(ValueError, match="render data unavailable"):
        _call(broken)


def test_no_applicable_formula_and_no_endcaps_never_claims_shadow_success(monkeypatch):
    monkeypatch.setattr(owner, "_validate_editable_rule_record", lambda _: {
        "assembly_intent": "INSERT",
    })
    monkeypatch.setattr(owner, "evaluate_editable_endcap_rule_record", lambda *a, **kw: None)
    with pytest.raises(ValueError, match="does not apply"):
        _call()
    body_only = {"box_body": _parts()["box_body"]}
    assert _call(body_only)["zero_penetration"] is False


def test_gui_only_forwards_operator_inputs_not_registry_solver():
    import fold_designer_bridge as bridge

    source = inspect.getsource(bridge._phase6_registry_validate_candidate_3d)
    assert "manufacturing_api.validate_operator_relief_registry_candidate_3d(" in source
    assert "solve_world_backprojected_endcap_relief(" not in source
    assert "evaluate_editable_endcap_rule_record(" not in source
    assert "from ae_engine.certified_relief_registry" not in source
    assert "from phase6_" not in inspect.getsource(owner)
