# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    BoxBodyPartSpec,
    EndCapAssemblyReliefRequest,
    EndCapPartSpec,
)
from ae_engine.assembly_collision import detect_planar_collision


def _box_body_spec():
    return BoxBodyPartSpec(
        width=100,
        height=50,
        depth=30,
        thickness=2,
        frame_width=5,
        zl1=15,
        zl2=20,
        zr1=15,
        zr2=20,
        z_comp=0,
    )


def test_endcap_part_spec_assembly_relief_is_opt_in_and_removes_boxbody_collision():
    box_body = _box_body_spec()
    plain_endcap = EndCapPartSpec(
        width=100,
        depth=50,
        thickness=2,
        frame_width=5,
    )
    relieved_endcap = EndCapPartSpec(
        width=100,
        depth=50,
        thickness=2,
        frame_width=5,
        assembly_relief=EndCapAssemblyReliefRequest(
            box_body=box_body,
            clearance=0.0,
        ),
    )

    plain = manufacturing_api.build_part_render_data(plain_endcap)
    relieved = manufacturing_api.build_part_render_data(relieved_endcap)
    box_render = manufacturing_api.build_part_render_data(box_body)

    assert detect_planar_collision(
        box_body_material=box_render.material,
        endcap_material=plain.material,
    ) is not None
    assert detect_planar_collision(
        box_body_material=box_render.material,
        endcap_material=relieved.material,
    ) is None
    assert relieved.material.area < plain.material.area


def test_disabled_endcap_assembly_relief_preserves_existing_render_data():
    box_body = _box_body_spec()
    plain_endcap = EndCapPartSpec(
        width=100,
        depth=50,
        thickness=2,
        frame_width=5,
    )
    disabled_endcap = EndCapPartSpec(
        width=100,
        depth=50,
        thickness=2,
        frame_width=5,
        assembly_relief=EndCapAssemblyReliefRequest(
            box_body=box_body,
            clearance=0.0,
            enabled=False,
        ),
    )

    plain = manufacturing_api.build_part_render_data(plain_endcap)
    disabled = manufacturing_api.build_part_render_data(disabled_endcap)

    assert disabled.material.equals_exact(plain.material, tolerance=1e-7)


def test_standard_vault_head_world_backprojection_replaces_fixed_relief_and_verifies_3d():
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import build_box_body_profile, build_endcap_xy_profiles

    snapshot = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 24.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
    }
    box_spec = BoxBodyPartSpec(
        width=500.0, height=600.0, depth=200.0, thickness=2.0,
        frame_width=24.0, zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=0.0,
    )
    head_spec = EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=24.0,
        is_tail=False,
    )
    body = manufacturing_api.build_part_render_data(box_spec)
    head = manufacturing_api.build_part_render_data(head_spec)
    profiles = build_endcap_xy_profiles(snapshot, part_key="head")

    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=head,
        box_body_x_profile=build_box_body_profile(snapshot),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(500.0, 600.0, 200.0),
        endcap_placement="top",
        sheet_thickness=2.0,
        clearance=0.0,
    )

    assert solution.verified is True
    assert solution.corner_reliefs
    assert solution.cut_polygon_2d is not None
    assert solution.solved_render_data.material.area >= head.material.area
    original_holes = sum(len(p.interiors) for p in ([head.material] if head.material.geom_type == "Polygon" else head.material.geoms))
    solved = solution.solved_render_data.material
    solved_holes = sum(len(p.interiors) for p in ([solved] if solved.geom_type == "Polygon" else solved.geoms))
    assert solved_holes == original_holes


def _standard_vault_world_relief_solution(*, part_key: str, clearance: float = 0.0):
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import build_box_body_profile, build_endcap_xy_profiles

    snapshot = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 24.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
    }
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=500.0, height=600.0, depth=200.0, thickness=2.0,
        frame_width=24.0, zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=0.0,
    ))
    is_tail = part_key == "tail"
    endcap = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=24.0,
        is_tail=is_tail,
    ))
    profiles = build_endcap_xy_profiles(snapshot, part_key=part_key)
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=build_box_body_profile(snapshot),
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(500.0, 600.0, 200.0),
        endcap_placement="bottom" if is_tail else "top",
        sheet_thickness=2.0,
        clearance=clearance,
    )
    return endcap, solution


