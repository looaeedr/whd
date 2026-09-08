# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from math import copysign

import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import build_box_body_divider_render_data
from ae_engine.sheetmetal_drawing import CirclePrimitive
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part
import fold_designer_bridge as bridge


def _signed_area3(a, b, c):
    return (
        (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1]))
        - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))
    )


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_issue63_receiving_has_three_independent_physical_box_body_fold_editors():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        root.update_idletasks(); root.update()

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        expected = {
            "box_body:left_side": ("zl1", "zl2", "fw_left", "d_left", "side_rear_bend_left"),
            "box_body:back": ("back_panel",),
            "box_body:right_side": ("side_rear_bend_right", "d_right", "fw_right", "zr2"),
        }
        available = tuple(designer.designer_workspace.available_parts)
        print("ISSUE63_AVAILABLE_PARTS=", available)
        for key in expected:
            assert key in available, (
                f"{key} has physical geometry but no independent Fold editor identity",
                available,
            )

        menu = designer.part_choice_menu
        labels = tuple(
            str(menu.entrycget(i, "label"))
            for i in range(int(menu.index("end")) + 1)
        )
        print("ISSUE63_PART_MENU=", labels)
        for label in ("左側板", "後面板", "右側板"):
            assert label in labels

        for key, expected_keys in expected.items():
            profiles = designer.designer_workspace.profiles_for(key, {}) or {}
            x = tuple(profiles.get("X") or ())
            actual_keys = tuple(str(row.get("phase6_key") or "") for row in x)
            print("ISSUE63_PIECE_PROFILE=", key, actual_keys, x)
            assert actual_keys == expected_keys
            designer.activate_part(key)
            root.update_idletasks(); root.update()
            assert designer.designer_workspace.active_part == key
            active_keys = tuple(
                str(row.get("phase6_key") or "")
                for row in tuple(designer.state.profiles.get("X") or ())
            )
            assert active_keys == expected_keys
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()

def test_issue63_divider_baseline_fixed_holes_are_rotated_not_mirrored():
    snap = _snapshot()
    divider = derive_box_body_dividers(
        tuple((float(w), tuple(float(h) for h in hs)) for w, hs in snap["door_layout_columns"]),
        depth=snap["d"], thickness=snap["t"],
        layout_scope=snap["door_layout_scope"], handle_edges={},
        model_name="受電箱", frame_width=snap["fw"],
    )[0]
    render = build_box_body_divider_render_data(divider, context=ManufacturingContext())

    mapped = [
        p for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
        and abs(float(p.radius) - 3.2) <= 1e-6
        and str(getattr(p, "source_type", "")) == "baseline_divider_hole"
    ]
    assert len(mapped) == 3

    # Source 中隔.dxf 6.4 centers in file order.  The baseline adapter contract
    # says rigid rotation, not mirror; rotation preserves oriented handedness.
    source = [
        (4959.91, 1487.86),
        (4959.91, 1525.36),
        (4936.41, 1607.36),
    ]
    target = [(float(p.center.x), float(p.center.y)) for p in mapped]
    source_area = _signed_area3(*source)
    target_area = _signed_area3(*target)
    print("ISSUE63_HOLE_ORIENTATION=", {
        "source": source, "target": target,
        "source_area": source_area, "target_area": target_area,
    })
    assert source_area * target_area > 0, (
        "中隔 fixed-hole transform mirrored the baseline hole pattern; "
        "the adapter contract only permits rigid rotation/translation"
    )



