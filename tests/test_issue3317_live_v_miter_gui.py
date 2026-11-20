"""#3317: real fifth GUI CHECK from canonical BEND and authored Fold, no DXF."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.contracts import DoorPartSpec, EndCapPartSpec, FoldProfileSegment
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


def _physical_four_corner_scene():
    points = (Vec2(0, 0), Vec2(200, 0), Vec2(200, 200), Vec2(0, 200))
    outline = PolylinePrimitive(points, "CUTTING", closed=True)
    bends = (
        LinePrimitive(Vec2(20, 20), Vec2(20, 180), "BEND"),
        LinePrimitive(Vec2(180, 20), Vec2(180, 180), "BEND"),
        LinePrimitive(Vec2(20, 20), Vec2(180, 20), "BEND"),
        LinePrimitive(Vec2(20, 180), Vec2(180, 180), "BEND"),
    )
    scene = DrawingScene([outline, *bends])
    render = PartRenderData(scene=scene, material=Polygon([(p.x, p.y) for p in points]))
    return render, tuple(scene.primitives)


def _endcap_spec(second_angle=-75.5, *, first_angle=-90):
    return EndCapPartSpec(
        width=200, depth=200, thickness=2, frame_width=20,
        fold_profile_x=(
            FoldProfileSegment(20, angle=first_angle),
            FoldProfileSegment(160, angle=-90),
            FoldProfileSegment(20),
        ),
        fold_profile_y=(
            FoldProfileSegment(20, angle=second_angle),
            FoldProfileSegment(160, angle=-90),
            FoldProfileSegment(20),
        ),
    )


def test_fifth_check_uses_actual_bends_and_fractional_other_fold_angle():
    render, original = _physical_four_corner_scene()
    spec = _endcap_spec()
    result = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left",
    )
    assert result.part_key == "head"
    assert result.corner_key == "bottom_left"
    assert result.second_fold_angle_deg == pytest.approx(75.5)
    assert result.first_flange_height_mm == pytest.approx(20)
    assert result.second_flange_height_mm == pytest.approx(20)
    assert result.manufacturing_status == "V_MITER_GUI_CHECK_ONLY_UNCERTIFIED"
    assert result.ideal.formed_contact_length_mm > 0
    assert all(row.layer == "CHECK" for row in result.check_scene.primitives)
    assert len(result.check_scene.primitives) == 2
    assert tuple(render.scene.primitives) == original


@pytest.mark.parametrize("corner", ("bottom_left", "bottom_right", "top_left", "top_right"))
def test_all_four_physical_corners_can_be_checked_without_mutating_original(corner):
    render, original = _physical_four_corner_scene()
    result = api.project_operator_v_miter_live_corner_check(
        _endcap_spec(second_angle=-90), render, corner,
    )
    assert result.corner_key == corner
    assert all(line.layer == "CHECK" for line in result.check_scene.primitives)
    assert tuple(render.scene.primitives) == original


def test_same_part_door_uses_existing_fixed_four_fold_source_not_extra_gui_angles():
    render, _ = _physical_four_corner_scene()
    spec = DoorPartSpec(
        width=200, height=200, thickness=2, frame_width=20,
        fold_left=20, fold_right=20, fold_top=20, fold_bottom=20,
    )
    result = api.project_operator_v_miter_live_corner_check(
        spec, render, "top_right",
    )
    assert result.part_key == "door"
    assert result.second_fold_angle_deg == 90
    assert result.ideal.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"


def test_paired_and_split_corner_drafts_never_mutate_certified_corner_type():
    baseline = {"head": {"bottom_left": "V_MITER_CHECK"}}
    same = {"top": True, "bottom": True}
    before = deepcopy(baseline)
    updated = api.change_operator_v_miter_gui_choice(
        baseline, "head", "bottom", same, enabled=True,
    )
    assert updated["head"] == {
        "bottom_left": "V_MITER_CHECK",
        "bottom_right": "V_MITER_CHECK",
    }
    assert baseline == before
    one = api.change_operator_v_miter_gui_choice(
        updated, "head", "bottom_right",
        {"top": True, "bottom": False}, enabled=False,
    )
    assert one["head"] == {"bottom_left": "V_MITER_CHECK"}
    assert updated["head"]["bottom_right"] == "V_MITER_CHECK"
    assert api.change_operator_v_miter_gui_choice(
        one, "head", "bottom_left", same, enabled=False,
    ) == {}
    with pytest.raises(GeometryError, match="SPLIT"):
        api.change_operator_v_miter_gui_choice(
            one, "head", "bottom", {"top": True, "bottom": False}, enabled=True,
        )


@pytest.mark.parametrize("bad", (
    {"head": {"bottom_left": "CERTIFIED"}},
    {"head": {"bottom": "V_MITER_CHECK"}},
    {"head": {"bottom_left": True}},
    {"box_body": {"bottom_left": "V_MITER_CHECK"}},
    [("head", "bottom_left")],
))
def test_saved_check_schema_rejects_forgery_and_unknown_physical_selection(bad):
    with pytest.raises((GeometryError, ValueError)):
        api.normalize_operator_v_miter_gui_choices(bad)


def test_v_check_roundtrip_preserves_physical_selection_not_fake_cutting(tmp_path):
    selected = api.change_operator_v_miter_gui_choice(
        {}, "head", "bottom", {"top": True, "bottom": True}, enabled=True,
    )
    saved = write_project(tmp_path / "fifth_check.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "自訂", "w": 500, "h": 600, "d": 300, "t": 2,
            "v_miter_gui_check_corners": selected,
        },
    })
    reread = read_project(saved)
    assert api.normalize_operator_v_miter_gui_choices(
        reread["snapshot"]["v_miter_gui_check_corners"],
    ) == selected
    assert "corner_state" not in reread["snapshot"]
    with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
        api.require_no_operator_v_miter_gui_check_for_export(reread["snapshot"])
    api.require_no_operator_v_miter_gui_check_for_export({"v_miter_gui_check_corners": {}})


def test_wrong_angle_direction_or_missing_real_source_fails_closed():
    render, original = _physical_four_corner_scene()
    with pytest.raises(GeometryError, match="OPPOSITE_FOLD_SENSE"):
        api.project_operator_v_miter_live_corner_check(
            _endcap_spec(second_angle=75.5), render, "bottom_left",
        )
    with pytest.raises(GeometryError):
        api.project_operator_v_miter_live_corner_check(
            _endcap_spec(second_angle=-180), render, "bottom_left",
        )
    missing = PartRenderData(
        scene=DrawingScene([render.scene.primitives[0]]),
        material=render.material,
    )
    with pytest.raises(GeometryError, match="TWO_PHYSICAL_BENDS_REQUIRED"):
        api.project_operator_v_miter_live_corner_check(
            _endcap_spec(), missing, "bottom_left",
        )
    assert tuple(render.scene.primitives) == original


def test_gui_is_selectable_without_fifth_certified_corner_type_or_new_angle_field():
    gui = Path(__file__).parents[1].joinpath("gui_modules/parts/panels/assembly_corner.py")
    source = gui.read_text(encoding="utf-8")
    assert 'text="V 型斜接（試算）"' in source
    assert 'command=host.set_v_miter_gui_check_choice' in source
    assert "self._project_v_miter_gui_check_for_corner(part_key, target_key)" in source
    assert "draw_v_miter_gui_live_check(self, live)" in source
    host = Path(__file__).parents[1].joinpath("gui.py").read_text(encoding="utf-8")
    handler = host.split("def set_v_miter_gui_check_choice(self):")[1].split(
        "def create_corner_type_panel(", 1,
    )[0]
    assert "change_operator_v_miter_gui_choice" in handler
    assert "project_operator_v_miter_live_corner_check" in handler
    assert "operator_apply_manual_corner_selection" not in handler


def test_all_main_dxfs_and_direct_fold_designer_export_guard_v_selection():
    project = Path(__file__).parents[1]
    main_export = project.joinpath("gui_modules/project/export_actions.py").read_text(encoding="utf-8")
    direct_export = project.joinpath(
        "gui_modules/application/fold_designer_manufacturing_projection.py",
    ).read_text(encoding="utf-8")
    assert "require_no_operator_v_miter_gui_check_for_export" in main_export
    assert "require_no_operator_v_miter_gui_check_for_export" in direct_export
    for handler in ("export_selected_dxf", "_export_selected_parts", "_export_selected_resolved_parts"):
        excerpt = main_export.split(f"def {handler}(")[1].split("\n\ndef ", 1)[0]
        assert "require_no_operator_v_miter_gui_check_for_export" in excerpt
