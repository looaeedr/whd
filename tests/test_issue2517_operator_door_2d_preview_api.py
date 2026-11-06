"""#2517 physical Door 2D preview facts belong to public Engine API."""
from pathlib import Path
from types import SimpleNamespace

from ae_engine import manufacturing_api
from ae_engine.operator_door_2d_preview import (
    project_operator_door_divider_frame_preview,
    project_operator_door_indicator_guides,
)
from ae_engine.sheetmetal_features import (
    DoorIndicatorContext, measure_door_indicator_position,
    resolve_door_indicator_dimension_guides, resolve_door_indicator_layout,
)
from ae_engine.sheetmetal_geometry import Vec2


def test_public_engine_single_door_indicator_matches_original_physical_dimensions():
    spec = SimpleNamespace(use_box_distance=True, frame_edges={
        "left": True, "top": True,
    })
    values = dict(
        t=2.0, fw=29.0, door_gap_w=3.5, door_gap_h=3.5,
        door_fold_l=20.0, door_fold_b=20.0,
    )
    finished = (700.0, 1250.0)
    groups = (2, 1)
    actual = manufacturing_api.project_operator_door_indicator_guides(
        finished, values, groups, spec, offset_x=7.0, offset_y=-4.0,
    )
    context = DoorIndicatorContext(
        finished_width=finished[0], finished_height=finished[1],
        left_fold=values["door_fold_l"], bottom_fold=values["door_fold_b"],
    )
    layout = resolve_door_indicator_layout(context, groups, Vec2(7.0, -4.0))
    position = measure_door_indicator_position(
        layout, context, frame_width=29.0, thickness=2.0,
        use_box_distance=True, frame_edges=spec.frame_edges,
        gap_w=3.5, gap_h=3.5,
    )
    x, y = resolve_door_indicator_dimension_guides(position)
    assert actual == (context, layout, x, y)
    assert manufacturing_api.project_operator_door_indicator_guides is project_operator_door_indicator_guides


def test_empty_and_bad_indicator_has_no_preview_fallback_to_fake_holes():
    spec = SimpleNamespace(use_box_distance=False, frame_edges=None)
    values = dict(t=2.0, fw=29.0, door_gap_w=3.5, door_gap_h=3.5,
                  door_fold_l=15.0, door_fold_b=15.0)
    assert project_operator_door_indicator_guides((500.0, 800.0), values, (), spec) == (None, None, None, None)
    assert project_operator_door_indicator_guides((500.0, 800.0), values, (True,), spec) == (None, None, None, None)


def test_headless_door_divider_frame_projection_returns_original_empty_shape_on_invalid_topology():
    values = dict(w=800, h=1600, d=350, t=2.0, fw=29.0)
    state = dict(model="金庫型", w=800, h=1600, door_layout_columns=[])
    actual = project_operator_door_divider_frame_preview(
        state, ((800, (1600,)),), values, layout_scope="main", model_name="金庫型",
    )
    assert set(actual) == {"total_w", "total_h", "dividers", "frames"}
    assert actual["total_w"] == 800
    assert actual["total_h"] == 1600
    assert isinstance(actual["dividers"], tuple)
    assert isinstance(actual["frames"], tuple)
    assert manufacturing_api.project_operator_door_divider_frame_preview is project_operator_door_divider_frame_preview


def test_gui_no_longer_imports_or_calculates_canonical_door_preview_geometry():
    gui = Path("gui_modules/application/render_snapshots.py").read_text(encoding="utf-8")
    assert "manufacturing_api.project_operator_door_divider_frame_preview(" in gui
    assert "manufacturing_api.project_operator_door_indicator_guides(" in gui
    for forbidden in ("derive_box_body_dividers(", "derive_inner_door_frame_sets(",
                      "resolve_assembly_placement(", "measure_door_indicator_position(",
                      "resolve_door_indicator_layout("):
        assert forbidden not in gui
