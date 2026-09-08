# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from math import copysign

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine.contracts import ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import build_box_body_divider_render_data
from ae_engine.sheetmetal_drawing import CirclePrimitive
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part
from tests.test_issue40_divider_6p4_shared_datum import _solved
import fold_designer_bridge as bridge



def _issue63_divider_middle_segment(material):
    minx, _miny, _maxx, _maxy = map(float, material.bounds)
    coords = list(material.exterior.coords)
    candidates = []
    for a, b in zip(coords, coords[1:]):
        if abs(float(a[0]) - minx) <= 1e-5 and abs(float(b[0]) - minx) <= 1e-5:
            length = abs(float(b[1]) - float(a[1]))
            if length > 1e-6:
                candidates.append((length, a, b))
    assert candidates
    length, a, b = max(candidates, key=lambda row: row[0])
    y0, y1 = sorted((float(a[1]), float(b[1])))
    return {
        "length": float(length),
        "center": (minx, (y0 + y1) / 2.0),
        "tangent": (0.0, 1.0),
        "inward": (1.0, 0.0),
    }


def _issue63_resolved_endcap_middle_rule(render):
    holes = [
        p for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
        and abs(float(p.radius) - 3.2) <= 1e-6
    ]
    assert len(holes) >= 2

    # Use the actual resolved Ø6.4 pair to identify the hole-bearing middle edge.
    pairs = []
    for i, a in enumerate(holes):
        for b in holes[i + 1:]:
            dx = float(b.center.x) - float(a.center.x)
            dy = float(b.center.y) - float(a.center.y)
            length = (dx * dx + dy * dy) ** 0.5
            if length > 1e-9:
                pairs.append((length, a, b))
    assert pairs
    _pair_len, h0, h1 = max(pairs, key=lambda row: row[0])
    hv = (
        float(h1.center.x) - float(h0.center.x),
        float(h1.center.y) - float(h0.center.y),
    )
    hlen = (hv[0] * hv[0] + hv[1] * hv[1]) ** 0.5
    hu = (hv[0] / hlen, hv[1] / hlen)
    hc = [
        (float(h0.center.x), float(h0.center.y), h0),
        (float(h1.center.x), float(h1.center.y), h1),
    ]

    pts = list(render.material.exterior.coords)
    candidates = []
    for a, b in zip(pts, pts[1:]):
        vx, vy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
        length = (vx * vx + vy * vy) ** 0.5
        if length <= 1e-9:
            continue
        tu = (vx / length, vy / length)
        if abs(tu[0] * hu[0] + tu[1] * hu[1]) < 0.999:
            continue
        center = (
            (float(a[0]) + float(b[0])) / 2.0,
            (float(a[1]) + float(b[1])) / 2.0,
        )
        projections = [
            (h[0] - center[0]) * tu[0] + (h[1] - center[1]) * tu[1]
            for h in hc
        ]
        if max(abs(v) for v in projections) > length / 2.0 + 1e-6:
            continue
        distances = [
            abs((h[0] - center[0]) * (-tu[1]) + (h[1] - center[1]) * tu[0])
            for h in hc
        ]
        candidates.append((sum(distances) / len(distances), center, tu, length))

    assert candidates
    _dist, center, tu, length = min(candidates, key=lambda row: row[0])
    if tu[0] < -1e-9 or (abs(tu[0]) <= 1e-9 and tu[1] < 0):
        tu = (-tu[0], -tu[1])

    centroid = (float(render.material.centroid.x), float(render.material.centroid.y))
    n1 = (-tu[1], tu[0])
    if (centroid[0] - center[0]) * n1[0] + (centroid[1] - center[1]) * n1[1] < 0:
        inward = (-n1[0], -n1[1])
    else:
        inward = n1

    ranked = []
    for x, y, primitive in hc:
        axial = (x - center[0]) * tu[0] + (y - center[1]) * tu[1]
        inward_offset = (x - center[0]) * inward[0] + (y - center[1]) * inward[1]
        ranked.append((axial, inward_offset, primitive))
    axial, inward_offset, primitive = max(ranked, key=lambda row: row[0])
    return {
        "length": float(length),
        "center": center,
        "tangent": tu,
        "inward": inward,
        "anchor_axial": float(axial),
        "anchor_edge_distance": float(inward_offset),
        "anchor": (float(primitive.center.x), float(primitive.center.y)),
    }

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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_issue63_physical_piece_fold_edit_survives_save_switch_and_resync():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        left_key = "box_body:left_side"
        right_key = "box_body:right_side"
        designer.activate_part(left_key)
        root.update_idletasks(); root.update()

        active = tuple(designer.state.profiles["X"] or ())
        rear_index = next(
            i for i, row in enumerate(active)
            if row.get("phase6_key") == "side_rear_bend_left"
        )
        ctrl = designer.bend_ui.controls[rear_index]["len"]
        old_ui = int(float(ctrl.get()))
        edited_ui = old_ui + 1
        ctrl.set(str(edited_ui))

        designer._save_current_part()
        root.update_idletasks(); root.update()
        designer.activate_part(right_key)
        root.update_idletasks(); root.update()
        designer.activate_part(left_key)
        root.update_idletasks(); root.update()

        after = tuple(designer.state.profiles["X"] or ())
        rear_index_after = next(
            i for i, row in enumerate(after)
            if row.get("phase6_key") == "side_rear_bend_left"
        )
        actual_ui = int(float(designer.bend_ui.controls[rear_index_after]["len"].get()))
        print("ISSUE63_PIECE_EDIT_ROUNDTRIP=", {
            "before_ui": old_ui,
            "edited_ui": edited_ui,
            "after_ui": actual_ui,
            "structure": designer.designer_workspace.box_body_structure_state(),
        })
        assert actual_ui == edited_ui, (
            "left-side Fold editor input was lost after save/switch/resync"
        )
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()

