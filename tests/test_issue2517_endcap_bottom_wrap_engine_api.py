"""#2517: Head/Tail lower WRAP state and BOTTOM Joint are Engine-owned."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import (
    commit_endcap_bottom_wrap,
    commit_endcap_bottom_wrap_joint,
    normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap,
)
from ae_engine import manufacturing_api
from ae_engine import endcap_bottom_wrap_state as owner
from ae_engine.assembly_joint import (
    AssemblyJointRelation,
    edge_relation_for_part,
    migrate_legacy_snapshot_joints,
    set_part_edge_relation,
)
import phase6_endcap_semantics as gui


def test_public_api_canonical_owner_and_legacy_defaults():
    assert normalize_endcap_bottom_wrap_state is manufacturing_api.normalize_endcap_bottom_wrap_state
    assert normalize_endcap_bottom_wrap_state is owner.normalize_endcap_bottom_wrap_state
    assert commit_endcap_bottom_wrap is owner.commit_endcap_bottom_wrap
    source = {"model": "受電箱", "t": 2}
    actual = normalize_endcap_bottom_wrap_state(source)
    assert source == {"model": "受電箱", "t": 2}
    assert actual == gui.normalize_endcap_bottom_wrap_state(source)
    assert actual["mode"] == "LINKED"
    assert resolve_endcap_bottom_wrap(source, "tail", state=actual) == {
        "enabled": True, "reserve_u": 2.0, "reserve_v": 1.0,
    }
    assert resolve_endcap_bottom_wrap({"model": "金庫型"}, "head")["enabled"] is False


def test_operator_wrap_reserves_and_link_split_are_identical_across_old_and_new_client():
    state = normalize_endcap_bottom_wrap_state({"model": "受電箱"})
    assert commit_endcap_bottom_wrap(state, "head", reserve_u=3.5) is state
    assert state["mode"] == "FOLLOW_HEAD"
    assert gui.commit_endcap_bottom_wrap(state, "head", reserve_v=2.25) is state
    assert state["head"] == state["tail"]
    assert commit_endcap_bottom_wrap(state, "tail", reserve_u=4) is state
    assert state["mode"] == "INDEPENDENT"
    assert state["head"]["reserve_u"] == pytest.approx(3.5)
    assert state["tail"]["reserve_u"] == pytest.approx(4)


def test_actual_joint_graph_not_legacy_enabled_mirror_is_authority():
    snap = migrate_legacy_snapshot_joints({
        "assembly_type": "OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "endcap_bottom_wrap": {
            "mode": "INDEPENDENT",
            "head": {"enabled": True, "reserve_u": 7, "reserve_v": 1},
        },
    })
    snap = set_part_edge_relation(snap, "head", "BOTTOM", AssemblyJointRelation.OVERLAY)
    assert resolve_endcap_bottom_wrap(snap, "head")["enabled"] is False
    assert resolve_endcap_bottom_wrap(snap, "head")["reserve_u"] == 7
    assert gui.resolve_endcap_bottom_wrap(snap, "head") == resolve_endcap_bottom_wrap(snap, "head")


def test_public_joint_commit_accepts_legal_and_rejects_illegal_preset_relation():
    editable = migrate_legacy_snapshot_joints({
        "assembly_type": "OVERLAY", "existing_parts": ["box_body", "head", "tail"],
    })
    result = commit_endcap_bottom_wrap_joint(editable, "head", False)
    assert edge_relation_for_part(result, "head", "BOTTOM") is AssemblyJointRelation.INSERT
    assert gui.commit_endcap_bottom_wrap_joint(editable, "head", False) == result
    with pytest.raises(ValueError, match="not allowed"):
        commit_endcap_bottom_wrap_joint(editable, "head", True)
    fixed = migrate_legacy_snapshot_joints({
        "assembly_type": "WRAP_OVERLAY", "existing_parts": ["box_body", "head", "tail"],
    })
    assert edge_relation_for_part(fixed, "head", "BOTTOM") is AssemblyJointRelation.WRAP
    with pytest.raises(ValueError, match="not allowed"):
        commit_endcap_bottom_wrap_joint(fixed, "head", False)


def test_phase6_has_no_independent_lower_wrap_or_joint_manufacturing_logic():
    for function, public_name in (
        (gui.normalize_endcap_bottom_wrap_state, "normalize_endcap_bottom_wrap_state"),
        (gui.resolve_endcap_bottom_wrap, "resolve_endcap_bottom_wrap"),
        (gui.commit_endcap_bottom_wrap, "commit_endcap_bottom_wrap"),
        (gui.commit_endcap_bottom_wrap_joint, "commit_endcap_bottom_wrap_joint"),
    ):
        assert f"manufacturing_api.{public_name}(" in inspect.getsource(function)
    src = inspect.getsource(gui)
    assert "cabinet_family_policy.default_bottom_wrap_enabled" not in src
    assert "edge_relation_for_part(" not in src
    engine = inspect.getsource(owner)
    assert "from phase6_" not in engine
