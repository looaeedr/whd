"""#2517: Fold Tk controls and Python callers cannot fabricate 0 mm material."""
from __future__ import annotations

from copy import deepcopy
from math import isnan
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import normalize_operator_fold_editor_control as root_parser
from phase6_bending_ui import Phase6BendingUI
import phase6_project_file as project


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw

    def set(self, raw):
        self.raw = raw


def _old():
    return [
        {"len": 12, "angle": 90, "phase6_key": "zl1"},
        {"len": 100, "phase6_key": "d_left"},
    ]


def _editor(length="18", angle="-90", thickness=2.0):
    material = _old()
    active = {"X": material}
    state = SimpleNamespace(
        phase6_thickness=thickness,
        phase6_fold_ui_vault_key="箱身", profiles_vault={},
    )
    host = SimpleNamespace(
        controls=({"len": Var(length), "angle": Var(angle)},
                  {"len": Var("100")}),
        state=state,
        get_active_dict=lambda: active,
        _active_profile_key=lambda _: "X",
    )
    return host, active, material


@pytest.mark.parametrize("raw,want", [
    ("17", 17), (" 17.5 ", 18), ("-18", -18), (0, 0),
    ("0.5", 0), (90, 90), ("-90", -90),
])
@pytest.mark.parametrize("field", ["len", "angle"])
def test_engine_control_parser_preserves_legacy_whole_mm_rounding(raw, want, field):
    assert api.normalize_operator_fold_editor_control(raw, field=field) == want
    assert root_parser is api.normalize_operator_fold_editor_control


@pytest.mark.parametrize("raw", [
    None, True, False, "", "not-number", "nan", "inf",
    float("nan"), float("inf"), float("-inf"), 10 ** 400,
])
@pytest.mark.parametrize("field", ["len", "angle"])
def test_invalid_tk_source_fails_closed_before_rounding_or_commit(raw, field):
    with pytest.raises(ValueError, match=f"FOLD_EDITOR_SOURCE_INVALID:{field}"):
        api.normalize_operator_fold_editor_control(raw, field=field)


@pytest.mark.parametrize("field,invalid", [
    ("len", True), ("len", False), ("len", None), ("len", "bad"),
    ("len", "nan"), ("len", float("inf")), ("len", float("nan")),
    ("angle", True), ("angle", False), ("angle", None), ("angle", "nan"),
    ("angle", float("inf")), ("angle", "not-angle"),
])
def test_headless_operator_commit_rejects_invalid_physical_fold_sources(field, invalid):
    old = _old()
    edits = [{"len": -18, "angle": -90}, {"len": 100}]
    edits[0][field] = invalid
    prior = deepcopy(old)
    with pytest.raises(ValueError, match=f"FOLD_EDITOR_SOURCE_INVALID:{field}"):
        api.commit_operator_fold_editor_rows(old, edits, 2.0)
    assert old == prior


@pytest.mark.parametrize("invalid", [
    None, True, False, -2.0, 0, "nan", "inf",
    float("nan"), float("inf"), "unknown", 10 ** 400,
])
def test_invalid_thickness_cannot_be_clamped_to_flat_fold(invalid):
    before = _old()
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:thickness"):
        api.commit_operator_fold_editor_rows(
            before, ({"len": -18, "angle": -90}, {"len": 100}), invalid,
        )
    assert before == _old()


def test_real_gui_save_rejects_malformed_entry_without_mutating_vault_or_workspace():
    for length, angle in (("invalid", "-90"), ("18", "invalid"),
                          ("nan", "-90"), ("18", "inf"), ("", "90")):
        gui, active, old = _editor(length, angle)
        prior = deepcopy(old)
        with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID"):
            Phase6BendingUI.save(gui)
        assert active["X"] is old
        assert old == prior
        assert gui.state.profiles_vault == {}


def test_real_gui_valid_signed_fold_save_matches_engine_and_project_roundtrip(tmp_path):
    gui, active, old = _editor("-18", "-90")
    before = deepcopy(old)
    expected = api.commit_operator_fold_editor_rows(
        old, ({"len": -18, "angle": -90}, {"len": 100}), 2.0,
    )
    Phase6BendingUI.save(gui)
    assert active["X"] == expected
    assert gui.state.profiles_vault["箱身"] is active["X"]
    assert old == before
    assert expected[0]["len"] == 16
    assert expected[0]["phase6_ui_sign"] == -1.0

    path = project.write_project(
        tmp_path / "fold-control-safe.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": {
            "model": "金庫型", "box_body_fold_profile": expected,
        }},
    )
    restored = project.read_project(path)["snapshot"]
    assert restored["box_body_fold_profile"] == expected


@pytest.mark.parametrize("bad", ["bad", "nan", float("nan"), "", True])
def test_symmetry_event_cannot_use_legacy_zero_fallback_on_invalid_control(bad):
    material = _old()
    controls = ({"len": Var(bad), "angle": Var("-90")}, {"len": Var("100")})
    dirty = []
    shell = SimpleNamespace(
        _phase6_refreshing_controls=False, controls=controls,
        _mark_workspace_dirty=lambda: dirty.append(1),
    )
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID"):
        Phase6BendingUI.apply_mirror(shell, 0, "len")
    assert not dirty
    assert material == _old()


def test_gui_has_no_get_int_manufacturing_fallback_in_fold_save():
    source = inspect.getsource(Phase6BendingUI.save)
    assert "manufacturing_api.normalize_operator_fold_editor_control(" in source
    assert "original.get_int(" not in source
    assert "manufacturing_api.commit_operator_fold_editor_rows(" in source
    mirror = inspect.getsource(Phase6BendingUI.apply_mirror)
    assert "manufacturing_api.normalize_operator_fold_editor_control(" in mirror
