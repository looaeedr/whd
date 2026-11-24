"""#3412 / PR #3415: independently reproduced native first-sheet defects.

Use the SAME actual Receiving BasePlate source as #2517 and the existing
CustomFold PartSpec, not synthesized CUTTING or made-up BEND profiles.
"""
from __future__ import annotations

from dataclasses import replace
from math import dist
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue3412_manual_marking_first_sheet import (
    actual_sheet, _attach_native_marking_pointer_and_controls, _mark,
)
from tests.test_issue2517_physical_sheet_hole_editor_context_api import _spec


def _profiles(source):
    return api.build_standard_part_fold_profiles(source, "base_plate")


def _formed_paths(render, source):
    folded = _profiles(source)
    return [pts for layer, pts in api.project_independent_scene_annotation_paths(
        render.scene, folded["X"], folded["Y"], render.fold_guides,
    ) if layer == "MARKING"]


@pytest.mark.parametrize("angle,length,offset", [
    (90, 12.0, 0.37),  # the independently reported 0.319 mm chord defect
    (60, 12.0, 0.37),  # oblique across the same actual 90-degree BEND
    (90, 0.8, 0.37),  # 1-mm fixed grid would give only two endpoints
])
def test_real_finite_bend_intersection_is_explicit_formed_vertex(
    actual_sheet, angle, length, offset,
):
    source, original, context, center, _ = actual_sheet
    target = Vec2(center.x, 20.0 + offset)
    mark = api.create_physical_manual_marking(
        "base_plate", context, (), midpoint=target, length=length,
        angle_deg=angle,
    )
    assert mark.points[0].y < 20 < mark.points[1].y
    formed = api.with_physical_sheet_features("base_plate", original, (mark,))
    path, = _formed_paths(formed, source)
    actual_bend = next(row for row in original.scene.primitives
                       if isinstance(row, LinePrimitive) and row.layer == "BEND")
    assert actual_bend.p1.y == actual_bend.p2.y == 20
    # True flat-source interpolation at y20, including an oblique crossing.
    p1, p2 = mark.points
    fraction = (20.0 - p1.y) / (p2.y - p1.y)
    world_x = p1.x + (p2.x - p1.x) * fraction
    assert min(actual_bend.p1.x, actual_bend.p2.x) <= world_x <= max(
        actual_bend.p1.x, actual_bend.p2.x,
    )
    bend_world, *_other = api.project_independent_scene_bend_segments(
        original.scene, _profiles(source)["X"], _profiles(source)["Y"],
        original.fold_guides,
    )
    world_fraction = (
        (world_x - actual_bend.p1.x) /
        (actual_bend.p2.x - actual_bend.p1.x)
    )
    expected = tuple(
        a + (b - a) * world_fraction for a, b in zip(*bend_world)
    )
    assert min(dist(point, expected) for point in path) < 1e-8, (
        "FOLD_INTERSECTION_MUST_BE_EXPLICIT_VERTEX"
    )
    # Every displayed chord's source interval lies entirely on one physical
    # formed face; it may end on the BEND but not bridge both sides.
    assert any(dist(point, expected) < 1e-8 for point in path[1:-1])
    # Material-face proof: every *formed stroke chord midpoint* lies on one
    # of the two true planar surfaces adjacent to the real y20 hinge.
    # A 0.319-mm bridge through the 90-degree corner fails this check even
    # if its endpoints look plausible.
    for a, b in zip(path, path[1:]):
        chord_mid = tuple((u + v) / 2 for u, v in zip(a, b))
        assert (abs(chord_mid[1] - expected[1]) < 1e-8
                or abs(chord_mid[2] - expected[2]) < 1e-8), (
                    "FORMED_MARKING_CHORD_MUST_LIE_ON_REAL_FACE"
                )


def _custom_saved_mark():
    start, finish = Vec2(34, 80), Vec2(46, 80)
    ink = ((Vec2(34, 80), Vec2(36, 80)),
           (Vec2(38, 80), Vec2(40, 80)),
           (Vec2(42, 80), Vec2(44, 80)))
    return ProfileFeature(
        points=(start, finish), anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0, 0), layer="MARKING",
        source_type=api.MANUAL_MARK_SOURCE,
        source_params=(("pattern", "dashed"), ("dash", 2.0), ("gap", 2.0)),
        layered_profiles=tuple(("MARKING", segment, False) for segment in ink),
    )


