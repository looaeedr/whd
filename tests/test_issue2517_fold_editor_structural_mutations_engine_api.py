# -*- coding: utf-8 -*-
"""#2517: fold Add/Remove source mutations are headless Engine transactions."""
from copy import deepcopy
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.operator_fold_editor import (
    add_operator_fold_editor_rows, remove_operator_fold_editor_rows,
)
from phase6_bending_ui import Phase6BendingUI
from phase6_fold_profiles import engine_segment_length_to_ui
from phase6_project_file import _encode, _decode


def _fold():
    return [
        {"len": 15, "angle": 90, "phase6_key": "zl1"},
        {"len": 25, "angle": -90, "phase6_key": "fw_left"},
        {"len": 100, "angle": -90, "phase6_key": "d_left", "core": "D"},
        {"len": 350, "angle": -90, "phase6_key": "w", "core": "W"},
        {"len": 100, "angle": -90, "phase6_key": "d_right", "core": "D"},
        {"len": 25, "angle": -90, "phase6_key": "fw_right"},
        {"len": 15, "phase6_key": "zr1"},
    ]


def test_engine_front_and_terminal_add_recalculate_true_bend_metadata():
    source = _fold()
    old = deepcopy(source)
    first = manufacturing_api.add_operator_fold_editor_rows(source, 0, 2.0)
    assert manufacturing_api.add_operator_fold_editor_rows is add_operator_fold_editor_rows
    assert len(first) == len(source) + 1
    assert first[0]["angle"] == 90 and first[0]["len"] == 50
    assert first[1]["phase6_key"] == "zl1"
    assert first[0]["ui_len_add"] == 2.0
    assert source == old

    terminal = manufacturing_api.add_operator_fold_editor_rows(source, 1, 2.0)
    assert terminal[-2]["phase6_key"] == "zr1"
    assert terminal[-2]["angle"] == -90
    assert terminal[-1]["len"] == 50
    assert terminal[-1]["ui_len_add"] == 2.0
    assert len(terminal) == len(source) + 1
    assert source == old
    assert _decode(_encode({"box_body_profile": terminal}))["box_body_profile"] == terminal


def test_source_owned_symmetric_remove_paired_unlocked_physical_rows():
    source = _fold()
    old = deepcopy(source)
    result = manufacturing_api.remove_operator_fold_editor_rows(
        source, 0, 2.0, symmetric_box_body=True,
    )
    assert manufacturing_api.remove_operator_fold_editor_rows is remove_operator_fold_editor_rows
    assert [row.get("phase6_key") for row in result] == [
        "fw_left", "d_left", "w", "d_right", "fw_right",
    ]
    assert "angle" not in result[-1]
    assert source == old
    assert tuple(engine_segment_length_to_ui(row) for row in result)
    assert _decode(_encode({"box_body_profile": result}))["box_body_profile"] == result


def test_fixed_fw_and_d_w_d_core_cannot_be_removed_or_partially_mirrored():
    source = _fold()
    old = deepcopy(source)
    for index in (-1, len(source), 1, 2, 3, 4, 5):
        assert manufacturing_api.remove_operator_fold_editor_rows(
            source, index, 2.0, symmetric_box_body=True,
        ) is None
    assert source == old
    # A removable left structural row may not remove a matching immutable row.
    no_right = deepcopy(source)
    no_right[-1]["phase6_key"] = "fw_right"
    assert manufacturing_api.remove_operator_fold_editor_rows(
        no_right, 0, 2.0, symmetric_box_body=True,
    ) is not None  # missing mirrored removable peer => only source is removed
    assert no_right == [*old[:-1], {**old[-1], "phase6_key": "fw_right"}]


def test_operator_added_unkeyed_mirror_requires_unkeyed_opposite():
    source = [
        {"len": 12, "angle": 90},
        {"len": 100, "core": "D", "angle": 90},
        {"len": 100, "core": "D", "angle": -90},
        {"len": 12},
    ]
    candidate = manufacturing_api.remove_operator_fold_editor_rows(
        source, 0, 2.0, symmetric_box_body=True,
    )
    assert len(candidate) == 2
    assert candidate[-1].get("core") == "D"
    assert "angle" not in candidate[-1]
    blocked = deepcopy(source)
    blocked[-1]["phase6_key"] = "zr1"
    only_first = manufacturing_api.remove_operator_fold_editor_rows(
        blocked, 0, 2.0, symmetric_box_body=True,
    )
    assert len(only_first) == 3 and only_first[-1]["phase6_key"] == "zr1"
    assert blocked[-1]["phase6_key"] == "zr1"


def test_receiving_disallows_box_symmetry_and_non_box_editor_deletes_only_selected():
    assert family_policy.box_body_symmetry_allowed("受電箱") is False
    assert family_policy.box_body_symmetry_allowed("金庫型") is True
    source = _fold()
    result = manufacturing_api.remove_operator_fold_editor_rows(
        source, 0, 2.0, symmetric_box_body=False,
    )
    assert "zr1" in [row.get("phase6_key") for row in result]
    assert "zl1" not in [row.get("phase6_key") for row in result]


def test_gui_add_remove_are_one_engine_call_and_keep_existing_source_cache(monkeypatch):
    import phase6_bending_ui

    active = {"X": _fold()}
    cache = {"箱身": active["X"]}
    events = []
    state = SimpleNamespace(
        symmetric=True, phase6_fold_ui_vault_key="箱身",
        phase6_thickness=2.0, profiles_vault=cache,
    )
    holder = SimpleNamespace(
        state=state,
        get_active_dict=lambda: active,
        _active_profile_key=lambda a: "X",
        _mark_workspace_dirty=lambda: events.append("dirty"),
        save=lambda: events.append("save"),
        render=lambda: events.append("render"),
        update_cb=lambda: events.append("update"),
    )
    calls = []
    actual_add = manufacturing_api.add_operator_fold_editor_rows
    actual_remove = manufacturing_api.remove_operator_fold_editor_rows

    def add(*args, **kwargs):
        calls.append(("add", args[1], args[2]))
        return actual_add(*args, **kwargs)

    def remove(*args, **kwargs):
        calls.append(("remove", args[1], kwargs["symmetric_box_body"]))
        return actual_remove(*args, **kwargs)

    monkeypatch.setattr(manufacturing_api, "add_operator_fold_editor_rows", add)
    monkeypatch.setattr(manufacturing_api, "remove_operator_fold_editor_rows", remove)
    Phase6BendingUI.add(holder, 0)
    assert calls == [("add", 0, 2.0)]
    assert active["X"] is cache["箱身"]
    assert events == ["dirty", "save", "render", "update"]

    events.clear()
    Phase6BendingUI.remove(holder, 0)
    assert calls[-1] == ("remove", 0, True)
    assert active["X"] is cache["箱身"]
    assert events == ["dirty", "save", "render", "update"]


def test_gui_no_longer_mutates_material_topology_or_mirrored_structural_rows():
    add = inspect.getsource(Phase6BendingUI.add)
    remove = inspect.getsource(Phase6BendingUI.remove)
    assert "manufacturing_api.add_operator_fold_editor_rows(" in add
    assert "manufacturing_api.remove_operator_fold_editor_rows(" in remove
    for fragment in ("segs.insert(", "segs.pop(", "apply_outside_dimension_compensation(",
                     "fw_left", "zr1", "candidate_idx", "remove_indexes"):
        assert fragment not in add + remove
    module = (Path(__file__).resolve().parents[1]
              / "ae_engine/operator_fold_editor.py").read_text(encoding="utf-8")
    assert "from phase6_" not in module and "tkinter" not in module
