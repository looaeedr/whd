"""#2517: operator Fold, Corner and Assembly source belongs to public Engine."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import (
    manufacturing_api,
    operator_normalize_corner_selection,
    project_operator_fold_editor_angle,
)
from ae_engine.assembly_intent import normalize_assembly_intent_id
from ae_engine.sheetmetal_corner_policy import normalize_corner_selection
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
import phase6_endcap_semantics as endcap_gui
import phase6_fold_profiles as fold_gui


@pytest.mark.parametrize("raw, expected", [
    (90, -90), (-90, 90), ("90", -90), (-90.0, 90),
    (45.5, 45.5), (-30, -30), (0, 0), ("-45.5", -45.5),
])
def test_fold_angle_engine_gui_bidirectional_parity(raw, expected):
    assert project_operator_fold_editor_angle is manufacturing_api.project_operator_fold_editor_angle
    assert project_operator_fold_editor_angle(raw) == expected
    assert fold_gui.engine_angle_to_ui(raw) == expected
    assert fold_gui.ui_angle_to_engine(raw) == expected
    assert project_operator_fold_editor_angle(expected) == float(raw)


@pytest.mark.parametrize("bad", [None, True, False, "bad", "", float("nan"), float("inf"), float("-inf")])
def test_fold_angle_bad_source_rejected_not_silently_converted_to_zero(bad):
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        manufacturing_api.project_operator_fold_editor_angle(bad)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        fold_gui.ui_angle_to_engine(bad)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        fold_gui.engine_angle_to_ui(bad)


def test_gui_fold_angle_is_only_engine_forwarding(monkeypatch):
    calls = []
    def public(raw):
        calls.append(raw)
        return 1234
    monkeypatch.setattr(manufacturing_api, "project_operator_fold_editor_angle", public)
    assert fold_gui.ui_angle_to_engine("a") == 1234
    assert fold_gui.engine_angle_to_ui("b") == 1234
    assert calls == ["a", "b"]


def test_existing_fold_commit_uses_same_engine_angle_without_mutating_inputs():
    old = [{"len": 27, "angle": 90, "phase6_key": "zl1"}, {"len": 150, "phase6_key": "core"}]
    rows = [{"len": 26, "angle": -90}, {"len": 151}]
    before_old, before_rows = deepcopy(old), deepcopy(rows)
    result = manufacturing_api.commit_operator_fold_editor_rows(old, rows, 2.0)
    assert result[0]["angle"] == project_operator_fold_editor_angle(rows[0]["angle"])
    assert result[0]["angle"] == 90
    assert all(row["len"] > 0 for row in result)
    assert old == before_old and rows == before_rows
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        manufacturing_api.commit_operator_fold_editor_rows(old, [
            {"len": 26, "angle": float("nan")}, {"len": 151},
        ], 2.0)
    assert old == before_old and rows == before_rows


@pytest.mark.parametrize("value", ["INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP_OVERLAY", "嵌入", CornerTypeId.OVERLAY])
def test_assembly_gui_same_registry_normalization_as_engine(value):
    canonical = normalize_assembly_intent_id(value)
    assert endcap_gui.assembly_intent_value(value) == canonical
    assert endcap_gui.assembly_intent_value(manufacturing_api.normalize_assembly_type(value)) == canonical


def test_assembly_invalid_input_fails_without_input_mutation():
    bad = {"assembly_type": "bogus"}
    before = deepcopy(bad)
    with pytest.raises(ValueError, match="unsupported Assembly Intent"):
        endcap_gui.assembly_intent_value(bad["assembly_type"])
    assert bad == before


def test_corner_legacy_mapping_is_original_engine_callable_and_gui_uses_public_api():
    assert operator_normalize_corner_selection is normalize_corner_selection
    assert manufacturing_api.operator_normalize_corner_selection is normalize_corner_selection
    for rotation in (0, 1, 2, 3):
        old = CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=rotation)
        frozen = deepcopy(old)
        assert operator_normalize_corner_selection(old) == normalize_corner_selection(old)
        assert old == frozen
    bridge = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    function = bridge.split("def _phase6_corner_parameter_summary(selection):", 1)[1].split("\ndef ", 1)[0]
    assert "manufacturing_api.operator_normalize_corner_selection(selection)" in function
    assert "selection = normalize_corner_selection(selection)" not in function
    semantics = Path("phase6_endcap_semantics.py").read_text(encoding="utf-8")
    assert "from ae_engine.assembly_intent import" not in semantics
    fold = Path("phase6_fold_profiles.py").read_text(encoding="utf-8")
    assert "angle = -angle" not in fold