def test_customfold_stored_dash_hole_in_blank_is_preserved_but_dxf_rejected(tmp_path):
    """A persisted unsupported mark is intent, not output authorization."""
    spec = _spec(axis="X", key="custom:17")
    mark = _custom_saved_mark()
    hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(37, 80), layer="CUTTING",
    )
    original_features = (mark, hole)
    current = replace(spec, features=original_features)
    render = api.build_part_render_data(current)
    assert render.scene.primitives
    assert len([r for r in render.scene.primitives if r.layer == "MARKING"]) == 3
    editor_context = api.resolve_physical_sheet_editor_context(
        current.physical_id, api.build_part_render_data(spec), custom_spec=spec,
    )
    with pytest.raises(ValueError, match="MANUAL_MARKING.*UNSUPPORTED"):
        api.propose_operator_physical_sheet_hole_features(
            current.physical_id, editor_context, original_features,
        )
    destination = tmp_path / "custom-must-not-export.dxf"
    destination.write_bytes(b"PREVIOUS_VALID_DATA")
    with pytest.raises(ValueError, match="MANUAL_MARKING.*UNSUPPORTED"):
        api.save_part_render_data_dxf(
            render, destination, overwrite=True, verify_reopen=True,
        )
    assert destination.read_bytes() == b"PREVIOUS_VALID_DATA"
    assert current.features == original_features


def test_generic_baseplate_direct_generate_part_never_uses_marking_bypass(
    actual_sheet, tmp_path,
):
    _source, _render, _context, _center, _angle = actual_sheet
    from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import (
        _part_spec, _configured,
    )
    _values, receiving = _part_spec(_configured("受電箱"))
    mark = _mark(actual_sheet, pattern="dashed")
    generic = replace(
        receiving, model_name="金庫型", receiving_bend_pattern=None,
        features=(mark,),
    )
    outfile = tmp_path / "generic-baseplate-existing.dxf"
    outfile.write_bytes(b"PREVIOUS_VALID_DATA")
    with pytest.raises(ValueError, match="MANUAL_MARKING.*UNSUPPORTED"):
        api.generate_part(
            generic, outfile,
            ManufacturingContext(
                resource_root=Path(__file__).resolve().parents[1], overwrite=True,
            ),
        )
    assert outfile.read_bytes() == b"PREVIOUS_VALID_DATA"


def test_customfold_creation_is_not_promoted_to_first_sheet(actual_sheet):
    spec = _spec(axis="X", key="custom:17")
    render = api.build_part_render_data(spec)
    context = api.resolve_physical_sheet_editor_context(
        spec.physical_id, render, custom_spec=spec,
    )
    with pytest.raises(ValueError, match="MANUAL_MARKING.*UNSUPPORTED"):
        api.create_physical_manual_marking(
            spec.physical_id, context, (), midpoint=Vec2(40, 80),
            length=12, angle_deg=0, pattern="dashed", dash=2, gap=2,
        )


