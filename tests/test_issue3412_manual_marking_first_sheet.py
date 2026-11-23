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
        for measured, canonical in zip(actual.get_points("xy"), expected):
            assert tuple(measured) == pytest.approx((canonical.x, canonical.y))
    base_entities = [
        e for e in drawing.modelspace() if e.dxf.layer in {"CUTTING", "BEND"}
    ]
    assert base_entities
    assert any(e.dxf.layer == "BEND" for e in base_entities)


def test_normal_baseplate_partspec_export_revalidates_full_stroke(actual_sheet, tmp_path):
    """The actual production PartSpec route cannot bypass the editor gate."""
    source, render, _context, _center, _angle = actual_sheet
    _values, spec = _part_spec(source)
    mark = _mark(actual_sheet, pattern="dashed")
    canonical = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    qualified = api.build_part_render_data(replace(spec, features=(mark,)), canonical)
    rows = [p for p in qualified.scene.primitives if p.layer == "MARKING"]
    assert len(rows) == len(mark.layered_profiles)
    assert qualified.material.equals(render.material)
    target = tmp_path / "qualified-base-regular-export.dxf"
    api.save_part_render_data_dxf(
        qualified, target, overwrite=False, verify_reopen=True,
    )
    assert ezdxf.readfile(target).header["$INSUNITS"] == 4

    start, end = mark.points
    blank = Vec2(start.x + (end.x-start.x) * 3 / 12,
                 start.y + (end.y-start.y) * 3 / 12)
    through_hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=blank, layer="CUTTING",
    )
    # Persisted real mark is not auto-adjusted after adding a hole.  Building
    # a fresh normal PartSpec must reject before any DXF writer can run.
    unsafe = replace(spec, features=(mark, through_hole))
    with pytest.raises(ValueError, match="完整筆畫"):
        api.build_part_render_data(unsafe, canonical)
    assert target.exists()


def test_real_tk_mark_button_middlepoint_red_warning_undo_and_escape(actual_sheet):
    """Actual Tk buttons and the original Hole Editor Session are exercised."""
    from types import SimpleNamespace
    import tkinter as tk
    from gui_modules.editors.hole_editor_composition import _install_manual_marking_actions
    from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction

    _source, _render, context, midpoint, angle = actual_sheet
    root = tk.Tk()
    root.geometry("840x360+0+0")
    actual_features = []
    redraw_calls = []
    try:
        root.update_idletasks()
        mark_length = tk.StringVar(master=root, value="12")
        mark_angle = tk.StringVar(master=root, value=str(angle))
        mark_style = tk.StringVar(master=root, value="dashed")
        dash = tk.StringVar(master=root, value="2")
        gap = tk.StringVar(master=root, value="2")
        confirm_button = tk.Button(root, text="確定")
        draw_button = tk.Button(root, text="打標")
        select_button = tk.Button(root, text="選取")
        warning = tk.Label(root, text="")
        session = Phase6HoleEditorSession("base_plate", actual_features)
        state = SimpleNamespace(
            part_key="base_plate", editor=root, manual_marking_context=context,
            live_context=SimpleNamespace(feature_list=actual_features),
            d=SimpleNamespace(tk=tk, manufacturing_api=api),
            manual_mark_mode=[False], manual_mark_length=mark_length,
            manual_mark_angle=mark_angle, manual_mark_pattern=mark_style,
            manual_mark_dash=dash, manual_mark_gap=gap,
            manual_mark_status=warning, confirm_all_btn=confirm_button,
            manual_mark_draw_button=draw_button,
            manual_mark_select_button=select_button,
            hole_session=session, indicator_redraw=[None],
            on_canvas_down=lambda e: None, on_canvas_drag=lambda e: None,
            on_escape=lambda e: "ESCAPE_DEFAULT",
            canvas_view=SimpleNamespace(
                canvas_to_world=lambda x, y: midpoint,
            ),
            set_insert_mode=lambda flag: None,
            redraw=lambda: redraw_calls.append("draw"),
            refresh_created=lambda: None,
            sync_all=lambda: api.propose_operator_physical_sheet_hole_features(
                "base_plate", context, actual_features,
            ),
        )
        _install_manual_marking_actions(state)
        assert select_button.cget("relief") == tk.SUNKEN
        draw_button.invoke()
        assert state.manual_mark_mode == [True]
        state.on_canvas_down(SimpleNamespace(x=120, y=90))
        assert len(actual_features) == 1
        assert api.is_manual_mark(actual_features[0])
        assert state.manual_mark_mode == [True]  # repeat until Esc
        assert confirm_button.cget("state") == tk.NORMAL
        assert redraw_calls

        mark = actual_features[0]
        a, b = mark.points
        point_in_blank = Vec2(a.x + (b.x-a.x) * 3/12,
                              a.y + (b.y-a.y) * 3/12)
        actual_features.append(CircleFeature(
            diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=point_in_blank, layer="CUTTING",
        ))
        state.redraw()
        assert confirm_button.cget("state") == tk.DISABLED
        assert warning.cget("fg") == "#ff453a"
        assert "完整筆畫" in warning.cget("text")
        actual_features.pop()
        state.redraw()
        assert confirm_button.cget("state") == tk.NORMAL
        assert warning.cget("text") == ""

        assert state.manual_mark_escape(SimpleNamespace()) == "break"
        assert state.manual_mark_mode == [False]
        session.execute(HoleEditorAction.undo())
        assert not actual_features
        state.redraw()
        assert confirm_button.cget("state") == tk.NORMAL
    finally:
        root.destroy()