def test_standard_vault_tail_world_backprojection_verifies_and_preserves_holes():
    endcap, solution = _standard_vault_world_relief_solution(part_key="tail", clearance=0.0)

    assert solution.verified is True
    measurements = {item.corner_name: item.measurement for item in solution.corner_reliefs}
    assert set(measurements) == {"top_left", "top_right"}
    for measurement in measurements.values():
        assert measurement.primary_u == pytest.approx(39.0, abs=1e-4)
        assert measurement.primary_v == pytest.approx(38.0, abs=1e-4)
        assert measurement.secondary_u == pytest.approx(14.0, abs=1e-4)
        assert measurement.secondary_depth == pytest.approx(4.0, abs=1e-2)

    original_holes = sum(
        len(poly.interiors)
        for poly in ([endcap.material] if endcap.material.geom_type == "Polygon" else endcap.material.geoms)
    )
    solved = solution.solved_render_data.material
    solved_holes = sum(
        len(poly.interiors)
        for poly in ([solved] if solved.geom_type == "Polygon" else solved.geoms)
    )
    assert solved_holes == original_holes


def test_standard_vault_tail_mirrored_corners_are_numerically_harmonized():
    _endcap, solution = _standard_vault_world_relief_solution(part_key="tail", clearance=0.0)

    assert solution.verified is True
    measurements = {item.corner_name: item.measurement for item in solution.corner_reliefs}
    left = measurements["top_left"]
    right = measurements["top_right"]
    assert left.primary_u == pytest.approx(right.primary_u, abs=1e-7)
    assert left.primary_v == pytest.approx(right.primary_v, abs=1e-7)
    assert left.secondary_u == pytest.approx(right.secondary_u, abs=1e-7)
    assert left.secondary_depth == pytest.approx(right.secondary_depth, abs=1e-7)


def test_standard_vault_clearance_a_changes_real_cut_dimensions_and_keeps_3d_verified():
    _endcap0, zero = _standard_vault_world_relief_solution(part_key="head", clearance=0.0)
    _endcap5, gap = _standard_vault_world_relief_solution(part_key="head", clearance=5.0)

    assert zero.verified is True
    assert gap.verified is True
    assert gap.cut_polygon_2d.area > zero.cut_polygon_2d.area
    zero_measurements = {item.corner_name: item.measurement for item in zero.corner_reliefs}
    gap_measurements = {item.corner_name: item.measurement for item in gap.corner_reliefs}
    assert set(gap_measurements) == set(zero_measurements)
    for corner_name, before in zero_measurements.items():
        after = gap_measurements[corner_name]
        assert after.clearance_a == pytest.approx(5.0)
        assert after.primary_u == pytest.approx(before.primary_u + 5.0, abs=1e-4)
        assert after.primary_v == pytest.approx(before.primary_v + 5.0, abs=1e-4)
        assert after.secondary_u == pytest.approx(before.secondary_u + 5.0, abs=1e-4)


def test_verified_world_relief_reclips_authoritative_bends_to_new_material():
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments

    snapshot = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 24.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
    }
    profiles = build_endcap_xy_profiles(snapshot, part_key="head")
    profile_x = profile_to_fold_segments(profiles["X"])
    profile_y = profile_to_fold_segments(profiles["Y"])

    plain = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=24.0,
        is_tail=False, fold_profile_x=profile_x, fold_profile_y=profile_y,
    ))
    _endcap, solution = _standard_vault_world_relief_solution(part_key="head", clearance=0.0)
    cut_polygons = getattr(solution.cut_polygon_2d, "geoms", (solution.cut_polygon_2d,))
    cuts = tuple(
        tuple((float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1])
        for poly in cut_polygons
    )
    solved = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=24.0,
        is_tail=False, fold_profile_x=profile_x, fold_profile_y=profile_y,
        resolved_assembly_relief_cuts=cuts,
    ))

    def guide(data, axis, position):
        return next(
            item for item in data.fold_guides
            if item.axis == axis and abs(float(item.position) - float(position)) <= 1e-7
        )

    # The verified 3D cut retains material that the legacy fixed relief used to
    # remove. Re-clipping from the authoritative fold profile must therefore
    # restore those BEND spans instead of preserving the shorter legacy guides.
    plain_left = guide(plain, "x", 15.0)
    solved_left = guide(solved, "x", 15.0)
    assert plain_left.span_start == pytest.approx(42.0, abs=1e-7)
    assert solved_left.span_start == pytest.approx(38.0, abs=1e-7)

    plain_fw = guide(plain, "y", 40.0)
    solved_fw = guide(solved, "y", 40.0)
    assert plain_fw.span_start == pytest.approx(16.0, abs=1e-7)
    # The collision solver/refold path uses micron-scale contact tolerances.
    # Re-clipping must restore the bend to the same manufacturing location;
    # sub-0.00002 mm triangulation drift is numerical, not a geometry change.
    assert solved_fw.span_start == pytest.approx(14.0, abs=2e-5)