def test_cancel_of_stale_saved_mark_destroys_editor_without_sync_or_validation(
    actual_sheet,
):
    """Original stale mark remains saved; Cancel does not re-submit it."""
    import tkinter as tk
    from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction
    from gui_modules.editors.hole_editor import HoleEditorModalLifecycle

    _source, original_render, _context, _center, _angle = actual_sheet
    saved_mark = _mark(actual_sheet, pattern="dashed")
    p1, p2 = saved_mark.points
    hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(p1.x + (p2.x-p1.x)*3/12, p1.y + (p2.y-p1.y)*3/12),
        layer="CUTTING",
    )
    new_render = api.with_physical_sheet_features(
        "base_plate", original_render, (hole,),
    )
    current = api.resolve_physical_sheet_editor_context("base_plate", new_render)
    with pytest.raises(ValueError, match="完整筆畫"):
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", current, (saved_mark,),
        )

    original_features = [saved_mark]
    live = list(original_features)
    session = Phase6HoleEditorSession("base_plate", live)
    session.execute(HoleEditorAction.insert(hole))
    session.execute(HoleEditorAction.commit_active())
    assert len(live) == 2
    sync_calls = []
    on_closes = []
    root = tk.Tk()
    try:
        controller = HoleEditorModalLifecycle(
            hole_session=session, has_selected_feature=lambda: False,
            position_authority=[None], commit_active_edit=lambda **_kw: None,
            sync_all=lambda: sync_calls.append("sync") or
            api.propose_operator_physical_sheet_hole_features(
                "base_plate", current, live,
            ),
            validate_current_indicator_fit=lambda show_error=False: True,
            door_indicator_state=None, collect_indicator_state=lambda: None,
            door_indicator_commit=None, editor_closed=[False],
            editor=root, on_close=lambda: on_closes.append("closed"),
            insert_mode=[False], set_insert_mode=lambda state: None,
            cancel_active_edit=lambda: None, sync_on_cancel=False,
        )
        controller.cancel_all()
        assert live == original_features
        try:
            still_open = root.winfo_exists()
        except tk.TclError:  # Tcl interpreter was destroyed with the root
            still_open = 0
        assert not still_open
        assert sync_calls == []
        assert on_closes == ["closed"]
        controller.cancel_all()  # already closed is an inert repeat
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_native_tk_canvas_place_confirm_save_new_instance_open_and_normal_dxf(
    actual_sheet, tmp_path, monkeypatch,
):
    """True native Tk canvas click -> confirm -> .p6fold -> a new GUI adapter
    instance -> normal Engine generate_part -> independently reopened DXF.
    """
    import tkinter as tk
    import phase6_project_file as project
    from phase6_hole_editor_canvas_view import (
        Phase6HoleEditorCanvasView, HoleEditorCanvasFrame,
    )
    from phase6_hole_editor_session import Phase6HoleEditorSession
    from gui_modules.editors.hole_editor_composition import _install_manual_marking_actions
    from gui_modules.editors.hole_editor import HoleEditorModalLifecycle
    from gui_modules.application.physical_part_hole_editor import open_workspace_sheet_editor
    from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _part_spec

    source, baseline, context, midpoint, _angle = actual_sheet
    tk_root = tk.Tk()
    tk_root.geometry("1100x850+0+0")
    canvas = tk.Canvas(tk_root, width=1000, height=700)
    canvas.pack(fill="both", expand=True)
    tk_root.update()
    live = []
    session = Phase6HoleEditorSession("base_plate", live)
    view = Phase6HoleEditorCanvasView(
        canvas, draw_grid=lambda *_a: None,
        render_secondary_scene=lambda *_a: None,
        render_resolved_features=lambda *_a, **_kw: None,
    )

    def redraw():
        view.render(HoleEditorCanvasFrame(
            surface=context.feature_surface, features=live,
            width=context.width, height=context.height,
            reference_guide=context.reference_guide, selected_index=-1,
            baseline_scene=baseline.scene,
        ))

    redraw()
    cx, cy = view.transform.world_to_canvas(Vec2(midpoint.x, 20.37))
    assert 0 <= cx <= canvas.winfo_width()
    assert 0 <= cy <= canvas.winfo_height()

    def button(title):
        return tk.Button(tk_root, text=title)

    confirm = button("確定")
    drawing = button("打標")
    selection = button("選取")
    warning = tk.Label(tk_root, text="")
    staged = []
    editor = SimpleNamespace(
        part_key="base_plate", editor=tk_root, manual_marking_draft=api.open_physical_sheet_marking("base_plate", context=context),
        live_context=SimpleNamespace(feature_list=live),
        d=SimpleNamespace(tk=tk, manufacturing_api=api),
        manual_mark_mode=[False],
        manual_mark_length=tk.StringVar(master=tk_root, value="12"),
        manual_mark_angle=tk.StringVar(master=tk_root, value="90"),
        manual_mark_pattern=tk.StringVar(master=tk_root, value="dashed"),
        manual_mark_dash=tk.StringVar(master=tk_root, value="2"),
        manual_mark_gap=tk.StringVar(master=tk_root, value="2"),
        manual_mark_status=warning, confirm_all_btn=confirm,
        manual_mark_draw_button=drawing, manual_mark_select_button=selection,
        hole_session=session, indicator_redraw=[None],
        on_escape=lambda _e: "unhandled", canvas_view=view, canvas=canvas,
        set_insert_mode=lambda _value: None,
        redraw=redraw, refresh_created=lambda: None,
        sync_all=lambda: None,
    )
    try:
        _attach_native_marking_pointer_and_controls(editor, context)
        _install_manual_marking_actions(editor)
        canvas.bind("<Button-1>", editor.on_canvas_down)
        canvas.bind("<ButtonRelease-1>", editor.on_canvas_up)
        drawing.invoke()
        canvas.event_generate("<Button-1>", x=round(cx), y=round(cy))
        canvas.event_generate("<ButtonRelease-1>", x=round(cx), y=round(cy))
        tk_root.update()
        assert len(live) == 1 and api.is_manual_mark(live[0])
        assert drawing.cget("relief") == tk.SUNKEN
        assert confirm.cget("state") == tk.NORMAL
        original_mark = live[0]
        assert abs((original_mark.points[0].y + original_mark.points[1].y) / 2 - 20.37) < 0.5

        lifecycle = HoleEditorModalLifecycle(
            hole_session=session, has_selected_feature=lambda: False,
            position_authority=[None], commit_active_edit=lambda **kw: None,
            sync_all=lambda: None, validate_current_indicator_fit=lambda show_error=False: True,
            door_indicator_state=None, collect_indicator_state=lambda: None,
            door_indicator_commit=None, editor_closed=[False],
            editor=tk_root, on_close=lambda: None, insert_mode=[False],
            set_insert_mode=lambda value: None, cancel_active_edit=lambda: None,
            before_commit=lambda: staged.append(
                api.propose_operator_physical_sheet_hole_features(
                    "base_plate", context, tuple(live),
                )
            ), sync_on_cancel=False,
        )
        lifecycle.confirm_all()
        assert len(staged) == 1 and staged[0] == (original_mark,)
    finally:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass

    saved_source = dict(source)
    saved_source["workspace"] = dict(saved_source.get("workspace") or {})
    saved_source["workspace"]["part_features"] = dict(
        saved_source["workspace"].get("part_features") or {}
    )
    saved_source["workspace"]["part_features"]["base_plate"] = list(staged[0])
    saved_path = project.write_project(
        tmp_path / "real-native-3412.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved_source},
    )

    # The next GUI request is a fresh workspace/app/window adapter instance.
    loaded = project.read_project(saved_path)["snapshot"]
    reopened = loaded["workspace"]["part_features"]["base_plate"]
    assert tuple(reopened) == staged[0]
    ctx = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    _values, spec = _part_spec(loaded)
    clean = api.build_part_render_data(spec, ctx)
    captured = {}
    writes = []
    workspace = SimpleNamespace(
        available_parts=("base_plate",), active_part="base_plate",
        features_for=lambda _key: reopened,
        stash_features=lambda *_args: writes.append(_args),
    )
    app = SimpleNamespace(
        designer_workspace=workspace, _load_part_holes=lambda _key: None,
        submit_update_intent=lambda *_a, **_kw: None,
    )
    from phase6_project_controller import Phase6ProjectController
    controller = Phase6ProjectController(
        read_project=project.read_project, write_project=project.write_project,
        schema=project.PROJECT_SCHEMA,
    )
    controller.load(saved_path)
    host = SimpleNamespace(
        fold_designer_app=app, project_controller=controller,
        _query_fold_designer_render_data=lambda *_a: clean,
        _open_unified_hole_editor=lambda *_a, **kw: captured.update(kw) or object(),
    )
    monkeypatch.setattr(
        "phase6_manufacturing_adapter.build_scene_payload_for_app",
        lambda *_a: dict(loaded),
    )
    monkeypatch.setattr(
        "phase6_part_navigation.operator_part_label",
        lambda *_a, **_kw: "真受電箱底板",
    )
    open_workspace_sheet_editor(host, "base_plate")
    assert captured["feature_list_override"] == reopened
    assert captured["feature_list_override"] is not reopened  # Transient editor draft must not mutate saved Features.
    draft = captured["manual_marking_draft"]
    assert draft.features == tuple(reopened)
    assert draft.context.part_key == "base_plate"
    assert draft.context.render_data is clean
    assert captured["defer_workspace_sync"] is True
    assert captured["skip_cancel_sync"] is True
    assert writes == []

    whole_spec = replace(spec, features=tuple(reopened))
    whole = api.build_part_render_data(whole_spec, ctx)
    output_path = tmp_path / "normal-public-generate-part.dxf"
    result = api.generate_part(whole_spec, output_path, ctx)
    assert result.output_path == str(output_path)
    assert api.verify_saved_part_render_data_dxf(whole, output_path).ok
    from_disk = ezdxf.readfile(output_path)
    assert from_disk.header["$INSUNITS"] == 4
    lines = [e for e in from_disk.modelspace() if e.dxf.layer == "MARKING"]
    assert len(lines) == len(original_mark.layered_profiles)
    assert {e.dxf.layer for e in from_disk.modelspace()} >= {
        "CUTTING", "BEND", "MARKING",
    }
    paths = _formed_paths(whole, loaded)
    assert len(paths) == len(lines)
    assert all(len(path) >= 2 for path in paths)


