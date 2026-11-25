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


def _attach_native_marking_pointer_and_controls(state, context):
    """Supply real Tk controls and the original pointer adapter to small tests."""
    from types import SimpleNamespace
    from gui_modules.editors.hole_editor import (
        HoleEditorCanvasPointerActions, HoleEditorCreatedListActions,
        HoleEditorSelectedFeatureActions,
    )
    from phase6_hole_editor_session import HoleEditorAction

    tk = state.d.tk
    state.dragging = [False]
    state.insert_mode = [False]
    state.insert_btn = tk.Button(state.editor, text="插入開孔")
    state.delete_btn = tk.Button(state.editor, text="刪除")
    state.undo_btn = tk.Button(state.editor, text="復原")
    state.created_list = tk.Listbox(state.editor)
    state.host = SimpleNamespace()
    state.on_confirm_features = None  # This harness confirms through the real modal lifecycle.
    state.feature_list = state.live_context.feature_list
    state.set_insert_mode = lambda value: state.insert_mode.__setitem__(0, bool(value))
    state.undo_last_action = lambda _event=None: state.hole_session.execute(HoleEditorAction.undo())
    state.on_catalog_double_click = lambda _event, _source_list: None
    if not hasattr(state, "canvas"):
        state.canvas = tk.Canvas(state.editor)
    if not hasattr(state.canvas_view, "hit_test"):
        state.canvas_view.hit_test = lambda _x, _y: None
    for key, value in {
        "arm_x": "20", "arm_y": "20", "angle": "0",
        "spacing_x": "", "spacing_y": "", "member": "",
        "offset_x": "0", "offset_y": "0",
    }.items():
        setattr(state, "manual_group_" + key, tk.StringVar(master=state.editor, value=value))
    state.manual_group_tool = ["select"]
    state.manual_group_tools = {
        kind: tk.Button(state.editor, text=kind)
        for kind in state.manual_marking_draft.allowed_tools
        if kind in ("cross", "l", "pair_l", "quad_l")
    }
    for name in ("manual_group_apply_offset", "manual_group_apply_size",
                 "manual_group_rotate", "manual_group_mirror", "manual_mark_copy_button"):
        setattr(state, name, tk.Button(state.editor, text=name))
    state.manual_round_diameter = tk.StringVar(master=state.editor)
    state.manual_round_button = tk.Button(state.editor, text="圓打標")
    def context_provider():
        return {
            "surface": context.feature_surface, "width": context.width,
            "height": context.height, "feature_list": state.live_context.feature_list,
        }

    def select_feature(index):
        state.hole_session.execute(HoleEditorAction.select(index))

    pointer = HoleEditorCanvasPointerActions(
        hole_session=state.hole_session, canvas_view=state.canvas_view,
        dragging=state.dragging, insert_mode=state.insert_mode,
        context_provider=context_provider,
        select_feature=select_feature, make_feature=lambda _point: None,
        feature_is_within_surface=api.operator_hole_feature_is_within_surface,
        move_feature_within_surface=api.operator_hole_move_feature_within_surface,
        begin_edit=lambda *_args: None, refresh_reference_fields=lambda: None,
        redraw=state.redraw, sync_all=state.sync_all,
        warn_out_of_bounds=lambda: pytest.fail("unexpected native pointer rejection"),
    )
    created = HoleEditorCreatedListActions(
        hole_session=state.hole_session, feature_list=state.feature_list,
        created_list=state.created_list, select_feature=select_feature,
        feature_with_process=api.operator_hole_feature_with_process,
        refresh_created=state.refresh_created, refresh_reference_fields=lambda: None,
        redraw=state.redraw, sync_all=state.sync_all,
    )
    selected = HoleEditorSelectedFeatureActions(
        hole_session=state.hole_session, canvas_view=state.canvas_view,
        context_provider=context_provider, select_feature=select_feature,
        menu_factory=lambda: tk.Menu(state.editor, tearoff=0),
        reference_anchor_labels={}, feature_reference_anchor=lambda feature: feature.anchor,
        set_reference_anchor=lambda _anchor: None, var_rotation=tk.StringVar(master=state.editor),
        rotate_feature=api.operator_hole_feature_with_rotation,
        feature_is_within_surface=api.operator_hole_feature_is_within_surface,
        warn_rotation_out_of_bounds=lambda: pytest.fail("unexpected rotation rejection"),
        refresh_reference_fields=lambda: None, redraw=state.redraw, sync_all=state.sync_all,
    )
    state.on_created_select = created.on_created_select
    state.toggle_created_process = created.toggle_created_process
    state.delete_selected = created.delete_selected
    state.on_canvas_right = selected.on_canvas_right
    state.rotate_selected = selected.rotate_selected
    state.on_canvas_down = pointer.on_canvas_down
    state.on_canvas_drag = pointer.on_canvas_drag
    state.on_canvas_up = pointer.on_canvas_up


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
            part_key="base_plate", editor=root, manual_marking_draft=api.open_physical_sheet_marking("base_plate", context=context),
            live_context=SimpleNamespace(feature_list=actual_features),
            d=SimpleNamespace(tk=tk, manufacturing_api=api),
            manual_mark_mode=[False], manual_mark_length=mark_length,
            manual_mark_angle=mark_angle, manual_mark_pattern=mark_style,
            manual_mark_dash=dash, manual_mark_gap=gap,
            manual_mark_status=warning, confirm_all_btn=confirm_button,
            manual_mark_draw_button=draw_button,
            manual_mark_select_button=select_button,
            hole_session=session, indicator_redraw=[None],
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
        _attach_native_marking_pointer_and_controls(state, context)
        _install_manual_marking_actions(state)
        assert select_button.cget("relief") == tk.SUNKEN
        draw_button.invoke()
        assert state.manual_mark_mode == [True]
        event = SimpleNamespace(x=120, y=90)
        state.on_canvas_down(event)
        state.on_canvas_up(event)
        assert not state.dragging[0]
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
        if extent < 25 or abs(dy) > 1e-9:
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
    edge_angle = 0.0  # horizontal boundary: avoid trig drift on the edge
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