def test_endcap_part_spec_verified_relief_cut_replaces_legacy_fixed_corner_cut_in_manufacturing_data():
    from shapely.geometry import box as sbox
    from ae_engine.assembly_geometry import restore_unrelieved_endcap_material

    plain_spec = EndCapPartSpec(
        width=100.0, depth=80.0, thickness=2.0, frame_width=24.0, is_tail=False,
    )
    plain = manufacturing_api.build_part_render_data(plain_spec)
    restored = restore_unrelieved_endcap_material(plain.material)
    minx, miny, _maxx, _maxy = restored.bounds
    dynamic_cut = sbox(minx, miny, minx + 7.0, miny + 9.0)
    coords = tuple((float(x), float(y)) for x, y in list(dynamic_cut.exterior.coords)[:-1])

    spec = EndCapPartSpec(
        width=100.0, depth=80.0, thickness=2.0, frame_width=24.0, is_tail=False,
        resolved_assembly_relief_cuts=(coords,),
    )
    resolved = manufacturing_api.build_part_render_data(spec)
    from ae_engine.assembly_collision import apply_verified_endcap_relief_material
    expected = apply_verified_endcap_relief_material(plain.material, (dynamic_cut,))

    assert resolved.material.symmetric_difference(expected).area == pytest.approx(0.0, abs=1e-7)
    # Only the legacy corner component actually replaced by the verified cut may
    # be restored.  Unrelated fixed-corner cuts remain material-absent.
    assert resolved.material.difference(plain.material).area > 0.0


def test_verified_relief_replay_matches_world_solver_material_and_keeps_unrelated_legacy_corners_cut():
    """2D/DXF replay must reconstruct the exact same material accepted by the 3D solver."""
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments

    snapshot = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 24.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
    }
    profiles = build_endcap_xy_profiles(snapshot, part_key="head")
    base, solution = _standard_vault_world_relief_solution(part_key="head", clearance=0.0)
    assert solution.verified is True
    cuts = tuple(
        tuple((float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1])
        for poly in getattr(solution.cut_polygon_2d, "geoms", (solution.cut_polygon_2d,))
    )
    replay = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=500.0, depth=200.0, thickness=2.0, frame_width=24.0,
        is_tail=False,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        resolved_assembly_relief_cuts=cuts,
    ))

    assert replay.material.symmetric_difference(solution.solved_render_data.material).area == pytest.approx(0.0, abs=1e-6)
    # Regression for the two unrelated 16x16 corner tabs that 2D replay used to resurrect.
    assert replay.material.area == pytest.approx(solution.solved_render_data.material.area, abs=1e-6)


