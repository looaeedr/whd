"""#2517 multi-Door cell editor consumes the same headless finished-face API."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, door_material_frame_width
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import DoorPartSpec
from ae_engine.part_dimension_projection import door_part_projections
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges, build_finished_reference_guide,
)
from ae_engine.sheetmetal_features import feature_surface_from_structural_result
import gui


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_public_family_door_fw_is_same_owner_as_manufacturing(model):
    assert door_material_frame_width is manufacturing_api.door_material_frame_width
    expected = family_policy.door_material_frame_width(
        model, frame_width=29.0, thickness=2.0,
    )
    assert door_material_frame_width(
        model, frame_width=29.0, thickness=2.0,
    ) == expected


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_cell_finished_size_matches_existing_engine_layout_projection(model):
    snapshot = {
        "model": model, "w": 500, "h": 600, "t": 2.0, "fw": 29.0,
        "multi_door_enabled": True,
        "door_layout_columns": ((500.0, (300.0, 300.0)),),
        "door_gap_w": 3.5, "door_gap_h": 3.5,
    }
    rows = door_part_projections(snapshot)
    assert len(rows) == 2
    for row in rows:
        spec = DoorPartSpec(
            width=row.start_width, height=row.start_height,
            thickness=2.0, frame_width=29.0, model_name=model,
            gap_w=3.5, gap_h=3.5, frame_edges=row.frame_edges,
        )
        assert manufacturing_api.door_finished_face_size(spec) == pytest.approx(
            (row.formed_width, row.formed_height),
        )


def test_door_editor_forwards_exact_cell_spec_and_receives_engine_dimensions(monkeypatch):
    captured = {}
    spec = DoorPartSpec(width=500, height=300, thickness=2,
                        frame_width=25, model_name="受電箱", gap_w=3.5, gap_h=3.5)
    cell = SimpleNamespace(column_index=0, row_index=0, edges=DoorFrameEdges(),
                           start_width=500.0, start_height=300.0)
    class Var:
        def set(self, value):
            captured["selected"] = value
    values = {
        "w": 500, "h": 600, "d": 200, "t": 2, "fw": 25,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 20, "door_fold_b": 20,
    }
    def projection(physical_result, request, *, baseline_scene, baseline_status):
        assert request is spec and physical_result is result
        captured["engine_called"] = True
        return SimpleNamespace(
            surface="face", width=result.width, height=result.height,
            reference_guide=(321.0, 222.0),
            door_indicator_context=SimpleNamespace(
                finished_width=321.0, finished_height=222.0,
            ),
            door_frame_edges=cell.edges,
            baseline_scene=baseline_scene, baseline_status=baseline_status,
        )
    monkeypatch.setattr(
        manufacturing_api, "project_operator_hole_editor_door_cell", projection,
    )
    monkeypatch.setattr(gui._door_layout_host_adapter, "_receiving_live_door_layout_source",
                        lambda host: None)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        pytest.fail("unexpected editor error: " + str(args)))
    result = SimpleNamespace(width=520.0, height=315.0)
    host = SimpleNamespace(
        door_layout_selected_var=Var(),
        get_selected_door_layout_cell=lambda: cell,
        _door_layout_cell_key=lambda _: "0:0",
        get_float_values=lambda: dict(values),
        _door_layout_cell_result=lambda *args: result,
        _door_layout_part_spec=lambda *args: spec,
        door_layout_features={}, door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        _door_layout_indicator_state_for_key=lambda key: {},
        _door_layout_baseline_scene=lambda *args: (None, "baseline"),
        _open_unified_hole_editor=lambda *args, **kw:
            captured.update({"editor_args": args, "editor_kwargs": kw}),
        _apply_multi_door_indicator_state=lambda *args: None,
        draw_door_layout_overview=lambda: None,
    )
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, 0, 0)
    assert captured["selected"] == "0:0"
    assert captured["engine_called"]
    assert captured["editor_kwargs"]["reference_guide"] == (321.0, 222.0)
    assert captured["editor_args"][2:5] == ("face", 520.0, 315.0)
    context = captured["editor_kwargs"]["door_indicator_context"]
    assert (context.finished_width, context.finished_height) == (321.0, 222.0)
    assert captured["editor_kwargs"]["door_frame_edges"] == cell.edges


def test_gui_has_no_duplicate_door_finished_size_calculation():
    method = inspect.getsource(gui.Phase6ApplicationHost.open_door_layout_cell_editor)
    helper = inspect.getsource(gui.Phase6ApplicationHost._door_material_frame_width)
    assert "manufacturing_api.project_operator_hole_editor_door_cell(" in method
    assert "self._door_layout_part_spec(cell, val)" in method
    assert "manufacturing_api.door_finished_face_size(door_spec)" not in method
    assert "feature_surface_from_structural_result(" not in method
    assert "build_finished_reference_guide(" not in method
    assert "ae.calculate_door_finished_size(" not in method
    assert "manufacturing_api.door_material_frame_width(" in helper
    assert "cabinet_family_policy.door_material_frame_width(" not in helper


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_selected_door_cell_hole_editor_geometry_matches_original_engine_source(model):
    edges = DoorFrameEdges(left=True, right=False, top=True, bottom=True)
    operator = {
        "t": 2.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 15.0,
        "door_fold_t": 15.0, "door_fold_b": 15.0,
    }
    result = manufacturing_api.project_operator_door_cell_result(
        operator, cell_width=500.0, cell_height=600.0, frame_edges=edges,
        material_frame_width=manufacturing_api.door_material_frame_width(
            model, frame_width=29.0, thickness=2.0,
        ),
    )
    spec = DoorPartSpec(
        width=500.0, height=600.0, thickness=2.0,
        frame_width=29.0, model_name=model, gap_w=3.5, gap_h=3.5,
        fold_left=19.0, fold_right=15.0, fold_top=15.0, fold_bottom=15.0,
        frame_edges=edges,
    )
    token = object()
    editor = manufacturing_api.project_operator_hole_editor_door_cell(
        result, spec, baseline_scene=token, baseline_status="真正基準來源",
    )
    finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
    expected_guide = build_finished_reference_guide(
        "door", result, finished_width=finished_w, finished_height=finished_h,
    )
    expected_surface = feature_surface_from_structural_result("door", result)
    assert editor.width == result.width and editor.height == result.height
    assert editor.reference_guide == expected_guide
    assert editor.surface.polygon.bounds == expected_surface.polygon.bounds
    assert editor.door_frame_edges == edges
    assert editor.door_indicator_context.finished_width == finished_w
    assert editor.door_indicator_context.finished_height == finished_h
    assert editor.door_indicator_context.left_fold == 19.0
    assert editor.door_indicator_context.bottom_fold == 15.0
    assert editor.baseline_scene is token
    assert editor.baseline_status == "真正基準來源"


def test_door_cell_hole_editor_rejects_missing_physical_fold_in_source():
    incomplete = DoorPartSpec(
        width=500.0, height=600.0, thickness=2.0, frame_width=29.0,
        model_name="受電箱", gap_w=3.5, gap_h=3.5,
    )
    with pytest.raises(ValueError, match="門格 Hole Editor"):
        manufacturing_api.project_operator_hole_editor_door_cell(
            object(), incomplete,
        )