def test_issue63_divider_baseline_holes_preserve_physical_edge_offsets_not_centered_envelope():

    snap = _snapshot()
    divider = derive_box_body_dividers(
        tuple((float(w), tuple(float(h) for h in hs)) for w, hs in snap["door_layout_columns"]),
        depth=snap["d"], thickness=snap["t"],
        layout_scope=snap["door_layout_scope"], handle_edges={},
        model_name="受電箱", frame_width=snap["fw"],
    )[0]
    render = build_box_body_divider_render_data(
        divider, context=ManufacturingContext(resource_root=Path.cwd())
    )

    doc = ezdxf.readfile(Path("基準檔") / "金庫型" / "中隔.dxf")
    msp = doc.modelspace()
    from ezdxf import bbox as ezdxf_bbox
    ext = ezdxf_bbox.extents(msp)
    source_min_y = float(ext.extmin.y)
    source_max_x = float(ext.extmax.x)

    source = list(msp.query("CIRCLE"))
    mapped = [
        p for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
        and str(getattr(p, "source_type", "")) == "baseline_divider_hole"
    ]
    assert len(mapped) == len(source) == 6

    actual = []
    expected = []
    for entity, primitive in zip(source, mapped):
        cx = float(entity.dxf.center.x)
        cy = float(entity.dxf.center.y)
        exp = (
            cy - source_min_y,
            source_max_x - cx,
        )
        got = (float(primitive.center.x), float(primitive.center.y))
        expected.append(exp)
        actual.append(got)
        assert got == pytest.approx(exp), (
            "baseline fixed holes must retain their physical edge offsets after "
            "clockwise rotation; centering the old 596-mm envelope inside a wider "
            "Divider span moves every fixed hole",
            {"source": (cx, cy), "expected": exp, "actual": got},
        )
    print("ISSUE63_HOLE_EDGE_DATUM=", {"expected": expected, "actual": actual})