def test_world_backprojected_relief_restores_only_the_two_solved_mating_corners():
    """Unrelated legacy corner relief must not reappear as 16x16 corner tabs."""
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
    from phase6_fold_profiles import build_box_body_profile, build_endcap_xy_profiles

    snapshot = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
    }
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400.0, height=600.0, depth=250.0, thickness=2.0,
        frame_width=25.0, zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=0.0,
    ))

    for part_key, is_tail, placement in (("head", False, "top"), ("tail", True, "bottom")):
        original = manufacturing_api.build_part_render_data(EndCapPartSpec(
            width=400.0, depth=250.0, thickness=2.0, frame_width=25.0,
            is_tail=is_tail,
        ))
        profiles = build_endcap_xy_profiles(snapshot, part_key=part_key)
        solution = solve_world_backprojected_endcap_relief(
            box_body_render_data=body,
            endcap_render_data=original,
            box_body_x_profile=build_box_body_profile(snapshot),
            endcap_x_profile=profiles["X"],
            endcap_y_profile=profiles["Y"],
            finished_dimensions=(400.0, 600.0, 250.0),
            endcap_placement=placement,
            sheet_thickness=2.0,
            clearance=0.0,
        )

        assert solution.verified is True
        added = solution.solved_render_data.material.difference(original.material)
        # Only the 2 mm x 4 mm material retained at each newly-solved corner
        # may be added back.  The opposite pair of legacy 16x16 corner cuts
        # must remain cut out.
        assert added.area == pytest.approx(16.0, abs=1e-3)
        minx, miny, maxx, maxy = map(float, added.bounds)
        if part_key == "head":
            assert maxy < 50.0
        else:
            assert miny > 250.0


def test_deleted_fold_insert_relief_keeps_single_stage_topology_across_iterations():
    """Iterative 3D evidence must resize INSERT relief, never invent a second stage."""
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
    from ae_engine.sheetmetal_geometry import (
        CornerTypeId,
        CornerTypeSelection,
        CrossCornerMode,
        FourCornerTypePolicy,
    )
    from phase6_fold_profiles import profile_to_fold_segments

    box_profile = [
        {"len": 25, "angle": -90, "phase6_key": "fw_left", "ui_len_add": 2.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_left", "ui_len_add": 4.0},
        {"len": 396, "angle": -90, "core": "W", "phase6_key": "w", "ui_len_add": 4.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_right", "ui_len_add": 4.0},
        {"len": 25, "phase6_key": "fw_right", "ui_len_add": 2.0},
    ]
    endcap_profiles = {
        "head": {
            "X": [
                {"len": 15, "angle": -90, "phase6_key": "yl1", "ui_len_add": 2.0},
                {"len": 392, "angle": -90, "phase6_key": "endcap_w_core", "core": "W-2T", "ui_len_add": 4.0},
                {"len": 15, "phase6_key": "yr1", "ui_len_add": 2.0},
            ],
            "Y": [
                {"len": 25, "angle": -90, "phase6_key": "fw", "ui_len_add": 2.0},
                {"len": 244, "angle": -90, "phase6_key": "endcap_d_core", "core": "D-T", "ui_len_add": 4.0},
                {"len": 15, "phase6_key": "ybottom1", "ui_len_add": 2.0},
            ],
        },
        "tail": {
            "X": [
                {"len": 15, "angle": -90, "phase6_key": "yl1", "ui_len_add": 2.0},
                {"len": 392, "angle": -90, "phase6_key": "endcap_w_core", "core": "W-2T", "ui_len_add": 4.0},
                {"len": 15, "phase6_key": "yr1", "ui_len_add": 2.0},
            ],
            "Y": [
                {"len": 15, "angle": -90, "phase6_key": "ybottom1", "ui_len_add": 2.0},
                {"len": 244, "angle": -90, "phase6_key": "endcap_d_core", "core": "D-T", "ui_len_add": 4.0},
                {"len": 25, "phase6_key": "fw", "ui_len_add": 2.0},
            ],
        },
    }
    cross = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    insert = CornerTypeSelection(CornerTypeId.INSERT)
    policy = FourCornerTypePolicy(cross, cross, insert, insert, 25.0)
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        fold_profile=profile_to_fold_segments(box_profile),
        head_corner_policy=policy, tail_corner_policy=policy,
        head_ybottom1=15, tail_ybottom1=15,
    ))

    for part_key in ("head", "tail"):
        is_tail = part_key == "tail"
        profiles = endcap_profiles[part_key]
        endcap = manufacturing_api.build_part_render_data(EndCapPartSpec(
            width=400, height=600, depth=250, thickness=2, frame_width=25,
            is_tail=is_tail,
            fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
            box_fold_left=15, box_fold_right=15,
            fold_profile_x=profile_to_fold_segments(profiles["X"]),
            fold_profile_y=profile_to_fold_segments(profiles["Y"]),
            corner_policy=policy,
        ))
        solution = solve_world_backprojected_endcap_relief(
            box_body_render_data=body,
            endcap_render_data=endcap,
            box_body_x_profile=box_profile,
            endcap_x_profile=profiles["X"],
            endcap_y_profile=profiles["Y"],
            finished_dimensions=(400, 600, 250),
            endcap_placement="bottom" if is_tail else "top",
            sheet_thickness=2,
            clearance=0,
        )

        assert solution.verified is True
        assert len(solution.corner_reliefs) == 2
        for relief in solution.corner_reliefs:
            assert relief.measurement.primary_u == pytest.approx(38.0, abs=1e-6)
            assert relief.measurement.primary_v == pytest.approx(27.0, abs=1e-6)
            assert relief.measurement.secondary_u is None
            assert relief.measurement.secondary_depth is None