def test_issue63_divider_backprojection_keeps_fold_band_shape_evidence():
    from ae_engine.assembly_collision import project_joint_interference_to_relief_owner
    from tests.test_issue39_divider_relief import _divider_insert_joint

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])
    world = bridge._phase6_build_joint_world_geometry((body, divider_part), dims, snap["t"])
    joint = _divider_insert_joint(divider.stable_id)

    core_start = float(
        dict(divider.physical_geometry_contract)["core_physical_segment"]["flat_band"][0]
    )
    evidence = {}
    for source_key in ("box_body:left_side", "box_body:right_side"):
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        eligible = [
            segment for segment in tuple(projected.projection.segments_2d or ())
            if min(float(segment[0][0]), float(segment[1][0])) < core_start - 1e-6
        ]
        rows = []
        for a, b in eligible:
            rows.append((
                round(min(float(a[0]), float(b[0])), 6),
                round(max(float(a[0]), float(b[0])), 6),
                round(min(float(a[1]), float(b[1])), 6),
                round(max(float(a[1]), float(b[1])), 6),
            ))
        evidence[source_key] = rows
    print("ISSUE63_RELIEF_BACKPROJECTION_SEGMENTS=", evidence)

    # Keep this diagnostic red-capable: each physical source must contribute
    # actual fold-band geometry, not just a scalar depth.
    assert evidence["box_body:left_side"]
    assert evidence["box_body:right_side"]