@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_issue63_resolved_divider_matches_resolved_head_tail_middle_and_hole_edge_parity():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        divider_parts = [
            part for part in tuple(resolved.parts or ())
            if str(part.part_key).startswith("box_body:divider:")
        ]
        assert len(divider_parts) == 1
        divider_render = divider_parts[0].render_data
        divider_middle = _issue63_divider_middle_segment(divider_render.material)
        divider_holes = [
            p for p in divider_render.scene.primitives
            if isinstance(p, CirclePrimitive)
            and abs(float(p.radius) - 3.2) <= 1e-6
        ]
        assert len(divider_holes) == 3
        divider_anchor = min(divider_holes, key=lambda item: float(item.center.x))
        divider_distance = (
            (float(divider_anchor.center.x) - divider_middle["center"][0])
            * divider_middle["inward"][0]
            + (float(divider_anchor.center.y) - divider_middle["center"][1])
            * divider_middle["inward"][1]
        )

        relief_meta = dict(divider_render.metadata["divider_assembly_relief"])
        relief_evidence = dict(relief_meta.get("evidence") or {})
        boolean_margin = float(relief_evidence.get("boolean_margin", 0.0))
        sheet_thickness = float(relief_evidence.get("sheet_thickness", 0.0))
        expected_t = float(designer._phase6_input_snapshot["t"])
        assert sheet_thickness == pytest.approx(expected_t, abs=1e-9)
        for source in ("box_body:left_side", "box_body:right_side"):
            source_evidence = dict(
                dict(relief_evidence["projection_by_source"])[source]
            )
            assert float(source_evidence["solid_half_thickness"]) == pytest.approx(
                expected_t / 2.0, abs=1e-9
            )

        # Test-only numerical tolerance: the production boolean fringe is
        # intentionally recorded by the solver. It may shorten the measured
        # retained line by one fringe at each end, but it is never fed back
        # into production geometry.
        parity_tolerance = max(1.0e-6, 2.0 * boolean_margin + 1.0e-6)
        evidence = {
            "divider_middle_length": float(divider_middle["length"]),
            "divider_anchor_edge_distance": float(divider_distance),
            "boolean_margin": boolean_margin,
            "parity_tolerance": parity_tolerance,
            "divider_bounds": tuple(map(float, divider_render.material.bounds)),
            "divider_exterior": [
                (float(x), float(y)) for x, y in divider_render.material.exterior.coords
            ],
            "endcaps": {},
        }
        for key in ("head", "tail"):
            resolved_part = resolved.part(key)
            endcap_render = resolved_part.render_data
            endcap = _issue63_resolved_endcap_middle_rule(endcap_render)
            evidence["endcaps"][key] = {
                **endcap,
                "bounds": tuple(map(float, endcap_render.material.bounds)),
                "x_profile": tuple(dict(row) for row in tuple(resolved_part.x_profile or ())),
                "y_profile": tuple(dict(row) for row in tuple(resolved_part.y_profile or ())),
                "exterior": [
                    (float(x), float(y)) for x, y in endcap_render.material.exterior.coords
                ],
                "metadata_keys": tuple(sorted(dict(endcap_render.metadata or {}))),
            }
        print("ISSUE63_RESOLVED_ENDCAP_AUTHORITY=", evidence)

        for key in ("head", "tail"):
            endcap = evidence["endcaps"][key]
            assert float(divider_middle["length"]) == pytest.approx(
                float(endcap["length"]), abs=parity_tolerance
            ), (
                "同一組 W/D/T/FW 下，中隔截角後中間直線段必須等同 resolved 封頭/尾",
                key,
                divider_middle,
                endcap,
            )
            assert float(divider_distance) == pytest.approx(
                float(endcap["anchor_edge_distance"]), abs=1e-6
            ), (
                "同一組 W/D/T/FW 下，中隔 shared Ø6.4 到截角邊距離必須等同 resolved 封頭/尾",
                key,
                divider_distance,
                endcap,
            )
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
    print("ISSUE63_RELIEF_DIAGNOSTIC=", {
        "status": diagnostics[0].candidate_status,
        "illegal": diagnostics[0].illegal_penetration,
        "pre": diagnostics[0].pre_pair_count,
        "post": diagnostics[0].post_pair_count,
        "evidence": diagnostics[0].evidence,
        "metadata_keys": tuple(sorted(dict(solved.render_data.metadata or {}))),
    })
    assert diagnostics[0].illegal_penetration is False, diagnostics[0].evidence
    assert "divider_assembly_relief" in solved.render_data.metadata
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


def test_issue63_divider_candidate_preserves_uv_shape_and_sweeps_skin_to_solid_boundary():
    from shapely.affinity import translate
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
        sheet_thickness=float(divider.thickness),
    )
    assert candidate is not None
    material = world["flat_material_by_part"][divider.stable_id]

    hulls = []
    solid_hulls = []
    minx, miny, maxx, maxy = map(float, material.bounds)
    half_t = float(divider.thickness) / 2.0
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

        points2 = [point for segment in front for point in segment]
        low_depth = max(0.0, max(float(p[1]) for p in points2) - miny)
        high_depth = max(0.0, maxy - min(float(p[1]) for p in points2))
        yoff = half_t if low_depth <= high_depth else -half_t
        # Independent physical-solid expectation: the collision hull is a skin
        # intersection. Sweep that convex UV footprint by half the sheet
        # thickness toward the material interior. No EndCap validation value is
        # used here.
        solid_hull = unary_union([
            hull,
            translate(hull, yoff=yoff),
        ]).convex_hull.intersection(material)
        solid_hulls.append(solid_hull)

    collision_shape = unary_union(hulls).intersection(material)
    expected_solid_shape = unary_union(solid_hulls).intersection(material)
    actual_cut = candidate.cut_polygon_2d.intersection(material)

    # Boolean robustness may add a microscopic fringe, but the manufacturing
    # cut must preserve the UV topology while converting skin crossings to the
    # physical solid footprint. It must not reduce either source to a full
    # scalar-depth rectangle.
    margin = max(
        1.0e-3,
        float(collision_shape.area) * 1.0e-4,
    )
    overcut = float(actual_cut.difference(expected_solid_shape.buffer(5.0e-4)).area)
    undercut = float(expected_solid_shape.difference(actual_cut.buffer(5.0e-4)).area)
    print("ISSUE63_RELIEF_SHAPE_DELTA=", {
        "skin_collision_area": float(collision_shape.area),
        "expected_solid_area": float(expected_solid_shape.area),
        "actual_cut_area": float(actual_cut.area),
        "half_thickness": half_t,
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
        "Divider relief failed to cover the thickness-derived physical solid footprint",
        undercut, margin,
    )
