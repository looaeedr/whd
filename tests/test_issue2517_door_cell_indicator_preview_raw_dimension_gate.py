"""#2517 Door cell indicator 2D cannot fabricate holes from invalid physical mm."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_door_cell_projection as owner
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def _state(mode="indicator"):
    return {
        "mode": mode, "layers": 1, "groups": [2, 2, 2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }


def _source():
    return {
        "cell_width": 420.0, "cell_height": 600.0,
        "frame_edges": DoorFrameEdges(), "family_model": "金庫型",
        "frame_width": 29.0, "thickness": 2.0,
        "gap_w": 3.5, "gap_h": 4.0,
        "fold_left": 15.0, "fold_bottom": 14.0,
    }


@pytest.mark.parametrize("part", ("indicator", "indicator_box"))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,bad", (
    ("cell_width", True), ("cell_height", "nan"),
    ("frame_width", True), ("frame_width", float("inf")),
    ("thickness", True), ("thickness", 0),
    ("gap_w", False), ("gap_h", float("nan")),
    ("fold_left", True), ("fold_bottom", "inf"),
))
def test_preview_omits_optional_physical_holes_on_bad_raw_dimensions(
    monkeypatch, part, family, field, bad,
):
    kwargs = _source()
    kwargs.update({field: bad, "family_model": family})
    before = deepcopy(kwargs)
    state = _state(part)
    original = deepcopy(state)
    calls = []
    monkeypatch.setattr(
        owner.ae, "calculate_door_finished_size",
        lambda *a, **k: calls.append((a, k)) or (400.0, 500.0),
    )
    result = api.project_operator_door_cell_features(
        object(), (), state, **kwargs,
    )
    assert result == [] and calls == []
    assert kwargs == before and state == original


@pytest.mark.parametrize("mode", ("indicator", "indicator_box"))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_valid_physical_source_keeps_existing_indicator_preview_geometry(mode, family):
    kwargs = _source()
    kwargs.update({
        "family_model": family, "frame_width": "29.0",
        "thickness": "2.125", "gap_w": "3.5",
        "gap_h": "4.0", "fold_left": "15.0", "fold_bottom": "14.0",
    })
    state = _state(mode)
    before = deepcopy((kwargs, state))
    projected = api.project_operator_door_cell_features(
        object(), (), state, **kwargs,
    )
    assert projected
    if mode == "indicator_box":
        assert len(projected) == 1
        assert projected[0].layer == "CUTTING"
        assert projected[0].source_type == "indicator_box_opening"
    assert (kwargs, state) == before


def test_invalid_optional_indicator_does_not_erase_separate_saved_features(monkeypatch):
    token = object()
    monkeypatch.setattr(owner, "feature_surface_from_structural_result",
                        lambda *a: object())
    monkeypatch.setattr(owner, "resolve_surface_features",
                        lambda *a: [token])
    monkeypatch.setattr(owner.ae, "calculate_door_finished_size",
                        lambda *a, **k: pytest.fail(
                            "invalid physical indicator passed to AE geometry"
                        ))
    kwargs = _source()
    kwargs["thickness"] = True
    assert api.project_operator_door_cell_features(
        object(), ["original-saved-feature"], _state("indicator_box"),
        **kwargs,
    ) == [token]


def test_disabled_indicator_preserves_legacy_preview_without_extra_dimensions():
    kwargs = _source()
    kwargs.update({"thickness": True, "frame_width": True})
    assert api.project_operator_door_cell_features(
        object(), (), _state("none"), **kwargs,
    ) == []
