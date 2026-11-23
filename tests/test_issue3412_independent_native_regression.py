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
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet, _mark
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
        assert root.winfo_exists() == 0
        assert sync_calls == []
        assert on_closes == ["closed"]
        controller.cancel_all()  # already closed is an inert repeat
    finally:
        if root.winfo_exists():
            root.destroy()