def test_user8_tail_insert_relief_stays_single_stage_and_refolds_without_penetration():
    """Regression from 自訂(8): Tail top INSERT must stay one stage and still verify in 3D."""
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
    from ae_engine.sheetmetal_geometry import (
        CornerDirection,
        CornerTypeId,
        CornerTypeSelection,
        CrossCornerMode,
        FourCornerTypePolicy,
    )
    from phase6_fold_profiles import profile_to_fold_segments

    box_profile = [
        {"len": 25, "angle": -90, "phase6_key": "fw_left", "ui_len_add": 2.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_left", "ui_len_add": 4.0},
        {"len": 396, "angle": -90, "core": "W", "phase6_key": "w", "ui_len_add": 4.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_right", "ui_len_add": 4.0},
        {"len": 25, "phase6_key": "fw_right", "ui_len_add": 2.0},
    ]
    tail_x = [
        {"len": 15, "angle": -90, "phase6_key": "yl1", "ui_len_add": 2.0},
        {"len": 392, "angle": -90, "phase6_key": "endcap_w_core", "core": "W-2T", "ui_len_add": 4.0},
        {"len": 15, "phase6_key": "yr1", "ui_len_add": 2.0},
    ]
    tail_y = [
        {"len": 15, "angle": -90, "phase6_key": "ybottom1", "ui_len_add": 2.0},
        {"len": 244, "angle": -90, "phase6_key": "endcap_d_core", "core": "D-T", "ui_len_add": 4.0},
        {"len": 25, "phase6_key": "fw", "ui_len_add": 2.0},
    ]
    insert = CornerTypeSelection(CornerTypeId.INSERT, direction=CornerDirection.HEIGHT, amount_t=1.0)
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    )
    tail_policy = FourCornerTypePolicy(bottom, bottom, insert, insert, 25.0)
    # Head policy only affects the opposite box-body vertical edge. Match 自訂(8): bottom is STANDARD.
    head_bottom = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    head_policy = FourCornerTypePolicy(head_bottom, head_bottom, insert, insert, 25.0)
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        fold_profile=profile_to_fold_segments(box_profile),
        head_corner_policy=head_policy, tail_corner_policy=tail_policy,
        head_ybottom1=15, tail_ybottom1=15,
    ))
    tail = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        is_tail=True, fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=15, box_fold_right=15,
        fold_profile_x=profile_to_fold_segments(tail_x),
        fold_profile_y=profile_to_fold_segments(tail_y),
        corner_policy=tail_policy,
    ))

    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=tail,
        box_body_x_profile=box_profile,
        endcap_x_profile=tail_x,
        endcap_y_profile=tail_y,
        finished_dimensions=(400, 600, 250),
        endcap_placement="bottom",
        sheet_thickness=2,
        clearance=0,
    )

    assert solution.verified is True
    assert len(solution.corner_reliefs) == 2
    for relief in solution.corner_reliefs:
        assert relief.measurement.secondary_u is None
        assert relief.measurement.secondary_depth is None