def test_composed_dxf_rejects_saved_customfold_mark_hole_in_dash_blank_atomically(
    tmp_path,
):
    """Existing Vault/Panel composed sink must not bypass source-marking gate.

    This uses real CustomFold material/CUTTING/BEND and the same persisted
    dash2/gap2 stroke with the real 0.5-mm through hole at x37 in a blank.
    An ordinary successful pre-commit guard does not authorize this intent.
    """
    from ae_engine.contracts import (
        ResolvedManufacturingGeometry, ResolvedManufacturingPart,
    )

    spec = _spec(axis="X", key="custom:17")
    mark = _custom_saved_mark()
    hole = CircleFeature(
        diameter=0.5, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(37, 80), layer="CUTTING",
    )
    original = replace(spec, features=(mark, hole))
    render = api.build_part_render_data(original)
    assert sum(p.layer == "MARKING" for p in render.scene.primitives) == 3
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(original.physical_id, render),
    ))
    outfile = tmp_path / "already-approved-composed.dxf"
    outfile.write_bytes(b"PREVIOUS_VALID_COMPOSED_DATA")
    guards = []

    def live_source_guard():
        guards.append(True)

    with pytest.raises(ValueError, match="MANUAL_MARKING_V1_UNSUPPORTED_SOURCE"):
        api.save_composed_panel_dxf(
            (("actual-custom-fold", geometry),),
            outfile, pre_commit_guard=live_source_guard, overwrite=True,
        )
    assert outfile.read_bytes() == b"PREVIOUS_VALID_COMPOSED_DATA"
    assert original.features == (mark, hole)
    # Reject occurs before any actual DXF writer, regardless of guard cadence.
    assert len(guards) <= 1


