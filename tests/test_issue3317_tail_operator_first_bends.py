# -*- coding: utf-8 -*-
"""#3317: physical first BEND per corner, never CHECK labels or nominal X.

The exact 620/185/T2 Vault Tail flat is the WHD Engine source, not a made-up
independent flange. These are preview-only checks; DXF gate remains closed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene,
    fold_guides_from_final_scene,
)
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_tail_no_ba_sequential import _stages, stations_from_real_flat
from ae_engine.v_miter_tail_user_image_source import project_tail_illustrated_side_v90_flat
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3317_tail_gui_lower_v import _real_source


@pytest.fixture
def actual_tail():
    return _real_source(w=620., d=185., t=2., bottom=48.)


def _selected(spec, raw, axis):
    snapshot = {"model": "金庫型", "w": 620., "d": 185., "t": 2.,
                "fw": 25., "yl1": 15., "yr1": 15.,
                "ytop1": 16., "ybottom1": 48.}
    snapshot = api.commit_operator_tail_lower_v_choice(
        snapshot, "v90", tail_scene_values=snapshot,
    )
    saved = api.commit_operator_tail_lower_v_first_bends(
        snapshot, {"bottom_left": axis, "bottom_right": axis},
        spec=spec, render_data=raw,
    )
    return snapshot, saved


def test_nominal_unselected_preview_not_operator_order(actual_tail):
    spec, raw = actual_tail
    preview = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice="v90",
    )
    assert preview.metadata["tail_lower_v_first_fold_basis"] == "NOMINAL_UNSELECTED_PREVIEW"
    assert preview.metadata["tail_lower_v_operator_first_axis"] is None
    assert api.tail_lower_v_first_stage_mesh(preview) is None
    assert api.tail_lower_v_preview_mesh(preview)
    with pytest.raises(ValueError, match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(preview)


@pytest.mark.parametrize("axis,first_xyz", (
    ("x", (15., 26., 10.)),
    ("y", (5., 48., 22.)),
))
def test_two_corners_select_real_finite_source_and_drive_first_stage(
    actual_tail, axis, first_xyz,
):
    spec, raw = actual_tail
    options = api.project_operator_tail_lower_v_first_bend_options(spec, raw)
    assert set(options) == {"source_bends", "bottom_left", "bottom_right"}
    assert options["bottom_left"]["x"]["bend"] != options["bottom_right"]["x"]["bend"]
    assert options["bottom_left"]["y"]["bend"] == options["bottom_right"]["y"]["bend"]
    for corner in ("bottom_left", "bottom_right"):
        assert "mm" in options[corner][axis]["label"]
        assert options[corner][axis]["bend"] in options["source_bends"]

    original, saved = _selected(spec, raw, axis)
    assert api.TAIL_LOWER_V_FIRST_BENDS_KEY not in original
    assert saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY]["bottom_left"]["first"] == axis
    assert saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY]["bottom_right"]["first"] == axis
    assert api.validate_operator_tail_lower_v_first_bends(
        saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY], spec=spec, render_data=raw,
    ) == axis
    stage = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice="v90",
        first_bends=saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY],
    )
    assert stage.metadata["tail_lower_v_operator_first_axis"] == axis
    assert stage.metadata["tail_lower_v_first_fold_basis"] == "OPERATOR_SELECTED_PHYSICAL_BEND"
    assert stage.material.geom_type == "Polygon"
    assert stage.material.bounds == pytest.approx((0., 0., 642., 268.))
    assert api.tail_lower_v_first_stage_mesh(stage)
    assert api.tail_lower_v_preview_mesh(stage)
    flat = project_tail_illustrated_side_v90_flat(spec, raw)
    p1, p2, *_ = _stages((5., 26.), axis, stations_from_real_flat(flat))
    assert p1 == pytest.approx(first_xyz)
    assert p2 == pytest.approx((15., 58., 22.))
    with pytest.raises(ValueError, match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(stage)


def test_xx_yy_same_flat_final_but_not_same_first_stage(actual_tail):
    spec, raw = actual_tail
    outputs = []
    for axis in ("x", "y"):
        _, saved = _selected(spec, raw, axis)
        outputs.append(api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90",
            first_bends=saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY],
        ))
    first, second = outputs
    assert first.material.symmetric_difference(second.material).area < 1e-7
    assert first.scene.primitives == second.scene.primitives
    assert api.tail_lower_v_first_stage_mesh(first) != api.tail_lower_v_first_stage_mesh(second)


def test_snapshot_reopen_retains_per_corner_real_bend_identity(actual_tail, tmp_path):
    spec, raw = actual_tail
    original, saved = _selected(spec, raw, "y")
    path = write_project(tmp_path / "tail-real-y-y.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": saved,
    })
    reopened = read_project(path)["snapshot"]
    assert reopened[api.TAIL_LOWER_V_FIRST_BENDS_KEY] == saved[
        api.TAIL_LOWER_V_FIRST_BENDS_KEY
    ]
    selected = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice=reopened[api.TAIL_LOWER_V_SNAPSHOT_KEY],
        first_bends=reopened[api.TAIL_LOWER_V_FIRST_BENDS_KEY],
    )
    assert selected.metadata["tail_lower_v_operator_first_axis"] == "y"
    assert api.tail_lower_v_first_stage_mesh(selected)
    restored = api.commit_operator_tail_lower_v_choice(
        reopened, "original", tail_scene_values=reopened,
    )
    assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in restored
    assert api.TAIL_LOWER_V_FIRST_BENDS_KEY not in restored
    assert restored["model"] == original["model"]
    assert restored["ybottom1"] == original["ybottom1"]
    assert restored["w"] == original["w"]
    assert restored["d"] == original["d"]


@pytest.mark.parametrize("selection,code", (
    ({"bottom_left": "x"}, "PARTIAL"),
    ({"bottom_left": "x", "bottom_right": None}, "PHYSICAL_LINE"),
    ({"bottom_left": "x", "bottom_right": "y"}, "MIXED"),
    ({"bottom_left": "y", "bottom_right": "x"}, "MIXED"),
    ({}, "PARTIAL"),
))
def test_partial_mixed_or_undefined_choices_cannot_be_auto_selected(
    actual_tail, selection, code,
):
    spec, raw = actual_tail
    prior, _ = _selected(spec, raw, "x")
    with pytest.raises(GeometryError, match=code):
        api.commit_operator_tail_lower_v_first_bends(
            prior, selection, spec=spec, render_data=raw,
        )
    assert api.TAIL_LOWER_V_FIRST_BENDS_KEY not in prior


def test_source_bend_drift_or_corrupt_saved_pair_rejected(actual_tail):
    spec, raw = actual_tail
    _, saved = _selected(spec, raw, "x")
    recorded = saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY]
    moved = deepcopy(recorded)
    moved["bottom_left"]["x"][0][0] += 0.2
    with pytest.raises(GeometryError, match="SOURCE_CHANGED"):
        api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90", first_bends=moved,
        )
    incomplete = deepcopy(recorded)
    incomplete.pop("bottom_right")
    with pytest.raises(GeometryError, match="STORED_SOURCE_INVALID"):
        api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90", first_bends=incomplete,
        )
    mixed = deepcopy(recorded)
    mixed["bottom_right"]["first"] = "y"
    with pytest.raises(GeometryError, match="MIXED"):
        api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90", first_bends=mixed,
        )
    # Change an ACTUAL original BEND line, not only the persisted label.
    src = next(p for p in raw.scene.primitives
               if isinstance(p, LinePrimitive) and p.layer == "BEND"
               and p.p1.x == p.p2.x)
    shifted = replace(src, p1=Vec2(src.p1.x + 0.2, src.p1.y),
                      p2=Vec2(src.p2.x + 0.2, src.p2.y))
    scene = DrawingScene([
        shifted if p is src else p for p in raw.scene.primitives
    ])
    changed = PartRenderData(
        scene=scene, material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    with pytest.raises(GeometryError, match="SOURCE_CHANGED"):
        api.validate_operator_tail_lower_v_first_bends(
            recorded, spec=spec, render_data=changed,
        )


@pytest.mark.parametrize("axis", (None, "x", "y"))
def test_active_v_labels_use_drawn_extended_bends_not_saved_source(
    actual_tail, axis,
):
    spec, raw = actual_tail
    source_options = api.project_operator_tail_lower_v_first_bend_options(
        spec, raw,
    )
    selected = (
        _selected(spec, raw, axis)[1][api.TAIL_LOWER_V_FIRST_BENDS_KEY]
        if axis is not None else None
    )
    active = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice="v90", first_bends=selected,
    )
    visible = api.project_operator_tail_lower_v_first_bend_options(
        spec, raw, active_v_render_data=active,
    )
    assert visible["source_bends"] == source_options["source_bends"]
    assert active.material.bounds == pytest.approx((0., 0., 642., 268.))
    for corner, x in (("bottom_left", 15.), ("bottom_right", 627.)):
        # The persistent BEFORE-V fold remains Y=49..225.
        original_x = [[x, 49.], [x, 225.]]
        final_x = [[x, 0.], [x, 225.]]
        assert source_options[corner]["x"]["bend"] == original_x
        assert visible[corner]["x"]["bend"] == original_x
        assert visible[corner]["x"]["display_bend"] == final_x
        assert visible[corner]["x"]["label"] == (
            f"側折線 X ({x:g},0)－({x:g},225) mm"
        )
        assert visible[corner]["x"]["label"] != source_options[corner]["x"]["label"]
        # Lower Y is unchanged in both physical scenes.
        assert visible[corner]["y"]["bend"] == source_options[corner]["y"]["bend"]
        assert visible[corner]["y"]["display_bend"] == source_options[corner]["y"]["bend"]
        assert visible[corner]["y"]["label"] == source_options[corner]["y"]["label"]
        # Display endpoints are actual unmodified BEND primitives in V FinalScene.
        assert any(
            isinstance(line, LinePrimitive) and line.layer == "BEND"
            and sorted((
                [round(line.p1.x, 7), round(line.p1.y, 7)],
                [round(line.p2.x, 7), round(line.p2.y, 7)],
            )) == final_x
            for line in active.scene.primitives
        )
    if selected is not None:
        assert api.validate_operator_tail_lower_v_first_bends(
            selected, spec=spec, render_data=raw,
        ) == axis
        assert api.tail_lower_v_first_stage_mesh(active)
    else:
        assert api.tail_lower_v_first_stage_mesh(active) is None
    assert api.tail_lower_v_preview_mesh(active)
    with pytest.raises(ValueError, match="禁止加工|尚未核准"):
        api.reject_tail_lower_v_preview_for_dxf(active)


def test_only_active_v_final_scene_may_override_bend_labels(actual_tail):
    spec, raw = actual_tail
    with pytest.raises(GeometryError, match="ACTIVE_V_FINAL_SCENE_REQUIRED"):
        api.project_operator_tail_lower_v_first_bend_options(
            spec, raw, active_v_render_data=raw,
        )
    active = api.project_operator_tail_lower_v_preview_render(
        spec, raw, choice="v90",
    )
    # An invalid active line cannot become an accepted source or GUI label.
    x_line = next(
        line for line in active.scene.primitives
        if isinstance(line, LinePrimitive) and line.layer == "BEND"
        and line.p1.x == line.p2.x and round(line.p1.x, 7) == 15.
    )
    altered = replace(
        x_line,
        p1=Vec2(x_line.p1.x, 55.),
    )
    changed = replace(
        active,
        scene=DrawingScene(
            [altered if line is x_line else line for line in active.scene.primitives]
        ),
    )
    # The Engine accepts only a line actually seen in the active V
    # FinalScene; it must not relabel, save, or alter original BEND.
    with pytest.raises(GeometryError, match="ACTIVE_V_SOURCE_MISMATCH"):
        api.project_operator_tail_lower_v_first_bend_options(
            spec, raw, active_v_render_data=changed,
        )


def test_same_finite_bends_do_not_authorize_changed_signed_angles(actual_tail, tmp_path):
    from ae_engine.v_miter_operator_gui_check import _endcap_existing_fold_angle_sources

    spec, raw = actual_tail
    snapshot, saved = _selected(spec, raw, "y")
    saved_key = api.TAIL_LOWER_V_FIRST_BENDS_KEY
    path = write_project(tmp_path / "authored-angle-source.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": saved,
    })
    reopened = read_project(path)["snapshot"]
    assert reopened[saved_key] == saved[saved_key]
    x, y = _endcap_existing_fold_angle_sources(spec, "tail")
    changes = [
        (x, tuple(replace(p, angle=-60.) if p.phase6_key == "ybottom1" else p for p in y),
         "AUTHORED_FOLD_NOT_90"),
        (tuple(replace(p, angle=-p.angle) if p.angle is not None else p for p in x),
         tuple(replace(p, angle=-p.angle) if p.angle is not None else p for p in y),
         "AUTHORED_FOLD_SENSE_UNSUPPORTED"),
    ]
    raw_bends = tuple(p for p in raw.scene.primitives if p.layer == "BEND")
    for authored_x, authored_y, code in changes:
        changed = replace(spec, fold_profile_x=authored_x, fold_profile_y=authored_y)
        with pytest.raises(GeometryError, match=code):
            api.commit_operator_tail_lower_v_first_bends(
                snapshot, dict.fromkeys(("bottom_left", "bottom_right"), "y"),
                spec=changed, render_data=raw,
            )
        with pytest.raises(GeometryError, match=code):
            api.validate_operator_tail_lower_v_first_bends(
                reopened[saved_key], spec=changed, render_data=raw,
            )
        with pytest.raises(GeometryError, match=code):
            api.build_operator_tail_d4_check_from_original(
                changed, original_render_data=raw,
            )
        assert tuple(p for p in raw.scene.primitives if p.layer == "BEND") == raw_bends
    assert api.validate_operator_tail_lower_v_first_bends(
        reopened[saved_key], spec=spec, render_data=raw,
    ) == "y"