def test_issue63_divider_left_right_physical_sides_cut_opposite_span_ends():
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    solved = next(p for p in solved_parts if p.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    by_source = dict(dict(relief["evidence"])["projection_by_source"])
    left_edge = str(by_source["box_body:left_side"]["edge"])
    right_edge = str(by_source["box_body:right_side"]["edge"])
    exterior = [(float(x), float(y)) for x, y in solved.render_data.material.exterior.coords]
    print("ISSUE63_RELIEF_EVIDENCE=", {
        "left": by_source["box_body:left_side"],
        "right": by_source["box_body:right_side"],
        "cut_depths": relief["cut_depths"],
        "material_bounds": tuple(map(float, solved.render_data.material.bounds)),
        "exterior": exterior,
        "diagnostic": {
            "status": diagnostics[0].candidate_status,
            "illegal": diagnostics[0].illegal_penetration,
        },
    })
    assert left_edge in {"MIN_Y", "MAX_Y"}
    assert right_edge in {"MIN_Y", "MAX_Y"}
    assert left_edge != right_edge, (
        "left/right physical BoxBody pieces must own opposite Divider span ends",
        by_source,
    )


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_issue63_receiving_box_body_physical_pieces_are_real_3d_input_contexts():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        root.update_idletasks(); root.update()

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        expected = (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        available = tuple(designer.designer_workspace.available_parts)
        print("ISSUE63_AVAILABLE_PARTS=", available)
        for key in expected:
            assert key in available, (
                "multipart BoxBody physical piece is visible in manufacturing but "
                "missing from the 3D workspace/operator selector",
                key, available,
            )
            designer.activate_part(key)
            root.update_idletasks(); root.update()
            assert designer.designer_workspace.active_part == key
            assert str(designer.part_var.get()) in {"左側板", "後面板", "右側板"}
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_issue63_diagnose_divider_relief_backprojection_shape():
    from ae_engine.assembly_collision import (
        project_joint_interference_to_relief_owner,
        _divider_front_fold_segments,
    )
    from tests.test_issue39_divider_relief import _divider_insert_joint

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snap["t"]
    )
    joint = _divider_insert_joint(divider.stable_id)
    core_start = float(
        dict(divider_part.render_data.metadata["physical_geometry_contract"])
        ["core_physical_segment"]["flat_band"][0]
    )

    piece_profiles = {}
    for piece in tuple(body.render_data.pieces or ()):
        piece_profiles[str(piece.role)] = [
            {
                "phase6_key": str(getattr(row, "phase6_key", "") or ""),
                "length": float(getattr(row, "length", 0.0)),
                "angle": getattr(row, "angle", None),
            }
            for row in tuple(piece.fold_profile or ())
        ]

    evidence = {}
    for source_key in ("box_body:left_side", "box_body:right_side"):
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        front = _divider_front_fold_segments(
            projected.projection, core_start=core_start
        )
        points = [
            (float(p[0]), float(p[1]))
            for seg in front
            for p in seg
        ]
        evidence[source_key] = {
            "pair_count": int(projected.projection.pair_count),
            "eligible_count": len(front),
            "x_range": (
                min(x for x, _y in points),
                max(x for x, _y in points),
            ) if points else None,
            "y_range": (
                min(y for _x, y in points),
                max(y for _x, y in points),
            ) if points else None,
            "sample_segments": [
                (
                    (round(float(a[0]), 6), round(float(a[1]), 6)),
                    (round(float(b[0]), 6), round(float(b[1]), 6)),
                )
                for a, b in front[:30]
            ],
        }

    print("ISSUE63_RELIEF_BACKPROJECTION=", {
        "core_start": core_start,
        "piece_profiles": piece_profiles,
        "projection": evidence,
    })
    assert evidence["box_body:left_side"]["eligible_count"] > 0
    assert evidence["box_body:right_side"]["eligible_count"] > 0


def test_issue63_diagnose_divider_projection_hulls():
    from shapely.geometry import MultiPoint
    from ae_engine.assembly_collision import (
        project_joint_interference_to_relief_owner,
        _divider_front_fold_segments,
    )
    from tests.test_issue39_divider_relief import _divider_insert_joint

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    joint = _divider_insert_joint(divider.stable_id)
    core_start = float(
        divider_part.render_data.metadata["physical_geometry_contract"]
        ["core_physical_segment"]["flat_band"][0]
    )
    result = {}
    for source_key in ("box_body:left_side", "box_body:right_side"):
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        front = _divider_front_fold_segments(projected.projection, core_start=core_start)
        pts = [(float(v[0]), float(v[1])) for seg in front for v in seg]
        hull = MultiPoint(pts).convex_hull
        result[source_key] = {
            "hull_area": float(hull.area),
            "hull_coords": [
                (round(float(x), 6), round(float(y), 6))
                for x, y in getattr(hull, "exterior", hull).coords
            ],
            "point_count": len(pts),
        }
    print("ISSUE63_PROJECTION_HULLS=", result)
    assert all(item["hull_area"] > 0 for item in result.values())


def test_issue63_divider_candidate_does_not_replace_uv_shape_with_depth_rectangle():
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union
    from ae_engine.assembly_collision import (
        build_divider_front_fold_relief_candidate,
        project_joint_interference_to_relief_owner,
        _divider_front_fold_segments,
    )
    from tests.test_issue39_divider_relief import _divider_insert_joint

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    joint = _divider_insert_joint(divider.stable_id)
    core_start = float(
        divider_part.render_data.metadata["physical_geometry_contract"]
        ["core_physical_segment"]["flat_band"][0]
    )
    source_keys = ("box_body:left_side", "box_body:right_side")
    candidate = build_divider_front_fold_relief_candidate(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        core_start=core_start,
        source_geometry_keys=source_keys,
        clearance=0.0,
    )
    assert candidate is not None
    material = world["flat_material_by_part"][divider.stable_id]

    hulls = []
    for source_key in source_keys:
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        front = _divider_front_fold_segments(
            projected.projection, core_start=core_start
        )
        points = [(float(p[0]), float(p[1])) for seg in front for p in seg]
        assert points
        hull = MultiPoint(points).convex_hull.intersection(material)
        assert not hull.is_empty and float(hull.area) > 0.0
        hulls.append(hull)

    collision_shape = unary_union(hulls).intersection(material)
    actual_cut = candidate.cut_polygon_2d.intersection(material)

    # Boolean robustness may add a microscopic fringe, but the manufacturing
    # cut must not throw away the UV topology and remove a full depth rectangle.
    margin = max(
        1.0e-3,
        float(collision_shape.area) * 1.0e-4,
    )
    overcut = float(actual_cut.difference(collision_shape.buffer(5.0e-4)).area)
    undercut = float(collision_shape.difference(actual_cut.buffer(5.0e-4)).area)
    print("ISSUE63_RELIEF_SHAPE_DELTA=", {
        "collision_area": float(collision_shape.area),
        "actual_cut_area": float(actual_cut.area),
        "overcut_area": overcut,
        "undercut_area": undercut,
        "margin": margin,
    })
    assert overcut <= margin, (
        "Divider relief overcuts material outside collision-derived flat-UV shape; "
        "candidate was reduced to a scalar-depth rectangle",
        overcut, margin,
    )
    assert undercut <= margin, (
        "Divider relief failed to cover collision-derived flat-UV shape",
        undercut, margin,
    )