def test_composed_dxf_rejects_mixed_valid_base_and_unsupported_custom_before_write(
    actual_sheet, tmp_path,
):
    """One illegal selected sheet must block the entire multi-panel publish."""
    from ae_engine.contracts import (
        ResolvedManufacturingGeometry, ResolvedManufacturingPart,
    )
    _source, real_base, _context, _, _ = actual_sheet
    good = _mark(actual_sheet, pattern="dashed")
    eligible = api.with_physical_sheet_features("base_plate", real_base, (good,))
    base = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("base_plate", eligible),
    ))

    custom = _spec(axis="X", key="custom:17")
    unsafe = replace(custom, features=(_custom_saved_mark(),))
    custom_geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(custom.physical_id,
                                  api.build_part_render_data(unsafe)),
    ))
    dest = tmp_path / "mixed-previous-approved.dxf"
    dest.write_bytes(b"KEEP_APPROVED_FILE")
    with pytest.raises(ValueError, match="MANUAL_MARKING_V1_UNSUPPORTED_SOURCE"):
        api.save_composed_panel_dxf(
            (("good-real-base", base), ("unsupported-custom", custom_geometry)),
            dest, pre_commit_guard=lambda: None, overwrite=True,
        )
    assert dest.read_bytes() == b"KEEP_APPROVED_FILE"


def test_composed_dxf_real_base_manual_mark_and_unmarked_custom_still_export(
    actual_sheet, tmp_path,
):
    """No-mark normal composed path and legal BasePlate are unchanged."""
    from ae_engine.contracts import (
        ResolvedManufacturingGeometry, ResolvedManufacturingPart,
    )
    _source, real_base, _context, _, _ = actual_sheet
    mark = _mark(actual_sheet, pattern="dashed")
    with_mark = api.with_physical_sheet_features(
        "base_plate", real_base, (mark,),
    )
    base = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("base_plate", with_mark),
    ))
    custom_spec = _spec(axis="X", key="custom:17")
    unmarked = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(custom_spec.physical_id,
                                 api.build_part_render_data(custom_spec)),
    ))
    dest = tmp_path / "valid-composed.dxf"
    guard_observations = []

    def guard():
        guard_observations.append(dest.read_bytes() if dest.exists() else None)

    result = api.save_composed_panel_dxf(
        (("valid-manual-base", base), ("unmarked-custom", unmarked)),
        dest, pre_commit_guard=guard, overwrite=False,
    )
    assert result.path == str(dest)
    published = dest.read_bytes()
    assert guard_observations[0] is None
    assert guard_observations[-1] == published
    assert all(observed is None or observed == published for observed in guard_observations)
    dxf = ezdxf.readfile(dest)
    assert not dxf.audit().errors
    expected_cutting = sum(
        primitive.layer == "CUTTING"
        for geom in (base, unmarked)
        for part in geom.parts
        for primitive in part.render_data.scene.primitives
    )
    assert sum(e.dxf.layer == "CUTTING" for e in dxf.modelspace()) == expected_cutting
    assert dxf.header["$INSUNITS"] == 4
    marked = [e for e in dxf.modelspace() if e.dxf.layer == "MARKING"]
    assert len(marked) == len(mark.layered_profiles)
    assert all(e.dxftype() == "LWPOLYLINE" and len(e) == 2 for e in marked)
    assert any(e.dxf.layer == "BEND" for e in dxf.modelspace())