def test_real_cutting_boundary_endpoint_allowed_along_rejected_bend_overlap_allowed(actual_sheet):
    from math import atan2, degrees
    _source, render, context, center, angle = actual_sheet
    material = render.material
    polygon = (max(material.geoms, key=lambda poly: poly.area)
               if hasattr(material, "geoms") else material)
    ring = list(polygon.exterior.coords)
    candidate_edge = None
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        dx, dy = x1-x0, y1-y0
        extent = hypot(dx, dy)
        if extent < 25 or (abs(dx) > 1e-9 and abs(dy) > 1e-9):
            continue
        mx, my = (x0+x1)/2, (y0+y1)/2
        for nx, ny in ((-dy/extent, dx/extent), (dy/extent, -dx/extent)):
            inward = LineString(((mx, my), (mx+nx*8, my+ny*8)))
            if material.covers(inward):
                candidate_edge = mx, my, nx, ny, dx, dy
                break
        if candidate_edge is not None:
            break
    assert candidate_edge is not None, "The real part must expose a usable CUTTING edge"
    mx, my, nx, ny, dx, dy = candidate_edge
    edge_angle = degrees(atan2(dy, dx))
    with pytest.raises(ValueError, match="不可沿 CUTTING"):
        api.create_physical_manual_marking(
            "base_plate", context, (), midpoint=Vec2(mx, my),
            length=8, angle_deg=edge_angle,
        )
    accepted = api.create_physical_manual_marking(
        "base_plate", context, (),
        midpoint=Vec2(mx+nx*4, my+ny*4), length=8,
        angle_deg=degrees(atan2(ny, nx)),
    )
    assert material.covers(LineString([(p.x, p.y) for p in accepted.points]))
    with pytest.raises(ValueError, match="完整筆畫"):
        api.create_physical_manual_marking(
            "base_plate", context, (),
            midpoint=Vec2(mx-nx*4, my-ny*4),
            length=6, angle_deg=degrees(atan2(ny, nx)),
        )

    bends = [row for row in render.scene.primitives
             if isinstance(row, LinePrimitive) and row.layer == "BEND"]
    bend = bends[0]
    overlap = api.create_physical_manual_marking(
        "base_plate", context, (), midpoint=center, length=8,
        angle_deg=degrees(atan2(
            bend.p2.y-bend.p1.y, bend.p2.x-bend.p1.x,
        )),
    )
    assert overlap.layer == "MARKING"
