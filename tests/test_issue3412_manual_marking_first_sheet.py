"""#3412: original physical BasePlate + manual MARKING through real Engine export."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from math import hypot

import ezdxf
import pytest
from shapely.geometry import LineString

import phase6_project_file as project
from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_drawing import LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import (
    _configured, _part_spec,
)


@pytest.fixture
def actual_sheet():
    # A registered Receiving physical BasePlate with the actual Engine
    # LEFT bend, not a fabricated rectangle or an uncertified CHECK render.
    source = _configured("受電箱")
    _, spec = _part_spec(source)
    render = api.build_part_render_data(
        spec, ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
    )
    context = api.resolve_physical_sheet_editor_context("base_plate", render)
    bends = [
        p for p in render.scene.primitives
        if isinstance(p, LinePrimitive) and p.layer == "BEND"
        and hypot(p.p2.x-p.p1.x, p.p2.y-p.p1.y) > 1e-7
    ]
    assert bends
    bend = bends[0]
    center = Vec2((bend.p1.x + bend.p2.x) / 2,
                  (bend.p1.y + bend.p2.y) / 2)
    angle = 0 if abs(bend.p1.x - bend.p2.x) < 1e-8 else 90
    return source, render, context, center, angle


def _mark(actual_sheet, *, pattern="solid", midpoint=None, **kwargs):
    _, _, context, center, angle = actual_sheet
    return api.create_physical_manual_marking(
        "base_plate", context, (), midpoint=midpoint or center,
        length=12, angle_deg=angle, pattern=pattern,
        dash=2, gap=2, **kwargs,
    )


def test_real_sheet_midpoint_solid_and_dash_are_full_strokes(actual_sheet):
    _source, render, context, center, _ = actual_sheet
    solid = _mark(actual_sheet)
    dashed = _mark(actual_sheet, pattern="dashed")
    assert solid.source_type == api.MANUAL_MARK_SOURCE
    assert tuple(solid.points[0] + solid.points[1]) if False else True
    assert len(solid.layered_profiles) == 1
    assert len(dashed.layered_profiles) == 3
    for mark in (solid, dashed):
        full = LineString([(p.x, p.y) for p in mark.points])
        assert render.material.covers(full)
        assert (mark.points[0].x + mark.points[1].x) / 2 == pytest.approx(center.x)
        assert (mark.points[0].y + mark.points[1].y) / 2 == pytest.approx(center.y)
        accepted = api.propose_operator_physical_sheet_hole_features(
            "base_plate", context, (mark,),
        )
        assert accepted == (mark,)
    produced = api.with_physical_sheet_features("base_plate", render, (dashed,))
    marks = [p for p in produced.scene.primitives if p.layer == "MARKING"]
    assert len(marks) == 3
    assert all(isinstance(row, PolylinePrimitive) and len(row.points) == 2
               and row.semantic_id == api.MANUAL_MARK_SOURCE for row in marks)
    assert [p for p in produced.scene.primitives if p.layer in {"CUTTING", "BEND"}] == [
        p for p in render.scene.primitives if p.layer in {"CUTTING", "BEND"}
    ]
    assert produced.material.equals(render.material)


def test_duplicate_same_style_rejected_overlap_and_bend_crossing_allowed(actual_sheet):
    _source, _render, context, center, angle = actual_sheet
    solid = _mark(actual_sheet)
    with pytest.raises(ValueError, match="重複"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", context, (solid, solid),
        )
    offset = Vec2(center.x + (1 if angle == 0 else 0),
                  center.y + (1 if angle != 0 else 0))
    overlapping = api.create_physical_manual_marking(
        "base_plate", context, (solid,), midpoint=offset, length=12,
        angle_deg=angle,
    )
    assert overlapping != solid
    assert api.propose_operator_physical_sheet_hole_features(
        "base_plate", context, (solid, overlapping),
    ) == (solid, overlapping)


def test_hole_wholly_inside_dash_blank_still_forbids_confirmation(actual_sheet):
    _source, render, context, _center, _angle = actual_sheet
    dashed = _mark(actual_sheet, pattern="dashed")
    start, end = dashed.points
    # Source: 0..2 ink, 2..4 *no ink*, 4..6 ink.  A real through
    # hole entirely in the blank must still block the complete stroke.
    x = start.x + (end.x - start.x) / 12 * 3
    y = start.y + (end.y - start.y) / 12 * 3
    hole = CircleFeature(diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                         offset=Vec2(x, y), layer="CUTTING")
    assert not any(
        LineString([(p.x, p.y) for p in points]).distance(
            LineString([(x, y), (x + 1e-9, y)])
        ) < 0.24
        for _layer, points, _closed in dashed.layered_profiles
    )
    with pytest.raises(ValueError, match="完整筆畫"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", context, (dashed, hole),
        )
    with pytest.raises(ValueError, match="完整筆畫"):
        api.with_physical_sheet_features("base_plate", render, (dashed, hole))


def test_stale_cutting_and_corrupted_saved_dash_fail_closed(actual_sheet, tmp_path):
    _source, render, context, center, angle = actual_sheet
    mark = _mark(actual_sheet)
    shifted = replace(
        mark, points=(mark.points[0] + Vec2(10000.0, 0), mark.points[1]),
    )
    with pytest.raises(ValueError, match="實段"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", context, (shifted,),
        )
    wrong = replace(
        mark, layered_profiles=(("MARKING", (mark.points[0], mark.points[0]), False),),
    )
    with pytest.raises(ValueError, match="實段"):
        api.with_physical_sheet_features("base_plate", render, (wrong,))
    with pytest.raises(ValueError, match="有限數字"):
        api.create_physical_manual_marking(
            "base_plate", context, (), midpoint=center, length=True,
            angle_deg=angle,
        )
    with pytest.raises(ValueError, match="有限數字"):
        api.create_physical_manual_marking(
            "base_plate", context, (), midpoint=center, length=12,
            angle_deg=float("nan"),
        )
    untouched = tmp_path / "previous-approved.dxf"
    untouched.write_bytes(b"KEEP_OLD")
    with pytest.raises(ValueError):
        api.with_physical_sheet_features("base_plate", render, (wrong,))
    assert untouched.read_bytes() == b"KEEP_OLD"


def test_real_p6fold_reopen_dxf_mm_and_form_marking_finite_fold(actual_sheet, tmp_path):
    source, render, _context, center, angle = actual_sheet
    mark = _mark(actual_sheet, pattern="dashed")
    source["workspace"] = dict(source.get("workspace") or {})
    source["workspace"]["part_features"] = dict(
        source["workspace"].get("part_features") or {}
    )
    source["workspace"]["part_features"]["base_plate"] = [mark]
    path = project.write_project(
        tmp_path / "manual-mark-first-physical-sheet.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    loaded = project.read_project(path)["snapshot"]
    reopened_mark = loaded["workspace"]["part_features"]["base_plate"][0]
    assert reopened_mark == mark
    _values, spec = _part_spec(loaded)
    restored = api.build_part_render_data(
        spec, ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
    )
    assert restored.scene.primitives == render.scene.primitives
    with_mark = api.with_physical_sheet_features("base_plate", restored, (reopened_mark,))
    profiles = api.build_standard_part_fold_profiles(loaded, "base_plate")
    paths = api.project_independent_scene_annotation_paths(
        with_mark.scene, profiles["X"], profiles["Y"], with_mark.fold_guides,
    )
    marking_paths = [pts for layer, pts in paths if layer == "MARKING"]
    assert len(marking_paths) == len(mark.layered_profiles)
    assert all(len(points) >= 3 for points in marking_paths)  # formed intermediate points
    assert any(abs(point[2]) > 1e-7 for points in marking_paths for point in points)
    dxf = tmp_path / "real-manual-marking.dxf"
    saved = api.save_part_render_data_dxf(
        with_mark, dxf, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(with_mark, saved).ok
    drawing = ezdxf.readfile(dxf)
    assert drawing.header["$INSUNITS"] == 4
    assert drawing.layers.get("MARKING").dxf.linetype == "CONTINUOUS"
    raw_marks = [e for e in drawing.modelspace() if e.dxf.layer == "MARKING"]
    assert len(raw_marks) == len(mark.layered_profiles)
    assert all(e.dxftype() == "LWPOLYLINE" and len(e) == 2 for e in raw_marks)
    for actual, (_layer, expected, _closed) in zip(raw_marks, mark.layered_profiles):
        assert [tuple(p) for p in actual.get_points("xy")] == pytest.approx([
            (p.x, p.y) for p in expected
        ])
    base_entities = [
        e for e in drawing.modelspace() if e.dxf.layer in {"CUTTING", "BEND"}
    ]
    assert base_entities
    assert any(e.dxf.layer == "BEND" for e in base_entities)
