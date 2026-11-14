"""#2517: stale Fold UI axis may be displayed but must never receive a physical edit."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.operator_fold_editor import (
    require_operator_fold_editor_profile_target as owner,
)
from phase6_bending_ui import Phase6BendingUI, resolve_profile_key
from phase6_project_file import PROJECT_SCHEMA, write_project, read_project


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _rows():
    return {
        "X": [{"len": 40.0, "phase6_key": "zl1"}],
        "Y": [{"len": 60.0, "phase6_key": "d_left"}],
    }


def _host(*, axis="Y"):
    profiles = _rows()
    notices = []
    state = SimpleNamespace(
        active_bend=axis, phase6_thickness=2.0,
        phase6_fold_ui_vault_key=None, profiles_vault={}, symmetric=True,
    )
    host = SimpleNamespace(
        state=state,
        get_active_dict=lambda: profiles,
        controls=({"len": Var("80")},),
        _mark_workspace_dirty=lambda: notices.append("dirty"),
        render=lambda: notices.append("render"),
        update_cb=lambda: notices.append("update"),
    )
    host.save = lambda: Phase6BendingUI.save(host)
    return host, profiles, notices


def test_original_public_engine_owner_qualifies_exact_existing_fold_axis():
    assert api.require_operator_fold_editor_profile_target is owner
    assert ae_engine.require_operator_fold_editor_profile_target is owner
    assert "require_operator_fold_editor_profile_target" in ae_engine.__all__
    profiles = _rows()
    before = deepcopy(profiles)
    assert api.require_operator_fold_editor_profile_target(profiles, "X") == "X"
    assert api.require_operator_fold_editor_profile_target(profiles, "Y") == "Y"
    assert profiles == before


@pytest.mark.parametrize("axis", [
    "Z", "x", "", "Y ", None, True, 0, 1.0, [], {}, ("X",),
])
def test_missing_or_nonstring_physical_axis_is_rejected_without_fallback(axis):
    profiles = _rows()
    before = deepcopy(profiles)
    with pytest.raises(ValueError, match="FOLD_EDITOR_PROFILE_TARGET_INVALID"):
        api.require_operator_fold_editor_profile_target(profiles, axis)
    assert profiles == before


@pytest.mark.parametrize("source", [
    None, [], "X", {}, {"X": None}, {"X": {}}, {"X": "not-a-profile"},
])
def test_missing_or_invalid_fold_profile_source_is_not_an_edit_target(source):
    with pytest.raises(ValueError, match="FOLD_EDITOR_PROFILE_TARGET_INVALID"):
        api.require_operator_fold_editor_profile_target(source, "X")


def test_legacy_stale_tab_can_still_render_x_but_never_commit_to_x():
    host, profiles, events = _host(axis="Z")
    original = deepcopy(profiles)
    assert resolve_profile_key(profiles, "Z") == "X"  # read-only display
    with pytest.raises(ValueError, match="FOLD_EDITOR_PROFILE_TARGET_INVALID"):
        Phase6BendingUI.save(host)
    assert profiles == original
    assert events == []
    assert host.state.profiles_vault == {}
    assert host.state.active_bend == "Z"


@pytest.mark.parametrize("edit", ["add", "remove", "mirror"])
def test_gui_invalid_axis_cannot_dirty_workspace_or_change_fold(edit):
    host, profiles, events = _host(axis="missing")
    original = deepcopy(profiles)
    if edit == "mirror":
        host._phase6_refreshing_controls = False
        perform = lambda: Phase6BendingUI.apply_mirror(host, 0, "len")
    elif edit == "add":
        perform = lambda: Phase6BendingUI.add(host, 0)
    else:
        perform = lambda: Phase6BendingUI.remove(host, 0)
    with pytest.raises(ValueError, match="FOLD_EDITOR_PROFILE_TARGET_INVALID"):
        perform()
    assert profiles == original and events == []
    assert host.state.profiles_vault == {}


def test_real_gui_valid_y_save_edits_only_y_and_survives_project_reload(tmp_path):
    host, profiles, events = _host(axis="Y")
    before = deepcopy(profiles)
    expected = api.commit_operator_fold_editor_rows(
        profiles["Y"], [{"len": 80}], 2.0,
    )
    Phase6BendingUI.save(host)
    assert profiles["X"] == before["X"]
    assert profiles["Y"] == expected
    assert profiles["Y"][0]["len"] == 80.0
    assert host.state.profiles_vault == {}
    assert events == []

    filename = write_project(
        tmp_path / "fold-physical-axis.p6fold",
        {"schema": PROJECT_SCHEMA, "snapshot": {
            "model": "金庫型",
            "box_body_fold_profile": profiles["X"],
            "head_fold_profile": profiles["Y"],
        }},
    )
    reopened = read_project(filename)["snapshot"]
    assert reopened["box_body_fold_profile"] == before["X"]
    assert reopened["head_fold_profile"] == expected


def test_real_gui_mutations_use_engine_target_and_keep_preview_fallback_separate():
    for method in (
        Phase6BendingUI.save, Phase6BendingUI.add,
        Phase6BendingUI.remove, Phase6BendingUI.apply_mirror,
    ):
        code = inspect.getsource(method)
        assert "manufacturing_api.require_operator_fold_editor_profile_target(" in code
    assert "resolve_profile_key(" not in code
    assert "original.BendingUI.save" not in code
