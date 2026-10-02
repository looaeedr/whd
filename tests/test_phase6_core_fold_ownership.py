# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene


def _snapshot():
    return {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
    }


def test_semantic_core_selects_endcap_d_core_for_head_and_native_tail():
    head = bridge.build_endcap_xy_profiles(_snapshot(), part_key="head")["Y"]
    tail = bridge.build_endcap_xy_profiles(_snapshot(), part_key="tail")["Y"]

    assert bridge._phase6_profile_base_index(head) == 2
    assert bridge._phase6_profile_base_index(tail) == 1

    for profile in (head, tail):
        boundaries, folded = bridge._phase6_profile_geometry(profile)
        idx = bridge._phase6_profile_base_index(profile)
        assert boundaries[idx + 1] - boundaries[idx] == pytest.approx(244.0)
        assert folded[idx][1] == pytest.approx(0.0)
        assert folded[idx + 1][1] == pytest.approx(0.0)
        assert abs(folded[idx + 1][0] - folded[idx][0]) == pytest.approx(244.0)


def _head_scene_with_real_bend_coverage():
    scene = DrawingScene()
    scene.add_polyline(
        [(0, 0), (422, 0), (422, 300), (0, 300)], layer="CUTTING", closed=True
    )
    # X folds are shortened by corner reliefs.
    scene.add_line((15, 43), (15, 284), layer="BEND")
    scene.add_line((407, 43), (407, 284), layer="BEND")
    # Head native Y folds from the uploaded diagnostic.
    scene.add_line((40, 16), (382, 16), layer="BEND")
    scene.add_line((16, 41), (406, 41), layer="BEND")
    scene.add_line((16, 285), (406, 285), layer="BEND")
    return scene


def test_part_render_data_exposes_final_bend_guides():
    scene = _head_scene_with_real_bend_coverage()
    guides = manufacturing_api.fold_guides_from_final_scene(scene)

    assert manufacturing_api.FoldGuide("y", 16.0, 40.0, 382.0) in guides
    assert manufacturing_api.FoldGuide("y", 41.0, 16.0, 406.0) in guides
    assert manufacturing_api.FoldGuide("x", 15.0, 43.0, 284.0) in guides


def test_retained_shoulder_skips_only_uncovered_bend_not_entire_y_folding():
    profile = bridge.build_endcap_xy_profiles(_snapshot(), part_key="head")["Y"]
    guides = manufacturing_api.fold_guides_from_final_scene(_head_scene_with_real_bend_coverage())

    # At x=100 all three horizontal BEND lines physically exist.
    full = bridge._phase6_profile_map_with_guides(
        8.0, 100.0, profile, axis="y", fold_guides=guides
    )
    legacy_boundaries, legacy_folded = bridge._phase6_profile_geometry(profile)
    legacy = bridge._phase6_profile_map(8.0, legacy_boundaries, legacy_folded)
    assert full == pytest.approx(legacy)

    # At x=20 the y=16 BEND line does NOT exist, but y=41 still exists.
    retained = bridge._phase6_profile_map_with_guides(
        8.0, 20.0, profile, axis="y", fold_guides=guides
    )
    flat = bridge._phase6_profile_flat_map(8.0, legacy_boundaries, profile=profile)

    assert retained != pytest.approx(legacy)
    assert retained != pytest.approx(flat)
    # This specifically proves we did not flatten all Y folding just because one
    # retained step lacks its local bend line.
    assert abs(retained[1]) > 1e-6


def test_mesh_uses_bend_coverage_so_retained_strip_skips_only_local_fold():
    from shapely.geometry import box

    y_profile = bridge.build_endcap_xy_profiles(_snapshot(), part_key="head")["Y"]
    x_profile = [{"len": 422.0, "core": "W"}]
    guides = manufacturing_api.fold_guides_from_final_scene(_head_scene_with_real_bend_coverage())

    retained = bridge._phase6_folded_mesh_from_polygon(
        box(18, 4, 22, 12), x_profile, y_profile, fold_guides=guides
    )
    ordinary = bridge._phase6_folded_mesh_from_polygon(
        box(98, 4, 102, 12), x_profile, y_profile, fold_guides=guides
    )

    retained_z = {round(p[2], 6) for tri in retained for p in tri}
    ordinary_z = {round(p[2], 6) for tri in ordinary for p in tri}
    assert retained_z != ordinary_z
    assert max(abs(z) for z in retained_z) > 1.0  # later y=41 fold still applies