def test_user10_insert_overlay_without_ytop_fold_treats_cut_boundary_skin_crossings_as_contact():
    """Regression from 自訂(10): no ytop row, INSERT_OVERLAY Head/Tail must both verify."""
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
    from ae_engine.sheetmetal_geometry import (
        CornerDirection, CornerTypeId, CornerTypeSelection,
        CrossCornerMode, FourCornerTypePolicy,
    )
    from phase6_fold_profiles import profile_to_fold_segments

    box_profile = [
        {"len": 25, "angle": -90, "phase6_key": "fw_left", "ui_len_add": 2.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_left", "ui_len_add": 4.0},
        {"len": 396, "angle": -90, "core": "W", "phase6_key": "w", "ui_len_add": 4.0},
        {"len": 246, "angle": -90, "core": "D", "phase6_key": "d_right", "ui_len_add": 4.0},
        {"len": 25, "phase6_key": "fw_right", "ui_len_add": 2.0},
    ]
    x_profile = [
        {"len": 15, "angle": -90, "phase6_key": "yl1", "ui_len_add": 2.0},
        {"len": 392, "angle": -90, "phase6_key": "endcap_w_core", "core": "W-2T", "ui_len_add": 4.0},
        {"len": 15, "phase6_key": "yr1", "ui_len_add": 2.0},
    ]
    head_y = [
        {"len": 25, "angle": -90.0, "phase6_key": "fw", "ui_len_add": 2.0},
        {"len": 244, "angle": -90.0, "phase6_key": "endcap_d_core", "core": "D-T", "ui_len_add": 4.0},
        {"len": 15, "phase6_key": "ybottom1", "ui_len_add": 2.0},
    ]
    tail_y = [
        {"len": 15, "angle": -90.0, "phase6_key": "ybottom1", "ui_len_add": 2.0},
        {"len": 244, "angle": -90.0, "phase6_key": "endcap_d_core", "core": "D-T", "ui_len_add": 4.0},
        {"len": 25, "phase6_key": "fw", "ui_len_add": 2.0},
    ]
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH, amount_t=0.5,
    )
    top = CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY, direction=CornerDirection.HEIGHT,
        amount_t=1.0, secondary_retain_t=0.5, secondary_depth_t=2.0,
    )
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        fold_profile=profile_to_fold_segments(box_profile),
        head_corner_policy=policy, tail_corner_policy=policy,
        head_ybottom1=15, tail_ybottom1=15,
    ))

    for part_key, y_profile in (("head", head_y), ("tail", tail_y)):
        is_tail = part_key == "tail"
        endcap = manufacturing_api.build_part_render_data(EndCapPartSpec(
            width=400, height=600, depth=250, thickness=2, frame_width=25,
            is_tail=is_tail, fold_left=15, fold_right=15, fold_top=0, fold_bottom=15,
            box_fold_left=15, box_fold_right=15,
            fold_profile_x=profile_to_fold_segments(x_profile),
            fold_profile_y=profile_to_fold_segments(y_profile),
            corner_policy=policy,
        ))
        solution = solve_world_backprojected_endcap_relief(
            box_body_render_data=body,
            endcap_render_data=endcap,
            box_body_x_profile=box_profile,
            endcap_x_profile=x_profile,
            endcap_y_profile=y_profile,
            finished_dimensions=(400, 600, 250),
            endcap_placement="bottom" if is_tail else "top",
            sheet_thickness=2,
            clearance=0,
            assembly_intent=CornerTypeId.INSERT_OVERLAY,
            cabinet_family="自訂",
        )
        assert solution.verified is True, part_key
        assert solution.rule_id == "ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1"
        assert solution.rule_revision == 1
        assert solution.trust_level == "CERTIFIED"
        assert len(solution.corner_reliefs) == 2
        for relief in solution.corner_reliefs:
            assert relief.measurement.primary_u == pytest.approx(40.0, abs=2e-4)
            assert relief.measurement.primary_v == pytest.approx(23.0, abs=2e-4)
            assert relief.measurement.secondary_u == pytest.approx(16.0, abs=2e-4)
            assert relief.measurement.secondary_depth == pytest.approx(4.0, abs=2e-4)