def test_oblique_crossing_and_dashed_ink_versus_blank_use_real_finite_fold(actual_sheet):
    """The real Receiving BasePlate BEND is crossed obliquely, not extended.

    The 3D path must bend through its intermediate physical face coordinates
    whereas DXF retains unmodified straight source segments.
    """
    from math import dist
    source, render, context, center, angle = actual_sheet
    assert angle == 90  # actual horizontal BEND20, not a fabricated test line
    profiles = api.build_standard_part_fold_profiles(source, "base_plate")

    def new_mark(delta_y, pattern):
        return api.create_physical_manual_marking(
            "base_plate", context, (), midpoint=Vec2(center.x, center.y + delta_y),
            length=12, angle_deg=60, pattern=pattern, dash=2, gap=2,
        )

    oblique = new_mark(0, "solid")
    formed = api.with_physical_sheet_features("base_plate", render, (oblique,))
    world = api.project_independent_scene_annotation_paths(
        formed.scene, profiles["X"], profiles["Y"], formed.fold_guides,
    )
    ink = [points for layer, points in world if layer == "MARKING"]
    assert len(ink) == 1 and len(ink[0]) > 2
    middle = ink[0][len(ink[0]) // 2]
    endpoint_midpoint = tuple((a+b)/2 for a, b in zip(ink[0][0], ink[0][-1]))
    assert dist(middle, endpoint_midpoint) > 0.1  # cannot paint a straight 3D chord

    # Dash period 2+2: real ink [0,2],[4,6],[8,10] from first tip.
    # Move the origin +0.1/-0.8 mm in Y: the same true BEND20 falls
    # respectively *inside* the second ink or the empty [6,8] interval.
    dashed_ink = new_mark(0.1, "dashed")
    dashed_blank = new_mark(-0.8, "dashed")

    def crossing_ink(mark):
        return any(
            min(p.y for p in points) < center.y - 1e-6
            and max(p.y for p in points) > center.y + 1e-6
            for _layer, points, _closed in mark.layered_profiles
        )

    assert crossing_ink(dashed_ink)
    assert not crossing_ink(dashed_blank)
    for mark in (dashed_ink, dashed_blank):
        physically = api.with_physical_sheet_features("base_plate", render, (mark,))
        marked = [row for row in physically.scene.primitives
                  if row.layer == "MARKING"]
        assert len(marked) == 3
        paths = [pts for layer, pts in
                 api.project_independent_scene_annotation_paths(
                     physically.scene, profiles["X"], profiles["Y"],
                     physically.fold_guides,
                 ) if layer == "MARKING"]
        assert len(paths) == 3
        assert all(len(points) > 2 for points in paths)
        for drawn, (_layer, physical_segment, _closed) in zip(
            marked, mark.layered_profiles,
        ):
            assert isinstance(drawn, PolylinePrimitive)
            assert drawn.points == physical_segment


def test_real_finite_bend_extension_does_not_authorize_infinite_mark(actual_sheet):
    """An extrapolated BEND is not an alternate source of material or cutting."""
    from math import degrees, atan2
    _source, render, context, _center, _angle = actual_sheet
    bending = next(
        p for p in render.scene.primitives
        if isinstance(p, LinePrimitive) and p.layer == "BEND"
    )
    assert bending.p1.y == pytest.approx(bending.p2.y)
    low = min(bending.p1.x, bending.p2.x)
    high = max(bending.p1.x, bending.p2.x)
    yy = float(bending.p1.y)
    target_x = low - 1.0
    if target_x <= render.material.bounds[0] + 1e-7:
        target_x = high + 1.0
    assert target_x < low or target_x > high

    # No fabricated extension of a finite BEND is added to DrawingScene.
    original_bends = [row for row in render.scene.primitives
                      if row.layer == "BEND"]
    from shapely.geometry import LineString
    full = LineString(((target_x, yy-3), (target_x, yy+3)))
    if (render.material.covers(full)
            and render.material.boundary.intersection(full).length <= 1e-7):
        mark = api.create_physical_manual_marking(
            "base_plate", context, (), midpoint=Vec2(target_x, yy),
            length=6, angle_deg=90,
        )
        resulting = api.with_physical_sheet_features("base_plate", render, (mark,))
        assert [p for p in resulting.scene.primitives if p.layer == "BEND"] == original_bends
    else:
        with pytest.raises(ValueError, match="完整筆畫|CUTTING"):
            api.create_physical_manual_marking(
                "base_plate", context, (), midpoint=Vec2(target_x, yy),
                length=6, angle_deg=90,
            )


def test_real_tk_sync_warns_when_existing_mark_conflicts_with_new_blank_hole(actual_sheet):
    """The real editor sync catches invalid MARKING but not unrelated errors."""
    import tkinter as tk
    from types import SimpleNamespace
    from gui_modules.editors.hole_editor_composition import _guard_manual_marking_sync

    _source, _render, context, _center, _angle = actual_sheet
    dashed = _mark(actual_sheet, pattern="dashed")
    p1, p2 = dashed.points
    blank_point = Vec2(p1.x + (p2.x-p1.x)*3/12,
                       p1.y + (p2.y-p1.y)*3/12)
    hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=blank_point, layer="CUTTING",
    )
    pending = [dashed, hole]
    root = tk.Tk()
    try:
        status = tk.Label(root)
        confirm = tk.Button(root, text="確定")
        original_calls = []
        def failing_publisher():
            original_calls.append(tuple(pending))
            raise ValueError("canonical physical publisher rejected candidate")
        state = SimpleNamespace(
            part_key="base_plate", manual_marking_draft=api.open_physical_sheet_marking("base_plate", context=context),
            live_context=SimpleNamespace(feature_list=pending),
            d=SimpleNamespace(tk=tk, manufacturing_api=api),
            sync_all=failing_publisher,
            confirm_all_btn=confirm, manual_mark_status=status,
        )
        _guard_manual_marking_sync(state)
        state.sync_all()
        assert len(original_calls) == 1
        assert tuple(pending) == (dashed, hole)  # no silent trimming/deletion
        assert confirm.cget("state") == tk.DISABLED
        assert status.cget("fg") == "#ff453a"
        assert "完整筆畫" in status.cget("text")

        pending.pop()  # after Undo, an unrelated publisher error still raises
        with pytest.raises(ValueError, match="canonical physical publisher"):
            state.sync_all()
    finally:
        root.destroy()
