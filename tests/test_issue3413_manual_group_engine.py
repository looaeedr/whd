"""#3413 real Engine-source MARKING groups and original first-sheet gates.

The four numerical points are user-approved coordinates in fixed flat-UV mm:
center=(100,100), X/Y=40/30, top-right local offset=(+3,+1).
After CCW 90 degrees, mirror about the fixed vertical axis x=100.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.operator_manual_marking_groups import source_group
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction
from phase6_project_file import PROJECT_SCHEMA, write_project, read_project
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet, _mark
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _part_spec


def _group(actual_sheet, **kw):
    _source, _render, ctx, _point, _angle = actual_sheet
    return api.create_physical_manual_marking_group(
        "base_plate", ctx, (),
        kind=kw.pop("kind", "quad_l"), center=kw.pop("center", Vec2(100, 100)),
        arm_x=kw.pop("arm_x", 12), arm_y=kw.pop("arm_y", 12),
        spacing_x=kw.pop("spacing_x", 40), spacing_y=kw.pop("spacing_y", 30),
        **kw,
    )


def _points(group):
    return dict(api.group_member_world_points(group))


def _validated_change(actual_sheet, group, **changes):
    _source, _render, ctx, _point, _angle = actual_sheet
    return api.edit_physical_manual_group(
        group, part_key="base_plate", context=ctx,
        existing_features=(group,), **changes,
    )


def test_four_corner_local_offsets_are_not_spacing_and_survive_transform(actual_sheet):
    group = _group(actual_sheet)
    assert api.is_manual_group(group) and api.is_manual_mark(group)
    assert group.points == ()  # NEVER render a group-center ink line
    assert len(group.layered_profiles) == 8
    assert tuple(_points(group)) == (
        "bottom_left", "bottom_right", "top_left", "top_right")
    # User-authorized test: all coordinates are actual group member corner
    # positions, not line midpoints or another guessed enclosure center.
    assert _points(group)["top_right"] == Vec2(120, 115)
    changed = _validated_change(
        actual_sheet, group, member_id="top_right", offset_x=3, offset_y=1,
    )
    stable_id = api.group_parameters(changed)["group_id"]
    member_ids = tuple(x[0] for x in api.group_parameters(changed)["members"])
    assert _points(changed)["top_right"] == Vec2(123, 116)
    resized = _validated_change(
        actual_sheet, changed, spacing_x=60, spacing_y=50,
    )
    assert _points(resized)["top_right"] == Vec2(133, 126)
    rotated = _validated_change(actual_sheet, resized, angle=90)
    assert _points(rotated)["top_right"].x == pytest.approx(74)
    assert _points(rotated)["top_right"].y == pytest.approx(133)
    reflected = _validated_change(actual_sheet, rotated, mirror_vertical=True)
    assert _points(reflected)["top_right"].x == pytest.approx(126)
    assert _points(reflected)["top_right"].y == pytest.approx(133)
    assert tuple(x[0] for x in api.group_parameters(reflected)["members"]) == member_ids
    assert api.group_parameters(reflected)["group_id"] == stable_id
    assert api.group_parameters(reflected)["members"][-1] == ("top_right", 3.0, 1.0)
    # Mirror is the vertical fixed-flat-UV axis x=100: x' = 200-x.
    for member_id, before in _points(rotated).items():
        after = _points(reflected)[member_id]
        assert after.x == pytest.approx(200-before.x)
        assert after.y == pytest.approx(before.y)
    # The same Engine form must still be a valid editable group after pose.
    assert api.group_parameters(reflected)["kind"] == "quad_l"
    assert source_group(reflected)[0] == "quad_l"


@pytest.mark.parametrize("kind,expected_arms", [
    ("cross", 2), ("l", 2), ("pair_l", 4), ("quad_l", 8),
])
def test_one_atomic_profile_per_tool_and_real_ink_only(actual_sheet, kind, expected_arms):
    group = _group(actual_sheet, kind=kind)
    assert len(group.layered_profiles) == expected_arms
    assert len(source_group(group)[2]) == expected_arms
    assert all(layer == "MARKING" and closed is False and len(points) == 2
               for layer, points, closed in group.layered_profiles)
    assert group.points == ()
    _source, render, ctx, _, _ = actual_sheet
    rendered = api.with_physical_sheet_features("base_plate", render, (group,))
    actual = [row for row in rendered.scene.primitives if row.layer == "MARKING"]
    assert len(actual) == expected_arms
    assert all(isinstance(row, PolylinePrimitive) and
               row.semantic_id == api.MANUAL_MARK_SOURCE for row in actual)
    assert api.propose_operator_physical_sheet_hole_features(
        "base_plate", ctx, (group,)) == (group,)


def test_any_angle_keeps_two_arms_and_same_member_ids(actual_sheet):
    group = _group(actual_sheet, kind="l", arm_x=16, arm_y=9,
                   spacing_x=0, spacing_y=0)
    rotated = _validated_change(actual_sheet, group, angle=37.5)
    _kind, _pattern, full = source_group(rotated)
    assert tuple(x.length for x in full) == pytest.approx((16, 9))
    assert tuple(_points(rotated)) == ("corner",)
    assert _points(rotated)["corner"] == Vec2(100, 100)
    assert api.group_parameters(rotated)["group_id"] == api.group_parameters(group)["group_id"]


def test_duplicate_whole_group_rejected_partial_overlap_allowed(actual_sheet):
    _source, _render, context, _, _ = actual_sheet
    first = _group(actual_sheet, kind="l", spacing_x=0, spacing_y=0)
    duplicate = _group(actual_sheet, kind="l", spacing_x=0, spacing_y=0)
    with pytest.raises(ValueError, match="重複"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", context, (first, duplicate),
        )
    shifted = _group(actual_sheet, kind="l", center=Vec2(102, 100),
                     spacing_x=0, spacing_y=0)
    assert api.propose_operator_physical_sheet_hole_features(
        "base_plate", context, (first, shifted),
    ) == (first, shifted)


def test_pair_and_four_corner_require_explicit_spacing(actual_sheet):
    with pytest.raises(ValueError, match="SPACING_X_REQUIRED"):
        _group(actual_sheet, kind="pair_l", spacing_x=0)
    with pytest.raises(ValueError, match="SPACING_Y_REQUIRED"):
        _group(actual_sheet, kind="quad_l", spacing_y="")
    # Single L and cross have a corner/intersection placement, not fake pair X/Y.
    for kind in ("l", "cross"):
        group = _group(actual_sheet, kind=kind, spacing_x=0, spacing_y=0)
        assert api.group_parameters(group)["spacing_x"] == 0


def test_group_dash_blank_hole_rejected_and_stale_saved_ink_rejected(actual_sheet):
    _source, render, ctx, _, _ = actual_sheet
    group = _group(
        actual_sheet, kind="l", pattern="dashed", dash=2, gap=8,
        spacing_x=0, spacing_y=0,
    )
    _kind, _pattern, strokes = source_group(group)
    first = strokes[0]
    assert first.length == pytest.approx(12)
    # At 4mm from start: 2mm visible ink followed by 8mm gap.
    point = first.interpolate(4)
    hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(point.x, point.y), layer="CUTTING",
    )
    with pytest.raises(ValueError, match="完整筆畫"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", ctx, (group, hole),
        )
    with pytest.raises(ValueError, match="完整筆畫"):
        api.with_physical_sheet_features("base_plate", render, (group, hole))
    # No accidental editing of ink-only source without updating group contract.
    damaged = replace(group, layered_profiles=group.layered_profiles[:-1])
    with pytest.raises(ValueError, match="MANUAL_GROUP_INK_CHANGED"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", ctx, (damaged,),
        )


def test_group_is_one_delete_undo_identity_and_old_line_still_works(actual_sheet):
    original = _group(actual_sheet)
    rows = [original]
    session = Phase6HoleEditorSession("base_plate", rows)
    session.execute(HoleEditorAction.select(0))
    session.execute(HoleEditorAction.delete_selected())
    assert not rows  # no exposed member deletion, remove entire group
    session.execute(HoleEditorAction.undo())
    assert rows == [original]
    updated = _validated_change(actual_sheet, original, member_id="top_right",
                                offset_x=3, offset_y=1)
    session.execute(HoleEditorAction.select(0))
    session.execute(HoleEditorAction.replace_selected_committed(updated))
    session.execute(HoleEditorAction.undo())
    assert rows == [original]
    legacy = _mark(actual_sheet)
    assert api.is_manual_mark(legacy) and not api.is_manual_group(legacy)
    assert tuple(x[0] for x in legacy.source_params) == ("pattern", "dash", "gap")


def test_real_saved_project_dxf_3d_and_reeditable_group(actual_sheet, tmp_path):
    source, base, context, _, _ = actual_sheet
    group = _group(actual_sheet, pattern="dashed", dash=4, gap=4)
    group = _validated_change(
        actual_sheet, group, member_id="top_right", offset_x=3, offset_y=1,
    )
    group = _validated_change(actual_sheet, group, spacing_x=60, spacing_y=50)
    group = _validated_change(actual_sheet, group, angle=90)
    group = _validated_change(actual_sheet, group, mirror_vertical=True)
    source["part_features"] = {"base_plate": [group]}
    source["workspace"] = dict(source.get("workspace") or {})
    source["workspace"]["part_features"] = {"base_plate": [group]}
    saved = write_project(
        tmp_path / "3413-four-corner-l.p6fold",
        {"schema": PROJECT_SCHEMA, "snapshot": source},
    )
    reloaded = read_project(saved)["snapshot"]
    original_id = api.group_parameters(group)["group_id"]
    loaded = reloaded["part_features"]["base_plate"][0]
    assert loaded == group
    assert api.group_parameters(loaded)["group_id"] == original_id
    assert _points(loaded)["top_right"].x == pytest.approx(126)
    assert _points(loaded)["top_right"].y == pytest.approx(133)
    # Editing persisted member offsets uses the SAME API and IDs.
    amended = api.edit_physical_manual_group(
        loaded, member_id="top_right", offset_x=4,
    )
    assert api.group_parameters(amended)["group_id"] == original_id
    assert api.group_parameters(amended)["members"][-1] == ("top_right", 4.0, 1.0)

    _values, spec = _part_spec(reloaded)
    spec = replace(spec, features=(loaded,))
    c = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    canonical = api.build_part_render_data(spec, c)
    assert canonical.material.equals(base.material)
    assert not any(row.layer == "MARKING" for row in base.scene.primitives)
    ink = [row for row in canonical.scene.primitives if row.layer == "MARKING"]
    assert len(ink) == len(group.layered_profiles)
    assert all(row.semantic_id == api.MANUAL_MARK_SOURCE for row in ink)
    profiles = api.build_standard_part_fold_profiles(reloaded, "base_plate")
    paths = api.project_independent_scene_annotation_paths(
        canonical.scene, profiles["X"], profiles["Y"], canonical.fold_guides,
    )
    assert len([points for layer, points in paths if layer == "MARKING"]) == len(ink)
    dxf = tmp_path / "3413-four-corner-production-normal.dxf"
    written = api.save_part_render_data_dxf(
        canonical, dxf, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(canonical, written).ok
    document = ezdxf.readfile(dxf)
    assert document.header["$INSUNITS"] == 4
    layers = {row.dxf.layer for row in document.modelspace()}
    assert {"CUTTING", "BEND", "MARKING"} <= layers
    actual_marks = [e for e in document.modelspace() if e.dxf.layer == "MARKING"]
    assert len(actual_marks) == len(ink)
    assert document.layers.get("MARKING").dxf.linetype == "CONTINUOUS"
    # Crucially neither primary group center nor hidden dash gaps are DXF ink.
    assert all(e.dxftype() == "LWPOLYLINE" and len(e) == 2 for e in actual_marks)
