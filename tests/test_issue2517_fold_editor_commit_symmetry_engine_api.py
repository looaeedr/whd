# -*- coding: utf-8 -*-
"""#2517 Fold Editor source writes and structural mirror keys belong to Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.operator_fold_editor import (
    OperatorFoldMirrorPlan, commit_operator_fold_editor_rows,
    plan_operator_fold_mirror_target,
)
from ae_engine.cabinet_types import policy as cabinet_family_policy
from phase6_project_file import _encode, _decode
from phase6_fold_profiles import (
    apply_outside_dimension_compensation,
    engine_segment_length_to_ui,
)
from phase6_bending_ui import Phase6BendingUI


@pytest.mark.parametrize(
    "ui_lengths,ui_angles,expected_material",
    [
        ((24, 24, 29), (-90, 90), (22, 20, 27)),
        ((24, 24, 29), (-90, 0), (22, 22, 29)),
        ((24, 24, 29), (0, 0), (24, 24, 29)),
        ((17, 29, 17), (-90, 90), (15, 25, 15)),
    ],
)
def test_engine_fold_source_uses_new_adjacent_bend_topology(
    ui_lengths, ui_angles, expected_material,
):
    originals = [
        {"len": 100, "angle": 90, "phase6_key": "left"},
        {"len": 100, "angle": -90, "core": "D", "phase6_key": "d_left"},
        {"len": 100, "phase6_key": "right"},
    ]
    before = deepcopy(originals)
    operator = [
        {"len": value, **({"angle": ui_angles[index]} if index < len(ui_angles) else {})}
        for index, value in enumerate(ui_lengths)
    ]
    edited = manufacturing_api.commit_operator_fold_editor_rows(
        originals, operator, 2.0,
    )
    assert manufacturing_api.commit_operator_fold_editor_rows is commit_operator_fold_editor_rows
    assert originals == before
    assert tuple(x["len"] for x in edited) == pytest.approx(expected_material)
    assert tuple(engine_segment_length_to_ui(x) for x in edited) == ui_lengths
    assert edited[0]["phase6_key"] == "left"
    assert edited[1]["core"] == "D"
    assert edited[2]["phase6_key"] == "right"
    assert edited[0].get("angle") == (90 if ui_angles[0] == -90 else ui_angles[0])
    assert edited[1].get("angle") == (-90 if ui_angles[1] == 90 else ui_angles[1])
    assert _decode(_encode({"box_body_profile": edited}))["box_body_profile"] == edited


def test_signed_operator_length_and_metadata_are_preserved_without_changing_material_sign():
    old = [
        {"len": 12, "angle": 90, "phase6_ui_sign": -1.0, "phase6_key": "zl1"},
        {"len": 100, "phase6_key": "d_left"},
    ]
    before = deepcopy(old)
    rows = manufacturing_api.commit_operator_fold_editor_rows(
        old, ({"len": -18, "angle": -90}, {"len": 100}), 2,
    )
    assert rows[0]["len"] == 16
    assert rows[0]["phase6_ui_sign"] == -1.0
    assert rows[1]["len"] == 98
    assert old == before
    assert tuple(row.get("phase6_key") for row in rows) == ("zl1", "d_left")
    with pytest.raises(KeyError):
        manufacturing_api.commit_operator_fold_editor_rows(
            old, ({"angle": -90},), 2,
        )
    assert old == before


def _structural_rows():
    return [
        {"phase6_key": "extra_left", "angle": 90},
        {"phase6_key": "zl1", "angle": 90},
        {"phase6_key": "zl2", "angle": 90},
        {"phase6_key": "fw_left", "angle": 90},
        {"phase6_key": "d_left", "angle": 90},
        {"phase6_key": "w", "angle": 90},
        {"phase6_key": "d_right", "angle": 90},
        {"phase6_key": "fw_right", "angle": 90},
        {"phase6_key": "zr2", "angle": 90},
        {"phase6_key": "zr1"},
    ]


def test_engine_keyed_mirror_matches_real_fw_and_bend_boundary_not_position():
    rows = _structural_rows()
    original = deepcopy(rows)
    assert manufacturing_api.plan_operator_fold_mirror_target(
        rows, 3, "len", is_box_body=True,
    ) == OperatorFoldMirrorPlan(7, True)
    assert manufacturing_api.plan_operator_fold_mirror_target(
        rows, 3, "angle", is_box_body=True,
    ) == OperatorFoldMirrorPlan(6, True)
    assert manufacturing_api.plan_operator_fold_mirror_target(
        rows, 0, "len", is_box_body=True,
    ) == OperatorFoldMirrorPlan(None, True)
    assert manufacturing_api.plan_operator_fold_mirror_target(
        rows, 3, "len", is_box_body=False,
    ) == OperatorFoldMirrorPlan(None, False)
    assert manufacturing_api.plan_operator_fold_mirror_target is plan_operator_fold_mirror_target
    with pytest.raises(FrozenInstanceError):
        manufacturing_api.plan_operator_fold_mirror_target(
            rows, 3, "len", is_box_body=True,
        ).target_index = 0
    assert rows == original


def test_engine_legacy_mirror_is_allowed_only_between_unkeyed_pieces():
    source = ({"len": 10}, {"len": 15}, {"len": 15}, {"len": 10})
    assert plan_operator_fold_mirror_target(
        source, 0, "len", is_box_body=True,
    ) == OperatorFoldMirrorPlan(None, False)
    keyed = source[:-1] + ({"len": 10, "phase6_key": "fw_right"},)
    assert plan_operator_fold_mirror_target(
        keyed, 0, "len", is_box_body=True,
    ) == OperatorFoldMirrorPlan(None, True)
    assert cabinet_family_policy.box_body_symmetry_allowed("金庫型") is True
    assert cabinet_family_policy.box_body_symmetry_allowed("受電箱") is False


class _Var:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


def test_tk_free_gui_save_reads_operator_fields_and_commits_one_engine_result(monkeypatch):
    originals = [
        {"len": 22, "angle": 90, "phase6_key": "fw_left"},
        {"len": 25, "phase6_key": "d_left"},
    ]
    active = {"X": deepcopy(originals)}
    state = SimpleNamespace(
        phase6_thickness=2.0, phase6_fold_ui_vault_key="箱身",
        profiles_vault={},
    )
    holder = SimpleNamespace(
        controls=(
            {"len": _Var(17), "angle": _Var(-90)},
            {"len": _Var(31)},
        ),
        state=state,
        get_active_dict=lambda: active,
        _active_profile_key=lambda _: "X",
    )
    calls = []
    real = manufacturing_api.commit_operator_fold_editor_rows

    def recording(old, edits, thickness):
        calls.append((deepcopy(old), deepcopy(edits), thickness))
        return real(old, edits, thickness)

    monkeypatch.setattr(manufacturing_api, "commit_operator_fold_editor_rows", recording)
    Phase6BendingUI.save(holder)
    assert len(calls) == 1
    assert calls[0][1] == [{"angle": -90, "len": 17}, {"len": 31}]
    assert active["X"] is state.profiles_vault["箱身"]
    assert tuple(engine_segment_length_to_ui(row) for row in active["X"]) == (17, 31)
    assert originals[0]["len"] == 22


def test_source_boundary_has_no_gui_mfg_symmetry_table_or_bend_topology_compute():
    source = inspect.getsource(Phase6BendingUI.save)
    mirror = inspect.getsource(Phase6BendingUI.apply_mirror)
    assert "manufacturing_api.commit_operator_fold_editor_rows(" in source
    assert "manufacturing_api.plan_operator_fold_mirror_target(" in mirror
    assert "apply_outside_dimension_compensation(" not in source
    assert "ui_segment_length_to_engine(" not in source
    assert '"zl1": "zr1"' not in mirror
    assert '"fw_left": "fw_right"' not in mirror
    assert "legacy_idx" not in mirror
    engine = Path(__file__).resolve().parents[1] / "ae_engine" / "operator_fold_editor.py"
    raw = engine.read_text(encoding="utf-8")
    assert "from phase6_" not in raw
    assert "gui_modules" not in raw
    assert "tkinter" not in raw
