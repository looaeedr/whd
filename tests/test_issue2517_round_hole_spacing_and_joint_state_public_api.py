# -*- coding: utf-8 -*-
"""#2517 Hole Editor spacing conversion and Fold Designer Joint state use public Engine."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_reference import (
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
)
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from gui_modules.editors.hole_editor_round_settings import _RoundHoleSettingsDialog


ROOT = Path(__file__).resolve().parents[1]


class Field:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.mark.parametrize("diameter_a,diameter_b,gap", (
    (20.0, 20.0, 0.0),
    (20.0, 20.0, 5.25),
    (20.0, 30.0, 12.5),
    (1.0, 2.0, 0.75),
))
def test_public_spacing_projection_is_exact_engine_owner_and_bidirectional(
    diameter_a, diameter_b, gap,
):
    assert api.operator_round_hole_center_distance_from_gap is circle_center_distance_from_gap
    assert api.operator_round_hole_gap_from_center_distance is circle_gap_from_center_distance
    assert ae_engine.operator_round_hole_center_distance_from_gap is circle_center_distance_from_gap
    assert ae_engine.operator_round_hole_gap_from_center_distance is circle_gap_from_center_distance
    assert {"operator_round_hole_center_distance_from_gap",
            "operator_round_hole_gap_from_center_distance"} <= set(ae_engine.__all__)
    center = api.operator_round_hole_center_distance_from_gap(
        gap, diameter_a, diameter_b,
    )
    assert center == circle_center_distance_from_gap(gap, diameter_a, diameter_b)
    assert api.operator_round_hole_gap_from_center_distance(
        center, diameter_a, diameter_b,
    ) == pytest.approx(gap)
    assert api.operator_round_hole_gap_from_center_distance(
        center, diameter_a, diameter_b,
    ) == circle_gap_from_center_distance(center, diameter_a, diameter_b)


def _gui_dialog():
    dialog = _RoundHoleSettingsDialog.__new__(_RoundHoleSettingsDialog)
    dialog.sync_guard = False
    dialog.selected_feature = type("CircleSeed", (), {"diameter": 20.0})()
    dialog.round_driver = Field("center")
    dialog.round_center = Field("30")
    dialog.round_gap = Field("10")
    return dialog


def test_gui_spacing_fields_use_engine_for_both_directions_and_reject_nonfinite(monkeypatch):
    dialog = _gui_dialog()
    calls = []
    previous = api.operator_round_hole_gap_from_center_distance

    def spy(*values):
        calls.append(values)
        return previous(*values)

    monkeypatch.setattr(api, "operator_round_hole_gap_from_center_distance", spy)
    dialog._sync_from_center()
    assert calls == [(30.0, 20.0, 20.0)]
    assert dialog.round_gap.get() == "10.00"
    assert dialog.round_driver.get() == "center"

    dialog.round_gap.set("8.50")
    dialog._sync_from_gap()
    assert dialog.round_center.get() == "28.50"
    assert dialog.round_driver.get() == "gap"

    before = (dialog.round_center.get(), dialog.round_gap.get(), dialog.round_driver.get())
    dialog.round_center.set("nan")
    dialog._sync_from_center()
    assert dialog.round_gap.get() == before[1]
    assert dialog.round_driver.get() == before[2]
    dialog.round_gap.set("-inf")
    dialog._sync_from_gap()
    assert dialog.round_center.get() == "nan"  # invalid text is not silently overwritten
    assert dialog.round_driver.get() == before[2]
    assert len(calls) == 1 and dialog.sync_guard is False


def test_gui_sources_have_no_private_spacing_or_joint_migration_calls():
    editor = ast.parse((ROOT / "gui_modules/editors/hole_editor_round_settings.py").read_text(encoding="utf-8"))
    state = ast.parse((ROOT / "gui_modules/application/fold_designer_composition_state.py").read_text(encoding="utf-8"))
    assert not [
        node for node in ast.walk(editor)
        if isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.sheetmetal_features"
        and any(item.name in {"circle_center_distance_from_gap", "circle_gap_from_center_distance"}
                for item in node.names)
    ]
    assert not [
        node for node in ast.walk(state)
        if isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.assembly_joint"
        and any(item.name == "migrate_legacy_snapshot_joints" for item in node.names)
    ]
    for tree, calls in (
        (editor, {"operator_round_hole_gap_from_center_distance",
                  "operator_round_hole_center_distance_from_gap"}),
        (state, {"migrate_operator_assembly_joint_snapshot"}),
    ):
        actual = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "manufacturing_api"
        }
        assert calls <= actual


def test_joint_migration_public_owner_source_immutability_and_future_schema_rejection():
    source = {
        "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_joint_schema_version": 0,
    }
    original = deepcopy(source)
    assert api.migrate_operator_assembly_joint_snapshot is migrate_legacy_snapshot_joints
    assert api.migrate_operator_assembly_joint_snapshot(source) == migrate_legacy_snapshot_joints(source)
    assert source == original
    invalid = {**source, "assembly_joint_schema_version": 999}
    before = deepcopy(invalid)
    with pytest.raises(ValueError, match="unsupported assembly joint schema version"):
        api.migrate_operator_assembly_joint_snapshot(invalid)
    assert invalid == before
