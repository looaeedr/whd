"""#2517: historical Fold symmetry must not bypass the public Engine commit."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.operator_fold_editor import OperatorFoldMirrorPlan
from phase6_bending_ui import Phase6BendingUI
import phase6_project_file as project


class Var:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


@pytest.mark.parametrize("field,index,target", [
    ("len", 0, 3), ("len", 1, 2), ("angle", 0, 2),
    ("angle", 1, None),
])
def test_engine_legacy_mirror_plan_resolves_historical_positional_index(
    field, index, target,
):
    unkeyed = tuple({"len": n} for n in (10, 15, 15, 10))
    before = deepcopy(unkeyed)
    assert api.plan_operator_fold_mirror_target(
        unkeyed, index, field, is_box_body=True,
    ) == OperatorFoldMirrorPlan(None, False)
    assert api.plan_operator_fold_mirror_target(
        unkeyed, index, field, is_box_body=True,
        resolve_legacy_position=True,
    ) == OperatorFoldMirrorPlan(target, True)
    assert unkeyed == before


def test_legacy_position_is_allowed_for_non_box_body_but_does_not_override_keyed_box():
    rows = tuple(
        {"len": n, "phase6_key": key}
        for n, key in ((10, "door_fold_l"), (200, "door_face_w"),
                       (10, "door_fold_r"))
    )
    assert api.plan_operator_fold_mirror_target(
        rows, 0, "len", is_box_body=False,
    ) == OperatorFoldMirrorPlan(None, False)
    assert api.plan_operator_fold_mirror_target(
        rows, 0, "len", is_box_body=False, resolve_legacy_position=True,
    ) == OperatorFoldMirrorPlan(2, True)

    keyed_box = (
        {"len": 10}, {"len": 15}, {"len": 15},
        {"len": 10, "phase6_key": "fw_right"},
    )
    assert api.plan_operator_fold_mirror_target(
        keyed_box, 0, "len", is_box_body=True,
        resolve_legacy_position=True,
    ) == OperatorFoldMirrorPlan(None, True)


def _host(rows, source_length="27", *, box_body=False):
    active = {"X": deepcopy(rows)}
    controls = []
    for i, row in enumerate(active["X"]):
        ctrl = {"len": Var(source_length if i == 0 else str(row["len"]))}
        if "angle" in row:
            ctrl["angle"] = Var(str(-row["angle"]) if row["angle"] in (-90, 90)
                                else str(row["angle"]))
        controls.append(ctrl)
    updates, dirty = [], []
    state = SimpleNamespace(
        symmetric=True, phase6_thickness=2.0, active_bend="X",
        phase6_fold_ui_vault_key="箱身" if box_body else None,
        profiles_vault={},
    )
    shell = SimpleNamespace(
        _phase6_refreshing_controls=False,
        controls=controls, state=state,
        update_cb=lambda: updates.append("render"),
        _mark_workspace_dirty=lambda: dirty.append("dirty"),
        get_active_dict=lambda: active,
        _active_profile_key=lambda _: "X",
    )
    shell.save = lambda: Phase6BendingUI.save(shell)
    return shell, active, controls, updates, dirty


def test_non_box_mirror_keeps_original_position_but_engine_owns_saved_fold(tmp_path):
    rows = [
        {"len": 23, "angle": 90, "phase6_key": "door_fold_l"},
        {"len": 200, "angle": -90, "core": "W", "phase6_key": "door_face_w"},
        {"len": 23, "phase6_key": "door_fold_r"},
    ]
    before = deepcopy(rows)
    shell, active, controls, updates, dirty = _host(rows, source_length="30")
    assert Phase6BendingUI.apply_mirror(shell, 0, "len") is None
    assert controls[2]["len"].get() == "30"
    assert updates == ["render"] and dirty == ["dirty"]
    assert [row["phase6_key"] for row in active["X"]] == [
        "door_fold_l", "door_face_w", "door_fold_r",
    ]
    assert active["X"][1]["core"] == "W"
    assert rows == before
    assert active["X"] == api.commit_operator_fold_editor_rows(
        rows, (
            {"len": 30, "angle": -90},
            {"len": 200, "angle": 90},
            {"len": 30},
        ), 2.0,
    )
    target = project.write_project(tmp_path / "legacy-mirror.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {"model": "金庫型", "door_fold_profiles": {"X": active["X"]}},
    })
    saved = project.read_project(target)["snapshot"]
    assert saved["door_fold_profiles"]["X"] == active["X"]


def test_keyed_box_body_mirror_is_semantic_not_positional_and_keeps_metadata():
    rows = [
        {"len": 25, "angle": 90, "phase6_key": "fw_left"},
        {"len": 200, "angle": -90, "core": "D", "phase6_key": "d_left"},
        {"len": 400, "angle": -90, "core": "W", "phase6_key": "w"},
        {"len": 200, "angle": -90, "core": "D", "phase6_key": "d_right"},
        {"len": 25, "phase6_key": "fw_right"},
    ]
    shell, active, controls, updates, dirty = _host(
        rows, source_length="31", box_body=True,
    )
    Phase6BendingUI.apply_mirror(shell, 0, "len")
    assert controls[4]["len"].get() == "31"
    assert controls[3]["len"].get() == "200"
    assert [row["phase6_key"] for row in active["X"]] == [
        "fw_left", "d_left", "w", "d_right", "fw_right",
    ]
    assert active["X"][1]["core"] == active["X"][3]["core"] == "D"
    assert updates == ["render"] and dirty == ["dirty"]


def test_mirror_never_calls_legacy_bendingui_manufacturing_save():
    source = inspect.getsource(Phase6BendingUI.apply_mirror)
    assert "manufacturing_api.plan_operator_fold_mirror_target(" in source
    assert "resolve_legacy_position=True" in source
    assert "self.save()" in source
    assert "super().apply_mirror(" not in source
    assert "len(self.controls) - 1" not in source


@pytest.mark.parametrize("bad", [
    True, False, -1, -4, 3, 5, 0.0, 1.5, "0", None, [], {},
])
@pytest.mark.parametrize("box", [False, True])
def test_public_engine_mirror_cannot_alias_or_wrap_physical_source_index(bad, box):
    rows = [
        {"len": 23, "angle": 90, "phase6_key": "door_fold_l"},
        {"len": 200, "angle": -90, "phase6_key": "door_face_w"},
        {"len": 23, "phase6_key": "door_fold_r"},
    ]
    before = deepcopy(rows)
    with pytest.raises(ValueError, match="FOLD_EDITOR_MIRROR_TARGET_INVALID"):
        api.plan_operator_fold_mirror_target(
            rows, bad, "len", is_box_body=box, resolve_legacy_position=True,
        )
    assert rows == before


@pytest.mark.parametrize("field", [None, True, 1, "", "width", "Angle", [], {}])
def test_public_engine_mirror_rejects_unknown_control_field(field):
    rows = ({"len": 23, "angle": 90}, {"len": 200}, {"len": 23})
    before = deepcopy(rows)
    with pytest.raises(ValueError, match="FOLD_EDITOR_MIRROR_TARGET_INVALID"):
        api.plan_operator_fold_mirror_target(
            rows, 0, field, is_box_body=False, resolve_legacy_position=True,
        )
    assert rows == before


def test_public_engine_mirror_rejects_malformed_other_source_row():
    source = ({"len": 23}, {"len": 200}, False)
    with pytest.raises(ValueError, match="FOLD_EDITOR_MIRROR_TARGET_INVALID"):
        api.plan_operator_fold_mirror_target(
            source, 0, "len", is_box_body=True, resolve_legacy_position=True,
        )


@pytest.mark.parametrize("bad_index,bad_field", [
    (True, "len"), (-1, "len"), (3, "len"),
    (0.0, "len"), ("0", "len"), (0, "width"), (0, None),
])
@pytest.mark.parametrize("symmetric", [False, True])
def test_gui_bad_mirror_target_never_dirties_workspace_or_writes_other_control(
    bad_index, bad_field, symmetric,
):
    rows = [
        {"len": 23, "angle": 90, "phase6_key": "door_fold_l"},
        {"len": 200, "angle": -90, "phase6_key": "door_face_w"},
        {"len": 23, "phase6_key": "door_fold_r"},
    ]
    shell, active, controls, updates, dirty = _host(rows, source_length="30")
    shell.state.symmetric = symmetric
    before = deepcopy(active)
    controls_before = [dict((key, var.get()) for key, var in row.items()) for row in controls]
    with pytest.raises(ValueError, match="FOLD_EDITOR_MIRROR_TARGET_INVALID"):
        Phase6BendingUI.apply_mirror(shell, bad_index, bad_field)
    assert active == before
    assert controls_before == [
        dict((key, var.get()) for key, var in row.items()) for row in controls
    ]
    assert updates == [] and dirty == []
    assert shell.state.profiles_vault == {}


def test_gui_late_mirror_control_drift_fails_before_dirty():
    rows = [{"len": 20}, {"len": 100}, {"len": 20}]
    shell, active, controls, updates, dirty = _host(rows)
    shell.controls = controls[:1]  # stale row widget list, complete physical source
    before = deepcopy(active)
    with pytest.raises(ValueError, match="FOLD_EDITOR_MIRROR_CONTROL_INVALID"):
        Phase6BendingUI.apply_mirror(shell, 0, "len")
    assert active == before
    assert updates == [] and dirty == []


def test_mirror_source_validation_precedes_gui_dirty_and_tk_modification():
    source = inspect.getsource(Phase6BendingUI.apply_mirror)
    assert source.index("manufacturing_api.plan_operator_fold_mirror_target(") < (
        source.index("self._mark_workspace_dirty()")
    )
    engine = inspect.getsource(api.plan_operator_fold_mirror_target)
    assert "type(source_index) is not int" in engine
    assert 'field not in ("len", "angle")' in engine
