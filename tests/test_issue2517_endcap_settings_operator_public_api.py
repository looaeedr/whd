"""#2517 EndCap Settings operator transactions only through public Engine."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import (
    AssemblyJointRelation, edge_relation_for_part, migrate_legacy_snapshot_joints,
)
import phase6_settings_transitions as gui


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_fw_operator_linked_head_tail_save_reload_and_nonmutation(model):
    source = {"model": model, "fw": 25, "w": 500, "h": 600, "d": 300, "t": 2}
    settings = {"fw": 29}
    original = deepcopy(source)
    state = api.normalize_endcap_fw_state({**source, **settings})
    old = deepcopy(state)
    first = api.operator_endcap_fw_override(source, settings, state, "head", 33)
    assert source == original and state == old
    assert first["mode"] == api.FW_FOLLOW_HEAD
    assert first["head"]["value"] == first["tail"]["value"] == 33
    assert gui.endcap_fw_override(source, settings, state, "head", 33) == first
    second = gui.endcap_fw_override(source, settings, first, "tail", 37)
    assert second["mode"] == api.FW_INDEPENDENT
    assert (second["head"]["value"], second["tail"]["value"]) == (33, 37)
    saved = {**source, **settings, "endcap_fw": deepcopy(second)}
    for key, expected in (("head", 33), ("tail", 37)):
        assert api.resolve_endcap_fw(saved, key) == expected
    followed = api.operator_endcap_fw_follow(source, settings, second, "head", True)
    assert gui.endcap_fw_follow(source, settings, second, "head", True) == followed
    assert followed["head"]["follow_box"] is True
    assert state == old


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_wrap_operator_copy_link_split_and_saved_joint_resolution(model):
    source = {"model": model, "t": 2}
    original = deepcopy(source)
    state = api.normalize_endcap_bottom_wrap_state(source)
    one = api.operator_endcap_bottom_wrap(
        source, state, "head", reserve_u=3.5, reserve_v=2.25
    )
    assert source == original
    assert one.state["mode"] == api.WRAP_FOLLOW_HEAD
    assert one.state["head"] == one.state["tail"]
    assert one.resolved["reserve_u"] == 3.5
    assert one.resolved["reserve_v"] == 2.25
    assert state["mode"] == api.WRAP_LINKED
    assert gui.BottomWrapTransition is api.OperatorBottomWrapTransition
    assert gui.bottom_wrap(source, state, "head", reserve_u=3.5, reserve_v=2.25) == one
    split = api.operator_endcap_bottom_wrap(
        source, one.state, "tail", reserve_u=4.0, reserve_v=2.25
    )
    assert split.state["mode"] == api.WRAP_INDEPENDENT
    assert split.state["head"]["reserve_u"] == 3.5
    assert split.state["tail"]["reserve_u"] == 4.0
    saved = {**source, "endcap_bottom_wrap": deepcopy(split.state)}
    assert api.resolve_endcap_bottom_wrap(saved, "head")["reserve_u"] == 3.5
    assert api.resolve_endcap_bottom_wrap(saved, "tail")["reserve_u"] == 4.0


def test_edge_relation_uses_same_engine_joint_graph_and_preserves_snapshot():
    source = migrate_legacy_snapshot_joints({
        "model": "金庫型", "assembly_type": "OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    original = deepcopy(source)
    out = api.operator_endcap_edge_relation(
        source, "head", "bottom", AssemblyJointRelation.INSERT,
    )
    assert source == original
    assert edge_relation_for_part(out, "head", "BOTTOM") is AssemblyJointRelation.INSERT
    assert gui.endcap_edge_relation(
        source, "head", "bottom", AssemblyJointRelation.INSERT,
    ) == out
    with pytest.raises(ValueError):
        api.operator_endcap_edge_relation(source, "head", "bottom", "NOT_A_RELATION")


@pytest.mark.parametrize("kind", ("follow", "override", "wrap"))
def test_invalid_endcap_is_rejected_by_public_api(kind):
    snapshot = {"model": "受電箱", "fw": 25}
    if kind == "follow":
        call = lambda: api.operator_endcap_fw_follow(snapshot, {}, {}, "fake", True)
    elif kind == "override":
        call = lambda: api.operator_endcap_fw_override(snapshot, {}, {}, "fake", 30)
    else:
        call = lambda: api.operator_endcap_bottom_wrap(
            snapshot, None, "fake", reserve_u=2, reserve_v=1,
        )
    with pytest.raises(ValueError, match="不支援的封頭尾板件"):
        call()


def test_gui_settings_adapter_has_no_manufacturing_state_machine():
    source = (Path(__file__).resolve().parents[1] /
              "phase6_settings_transitions.py").read_text(encoding="utf-8")
    functions = {
        name: source.split("def " + name + "(", 1)[1].split("\ndef ", 1)[0]
        for name in ("endcap_fw_follow", "endcap_fw_override",
                     "bottom_wrap", "endcap_edge_relation")
    }
    for name, operation in {
        "endcap_fw_follow": "operator_endcap_fw_follow",
        "endcap_fw_override": "operator_endcap_fw_override",
        "bottom_wrap": "operator_endcap_bottom_wrap",
        "endcap_edge_relation": "operator_endcap_edge_relation",
    }.items():
        assert "manufacturing_api." + operation + "(" in functions[name]
        assert "deepcopy(" not in functions[name]
        assert "set_part_edge_relation(" not in functions[name]
    engine = (Path(__file__).resolve().parents[1] /
              "ae_engine/operator_endcap_settings_transactions.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine
