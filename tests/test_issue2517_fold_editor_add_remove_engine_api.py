"""#2517: Fold-editor Add/Remove physical transactions live in Engine."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

from ae_engine import manufacturing_api
from ae_engine import operator_fold_editor_add_segment, operator_fold_editor_remove_segment
from phase6_bending_ui import Phase6BendingUI


def test_engine_add_front_or_back_recomputes_real_bend_count():
    original = [{"len": 20, "angle": 90}, {"len": 70}]
    before = deepcopy(original)
    front = operator_fold_editor_add_segment(original, 0, 2)
    back = operator_fold_editor_add_segment(original, 1, 2)
    assert original == before
    assert [x["len"] for x in front] == [50, 20, 70]
    assert [x.get("ui_len_add") for x in front] == [2, 4, 2]
    assert [x.get("angle") for x in back] == [90, -90, None]
    assert [x.get("ui_len_add") for x in back] == [2, 4, 2]
    assert manufacturing_api.operator_fold_editor_add_segment is operator_fold_editor_add_segment


def test_engine_remove_two_unkeyed_mates_and_recomputes_live_bends():
    original = [
        {"len": 12, "angle": 90}, {"len": 25, "angle": 90},
        {"len": 100, "core": "W", "angle": 90},
        {"len": 25, "angle": 90}, {"len": 12},
    ]
    saved = deepcopy(original)
    rows = operator_fold_editor_remove_segment(original, 0, 2, symmetric_box_body=True)
    assert original == saved
    assert [x["len"] for x in rows] == [25, 100, 25]
    assert [x.get("ui_len_add") for x in rows] == [2, 4, 2]
    assert "angle" not in rows[-1]
    assert manufacturing_api.operator_fold_editor_remove_segment is operator_fold_editor_remove_segment


def test_engine_remove_keyed_pair_and_protect_core_or_invalid_target():
    original = [
        {"phase6_key": "extra_left", "len": 14, "angle": 90},
        {"phase6_key": "zl2", "len": 17, "angle": 90},
        {"phase6_key": "d_left", "core": "D", "len": 100, "angle": 90},
        {"phase6_key": "w", "core": "W", "len": 400, "angle": 90},
        {"phase6_key": "d_right", "core": "D", "len": 100, "angle": 90},
        {"phase6_key": "zr2", "len": 17, "angle": 90},
        {"phase6_key": "extra_right", "len": 14},
    ]
    saved = deepcopy(original)
    rows = operator_fold_editor_remove_segment(original, 1, 2, symmetric_box_body=True)
    assert [x.get("phase6_key") for x in rows] == [
        "extra_left", "d_left", "w", "d_right", "extra_right",
    ]
    assert operator_fold_editor_remove_segment(original, 2, 2, symmetric_box_body=True) is None
    assert operator_fold_editor_remove_segment(original, 100, 2) is None
    assert original == saved


def test_engine_rejects_protected_symmetric_counterpart_without_mutation():
    source = [{"len": 12, "angle": 90}, {"len": 100, "core": "D"}]
    before = deepcopy(source)
    assert operator_fold_editor_remove_segment(
        source, 0, 2, symmetric_box_body=True,
    ) is None
    assert source == before


def test_gui_add_remove_only_forward_operator_actions_preserving_vault_list(monkeypatch):
    rows = [{"len": 12}]
    active = {"X": rows}
    called = []
    monkeypatch.setattr(manufacturing_api, "operator_fold_editor_add_segment",
                        lambda segs, pos, thickness: (called.append(("add",pos,thickness)) or [{"len": 50}]))
    monkeypatch.setattr(manufacturing_api, "operator_fold_editor_remove_segment",
                        lambda segs, index, thickness, *, symmetric_box_body:
                        (called.append(("remove",index,thickness,symmetric_box_body)) or [{"len": 16}]))
    state = SimpleNamespace(phase6_thickness=2.0, phase6_fold_ui_vault_key="箱身",
                            symmetric=True, profiles_vault={"箱身": rows})
    host = SimpleNamespace(
        state=state, save=lambda:None, _mark_workspace_dirty=lambda:None,
        get_active_dict=lambda:active, _active_profile_key=lambda _: "X",
        render=lambda: called.append(("render",)),
        update_cb=lambda:called.append(("updated",)),
    )
    Phase6BendingUI.add(host, 0)
    Phase6BendingUI.remove(host, 0)
    assert rows == [{"len": 16}] and rows is active["X"] is state.profiles_vault["箱身"]
    assert ("add",0,2.0) in called
    assert ("remove",0,2.0,True) in called
    assert called.count(("render",)) == 2


def test_gui_add_remove_do_not_own_material_formula_or_physical_mirror_table():
    src = inspect.getsource(Phase6BendingUI.add)+inspect.getsource(Phase6BendingUI.remove)
    assert "manufacturing_api.operator_fold_editor_add_segment(" in src
    assert "manufacturing_api.operator_fold_editor_remove_segment(" in src
    assert "apply_outside_dimension_compensation(" not in src
    assert '"zl1": "zr1"' not in src
    assert "can_remove_segment(" not in src
