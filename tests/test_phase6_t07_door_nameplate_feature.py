from __future__ import annotations

from pathlib import Path

import pytest


def _vault_door_spec(*, model_name="金庫型", datum=None):
    from ae_engine.contracts import DoorPartSpec
    return DoorPartSpec(
        width=800, height=1600, thickness=2, frame_width=29,
        model_name=model_name, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
        nameplate_center_datum_top=datum,
    )


def _nameplate_circles(scene):
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    return tuple(
        p for p in scene.primitives
        if isinstance(p, CirclePrimitive) and getattr(p, "source_type", None) == "nameplate_mount"
    )


def test_vault_baseline_door_pair_is_featureized_as_nameplate_mount():
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene
    root = Path(__file__).resolve().parents[1]
    scene = build_part_scene(_vault_door_spec(), ManufacturingContext(resource_root=root))
    circles = _nameplate_circles(scene)
    assert len(circles) == 2
    assert tuple(sorted(getattr(c, "source_id", "") for c in circles)) == (
        "door:nameplate_mount:left", "door:nameplate_mount:right"
    )


def test_receiving_reuses_vault_baseline_resolver_and_applies_top_datum_140():
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene, door_finished_face_size
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide
    root = Path(__file__).resolve().parents[1]
    spec = _vault_door_spec(model_name="受電箱", datum=140)
    scene = build_part_scene(spec, ManufacturingContext(resource_root=root))
    circles = _nameplate_circles(scene)
    assert len(circles) == 2

    fw, fh = door_finished_face_size(spec, ManufacturingContext(resource_root=root))
    structural = build_door_result(
        w=spec.width, h=spec.height, t=spec.thickness, fw=spec.frame_width,
        gap_w=spec.gap_w, gap_h=spec.gap_h,
        fold_left=spec.fold_left, fold_right=spec.fold_right,
        fold_top=spec.fold_top, fold_bottom=spec.fold_bottom,
        frame_edges=spec.frame_edges,
    )
    guide = build_finished_reference_guide("door", structural, finished_width=fw, finished_height=fh)
    expected_y = guide.min_point.y + fh - 140.0
    assert {round(c.center.y, 6) for c in circles} == {round(expected_y, 6)}
    # X remains whatever the certified baseline feature resolver produces;
    # the family datum override changes only the canonical top-distance Y.
    assert circles[0].center.x < circles[1].center.x


def test_receiving_family_default_nameplate_datum_is_140():
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene, door_finished_face_size
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide
    root = Path(__file__).resolve().parents[1]
    spec = _vault_door_spec(model_name="受電箱", datum=None)
    ctx = ManufacturingContext(resource_root=root)
    scene = build_part_scene(spec, ctx)
    circles = _nameplate_circles(scene)
    fw, fh = door_finished_face_size(spec, ctx)
    structural = build_door_result(
        w=spec.width, h=spec.height, t=spec.thickness, fw=spec.frame_width,
        gap_w=spec.gap_w, gap_h=spec.gap_h, fold_left=spec.fold_left, fold_right=spec.fold_right,
        fold_top=spec.fold_top, fold_bottom=spec.fold_bottom, frame_edges=spec.frame_edges,
    )
    guide = build_finished_reference_guide("door", structural, finished_width=fw, finished_height=fh)
    assert {round(c.center.y - guide.min_point.y, 6) for c in circles} == {round(fh - 140.0, 6)}


def test_same_datum_has_same_feature_local_coordinates_across_families():
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene, door_finished_face_size
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide
    root = Path(__file__).resolve().parents[1]
    ctx = ManufacturingContext(resource_root=root)

    local_sets = []
    for model in ("金庫型", "受電箱"):
        spec = _vault_door_spec(model_name=model, datum=140)
        scene = build_part_scene(spec, ctx)
        circles = _nameplate_circles(scene)
        fw, fh = door_finished_face_size(spec, ctx)
        structural = build_door_result(
            w=spec.width, h=spec.height, t=spec.thickness, fw=spec.frame_width,
            gap_w=spec.gap_w, gap_h=spec.gap_h,
            fold_left=spec.fold_left, fold_right=spec.fold_right,
            fold_top=spec.fold_top, fold_bottom=spec.fold_bottom,
            frame_edges=spec.frame_edges,
        )
        guide = build_finished_reference_guide("door", structural, finished_width=fw, finished_height=fh)
        local_sets.append(tuple(sorted((round(c.center.x-guide.min_point.x,6), round(c.center.y-guide.min_point.y,6)) for c in circles)))
    assert local_sets[0] == local_sets[1]


def test_nameplate_feature_identity_survives_scene_mirroring():
    from ae_engine.sheetmetal_drawing import DrawingScene, mirror_drawing_scene_x, mirror_drawing_scene_y
    scene = DrawingScene()
    scene.add_circle((10, 20), 1.6, layer="CUTTING", source_type="nameplate_mount", source_id="door:nameplate_mount:left")
    mx = mirror_drawing_scene_x(scene, 0, 100)
    my = mirror_drawing_scene_y(scene, 200)
    for mirrored in (mx, my):
        circle = _nameplate_circles(mirrored)[0]
        assert circle.source_id == "door:nameplate_mount:left"
