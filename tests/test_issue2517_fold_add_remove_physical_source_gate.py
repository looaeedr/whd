"""#2517: headless and GUI Fold Add/Remove cannot manufacture with invalid T."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_fold_editor_add_segment, operator_fold_editor_remove_segment
from phase6_bending_ui import Phase6BendingUI
import phase6_project_file as project


def _material():
    return [{"len": 24.0, "angle": 90}, {"len": 120.0, "core": "W"}]


@pytest.mark.parametrize("bad", (
    None, True, False, -2, 0, -0.0, "0", "-1.5", "", "bad",
    "nan", "inf", float("nan"), float("inf"), float("-inf"), 10 ** 400,
))
@pytest.mark.parametrize("operation", ("add", "remove"))
def test_engine_add_remove_rejects_bad_physical_T_without_touching_existing_fold(
    bad, operation,
):
    source = _material()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:thickness"):
        if operation == "add":
            api.operator_fold_editor_add_segment(source, 0, bad)
        else:
            api.operator_fold_editor_remove_segment(source, 0, bad)
    assert source == before


@pytest.mark.parametrize("bad", (True, False, None, "0", 0.0, 1.25, [], {}))
def test_add_position_must_be_real_operator_action_not_boolean_or_display_text(bad):
    source = _material()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:position"):
        api.operator_fold_editor_add_segment(source, bad, 2.0)
    assert source == before


@pytest.mark.parametrize("bad", (True, False, None, "0", 0.0, 1.5))
def test_remove_invalid_index_retains_existing_none_contract_without_deleting_row(bad):
    source = _material()
    before = deepcopy(source)
    assert api.operator_fold_editor_remove_segment(source, bad, 2.0) is None
    assert source == before


@pytest.mark.parametrize("T", (2, 2.0, 2.5, "2.5"))
@pytest.mark.parametrize("position", (0, -1, 1, 3))
def test_valid_legacy_add_position_preserves_true_material_and_adjacent_bends(
    T, position,
):
    source = _material()
    before = deepcopy(source)
    actual = api.operator_fold_editor_add_segment(source, position, T)
    assert source == before
    assert len(actual) == 3
    assert [row["len"] for row in actual] == (
        [50, 24.0, 120.0] if position == 0 else [24.0, 120.0, 50]
    )
    assert actual[0]["ui_len_add"] == pytest.approx(float(T))
    if position == 0:
        assert actual[1]["ui_len_add"] == pytest.approx(2 * float(T))
        assert actual[2]["ui_len_add"] == pytest.approx(float(T))
    else:
        assert actual[1]["ui_len_add"] == pytest.approx(2 * float(T))
        assert actual[2]["ui_len_add"] == pytest.approx(float(T))


@pytest.mark.parametrize("T", (2, 2.5, "2.5"))
def test_valid_remove_recomputes_material_bends_with_original_public_contract(T):
    source = [{"len": 12, "angle": 90}, {"len": 25, "angle": 90},
              {"len": 120, "core": "W", "angle": 90},
              {"len": 25, "angle": 90}, {"len": 12}]
    before = deepcopy(source)
    output = api.operator_fold_editor_remove_segment(
        source, 0, T, symmetric_box_body=True,
    )
    assert source == before
    assert [row["len"] for row in output] == [25, 120, 25]
    assert [row.get("ui_len_add") for row in output] == pytest.approx([
        float(T), float(T) * 2, float(T),
    ])
    assert output[1]["core"] == "W"


class Var:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


def _host(rows):
    material = deepcopy(rows)
    active = {"X": material}
    state = SimpleNamespace(
        phase6_thickness=2.0, active_bend="X",
        phase6_fold_ui_vault_key="箱身",
        symmetric=False, profiles_vault={},
    )
    controls = []
    for row in material:
        ui = {"len": Var(row["len"])}
        if "angle" in row:
            ui["angle"] = Var(-row["angle"] if row["angle"] in (-90, 90)
                              else row["angle"])
        controls.append(ui)
    notices = []
    host = SimpleNamespace(
        controls=tuple(controls), state=state,
        get_active_dict=lambda: active, _active_profile_key=lambda _: "X",
        _mark_workspace_dirty=lambda: notices.append("dirty"),
        render=lambda: notices.append("render"),
        update_cb=lambda: notices.append("update"),
    )
    host.save = lambda: Phase6BendingUI.save(host)
    return host, active, material, notices


def test_actual_tk_free_gui_add_uses_engine_commit_then_engine_add_and_saves(tmp_path):
    material = _material()
    host, active, detached, notices = _host(material)
    expected_committed = api.commit_operator_fold_editor_rows(
        material, ({"len": 24, "angle": -90}, {"len": 120}), 2.0,
    )
    expected = api.operator_fold_editor_add_segment(expected_committed, 0, 2.0)
    Phase6BendingUI.add(host, 0)
    assert active["X"] == expected
    assert active["X"] is host.state.profiles_vault["箱身"]
    assert detached == material
    assert notices == ["dirty", "render", "update"]

    path = project.write_project(tmp_path / "fold-add.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {"model": "金庫型", "box_body_fold_profile": expected},
    })
    assert project.read_project(path)["snapshot"]["box_body_fold_profile"] == expected


def test_actual_tk_free_gui_remove_uses_engine_commit_then_engine_remove():
    material = _material()
    host, active, detached, notices = _host(material)
    expected_committed = api.commit_operator_fold_editor_rows(
        material, ({"len": 24, "angle": -90}, {"len": 120}), 2.0,
    )
    expected = api.operator_fold_editor_remove_segment(expected_committed, 0, 2.0)
    Phase6BendingUI.remove(host, 0)
    assert active["X"] == expected
    assert active["X"] is host.state.profiles_vault["箱身"]
    assert detached == material
    assert active["X"][0]["core"] == "W"
    assert notices == ["dirty", "render", "update"]


def test_engine_source_add_remove_share_commit_thickness_gate_and_no_ui_formula():
    source = inspect.getsource(api.operator_fold_editor_add_segment)
    removed = inspect.getsource(api.operator_fold_editor_remove_segment)
    committed = inspect.getsource(api.commit_operator_fold_editor_rows)
    assert "_positive_fold_thickness(thickness)" in source
    assert "_positive_fold_thickness(thickness)" in removed
    assert "_positive_fold_thickness(thickness)" in committed
    assert api.operator_fold_editor_add_segment is operator_fold_editor_add_segment
    assert api.operator_fold_editor_remove_segment is operator_fold_editor_remove_segment
