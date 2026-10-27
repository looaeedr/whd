# -*- coding: utf-8 -*-
"""WHD source-backed RECEIVING contact MARKING capture: one and two NFB tiers.

Capture the canonical 2D mother-sheet MARKING plus 3D world contact lines
for EAR, INNER-DOOR FRAME and DIVIDER. These are headless rendered evidence
from product solvers, *not* Windows Tk screenshots or welding/NC approval.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ae_engine.manufacturing_scene_access import owner_render_data
from ae_engine.receiving_joint_marking import resolve_receiving_joint_markings
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive,
)
from gui_modules.application.receiving_ear_side_2d import (
    project_receiving_ear_side_piece_2d_preview,
)
from phase6_final_scene_contracts import (
    AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
)
from phase6_final_scene_projection import _phase6_contract_profile_rows
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import (
    _source, _two_tier,
)
from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts


DIMENSIONS = (800., 1600., 350.)
OWNERS = ("box_body:left_side", "box_body:right_side", "head")
COLOR_JOINT = "#fb923c"     # Inner-door frame and divider true physical mating
COLOR_EAR = "#facc15"       # T2/BEND23 fixed-plate physical weld contact


def _signature(p1, p2):
    return tuple(sorted((
        tuple(round(float(v), 6) for v in p1),
        tuple(round(float(v), 6) for v in p2),
    )))


def _prepared(factory):
    snapshot, source = _actual(factory)
    resolution = resolve_receiving_joint_markings(
        snapshot, source, dimensions=DIMENSIONS, sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    emitted = tuple(row for row in resolution.results if row.status == "EMITTED")
    if len(emitted) != 7 or len(resolution.results) != 7:
        raise ValueError(
            "FULL_MARKING_FRAME_DIVIDER_INCOMPLETE:"
            + repr([(r.locator_part_id, r.attached_part_id,
                     r.status, r.diagnostic_code) for r in resolution.results])
        )
    pairs = {(r.locator_part_id, r.attached_part_id) for r in emitted}
    expected = {
        ("box_body:left_side", "inner_door:upper:left_frame"),
        ("box_body:right_side", "inner_door:upper:right_frame"),
        ("head", "inner_door:upper:top_frame"),
        ("box_body:left_side", next(
            r.attached_part_id for r in emitted
            if r.locator_part_id == "box_body:left_side"
            and r.attached_part_id.startswith("box_body:divider:")
        )),
        ("box_body:right_side", next(
            r.attached_part_id for r in emitted
            if r.locator_part_id == "box_body:right_side"
            and r.attached_part_id.startswith("box_body:divider:")
        )),
    }
    if not expected.issubset(pairs):
        raise ValueError("FULL_MARKING_FRAME_OR_DIVIDER_SIDE_MISSING")
    return snapshot, resolution.geometry, emitted


def _draw_sheet(material, scene, metadata, *, title, target):
    fig = Figure(figsize=(10.7, 9.4), dpi=145)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    polygons = tuple(getattr(material, "geoms", (material,)))
    for poly in polygons:
        if poly.geom_type != "Polygon":
            continue
        x, y = poly.exterior.xy
        ax.fill(x, y, facecolor="#f1f5f9", alpha=0.55)
        ax.plot(x, y, color="#334155", linewidth=1.3)
        for ring in poly.interiors:
            xx, yy = ring.xy
            ax.plot(xx, yy, color="#334155", linewidth=0.85)

    joint_signatures = {
        _signature(row["p1"], row["p2"])
        for row in tuple((metadata or {}).get("joint_markings") or ())
        if row.get("source") == "JOINT_PLACEMENT_MARKING"
    }
    counts = {"joint": 0, "ear": 0, "other": 0}
    for item in scene.primitives:
        layer = str(getattr(item, "layer", "")).upper()
        if isinstance(item, LinePrimitive):
            p1 = (item.p1.x, item.p1.y)
            p2 = (item.p2.x, item.p2.y)
            if layer == "MARKING":
                if _signature(p1, p2) in joint_signatures:
                    color = COLOR_JOINT
                    counts["joint"] += 1
                else:
                    color = COLOR_EAR
                    counts["ear"] += 1
                ax.plot((p1[0], p2[0]), (p1[1], p2[1]),
                        color=color, linewidth=3.2, zorder=15)
            elif layer == "BEND":
                ax.plot((p1[0], p2[0]), (p1[1], p2[1]),
                        color="#0ea5e9", linewidth=1.1, linestyle="--")
        elif isinstance(item, PolylinePrimitive) and layer == "MARKING":
            pts = [(float(p.x), float(p.y)) for p in item.points]
            if item.closed and pts:
                pts += [pts[0]]
            if len(pts) > 1:
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        color=COLOR_EAR, linewidth=2.5)
                counts["other"] += 1
        elif isinstance(item, CirclePrimitive) and layer == "MARKING":
            from matplotlib.patches import Circle
            ax.add_patch(Circle((item.center.x, item.center.y), item.radius,
                                edgecolor=COLOR_EAR, fill=False, linewidth=2.5))
            counts["other"] += 1

    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("2D source-flat X / mm")
    ax.set_ylabel("2D source-flat Y / mm")
    ax.grid(False)
    fig.text(
        0.025, 0.012,
        "ORANGE = frame/divider real contact     YELLOW = fixed-plate upper installation line"
        "     |   WHD source render / NOT live Tk or welding approval",
        fontsize=8,
    )
    fig.savefig(target, bbox_inches="tight")
    return counts


def _save_2d(snapshot, geometry, tier_count, root):
    side_pieces = {
        p.role: p
        for p in geometry.part("box_body").render_data.pieces
    }
    detail = {}
    for side in ("left_side", "right_side"):
        original = side_pieces[side]
        display = project_receiving_ear_side_piece_2d_preview(
            snapshot, original, piece_key="box_body:" + side,
            geometry=geometry, dimensions=DIMENSIONS, sheet_thickness=2.,
        )
        md = display.render_data.metadata
        assert md["ear_side_mark_preview_count"] == tier_count * 3
        counts = _draw_sheet(
            display.render_data.material, display.render_data.scene, md,
            title=f"WHD {tier_count} NFB TIER(S) / 2D {side} / ALL CONTACT MARKING",
            target=root / f"2d_{side}.png",
        )
        if counts["joint"] != 2 or counts["ear"] < tier_count * 3:
            raise ValueError("FULL_MARKING_2D_SIDE_MISSING:" + side + ":" + repr(counts))
        detail[side] = counts

    divider_keys = tuple(
        p.part_key for p in geometry.parts
        if p.part_key.startswith("box_body:divider:")
    )
    if len(divider_keys) != 1:
        raise ValueError("FULL_MARKING_DIVIDER_OWNER_INVALID")
    for name, key, expected in (
        ("head", "head", 1),
        ("divider", divider_keys[0], 2),
    ):
        data = owner_render_data(geometry, key)
        if data is None:
            raise ValueError("FULL_MARKING_2D_OWNER_MISSING:" + key)
        counts = _draw_sheet(
            data.material, data.scene, data.metadata,
            title=f"WHD {tier_count} NFB TIER(S) / 2D {name} / FRAME CONTACT MARKING",
            target=root / f"2d_{name}.png",
        )
        if counts["joint"] != expected:
            raise ValueError("FULL_MARKING_2D_FRAME_MISSING:" + key + ":" + repr(counts))
        detail[name] = counts
    return detail


def _assembled_parts(snapshot, geometry, tier_count):
    # Use source PartRenderData, exact physical installation and true
    # per-NFB-tier blanks, never fabricate 3D blanks from a footprint.
    root = _source(snapshot)
    if tier_count == 1:
        from ae_engine.assembly_placement import resolve_assembly_placement
        place = resolve_assembly_placement(snapshot, "base_plate")
        bases = (replace(root, placement="offset", offset=tuple(place.world_offset)),)
    else:
        bases = expand_receiving_nfb_layer_parts(snapshot, (root,))
        if {p.part_key for p in bases} != {
            "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
        }:
            raise ValueError("FULL_MARKING_3D_TWO_BASES_NOT_PHYSICAL")
    originals = tuple(
        AssemblyScenePart(
            part_key=p.part_key, render_data=p.render_data,
            x_profile=tuple(_phase6_contract_profile_rows(p.x_profile)),
            y_profile=tuple(_phase6_contract_profile_rows(p.y_profile)),
            placement=p.placement, offset=p.offset,
        )
        for p in geometry.parts
    )
    return originals + tuple(bases)


def _save_3d(snapshot, geometry, tier_count, root):
    parts = _assembled_parts(snapshot, geometry, tier_count)
    view = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    view._formed_ear_display_cache = None
    view.last_formed_ear_display_blocker = None
    visible = {p.part_key for p in parts}
    formed = view._formed_ear_assembly_preview(snapshot, visible)
    if len(formed) != tier_count * 2:
        raise ValueError("FULL_MARKING_3D_EAR_SOURCE_MISSING")
    scene = AssemblySceneRenderData(
        assembly_parts=parts, visible_part_keys=tuple(sorted(visible)),
        visible_box_body_piece_keys=(
            "box_body:left_side", "box_body:right_side", "box_body:back"
        ),
        formed_fixing_plate_skins=formed, preserve_endcap_core_origin=True,
    )
    fig = Figure(figsize=(14.5, 10.5), dpi=145)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d")
    renderer = Phase6FinalSceneRenderer(type("AxisHost", (), {"ax3d": ax})())
    renderer.render(FinalSceneViewRequest(
        render_data=scene, x_profile=(), y_profile=(), part_key="assembly",
        thickness=2., finished_dimensions=DIMENSIONS, alpha_bend=0.18,
    ))
    if len(renderer.last_receiving_ear_marking_segments) != tier_count * 6:
        raise ValueError("FULL_MARKING_3D_EAR_LINES_MISSING")
    if len(renderer.last_formed_ear_display_ids) != tier_count * 2:
        raise ValueError("FULL_MARKING_3D_EARS_INVISIBLE")
    joint_segments = sum(
        len(tuple((p.render_data.metadata or {}).get("joint_markings") or ()))
        for p in parts if not p.part_key == "box_body"
    ) + sum(
        len(tuple((p.render_data.metadata or {}).get("joint_markings") or ()))
        for p in geometry.part("box_body").render_data.pieces
    )
    if joint_segments != 7:
        raise ValueError("FULL_MARKING_3D_FRAME_DIVIDER_MISSING:" + str(joint_segments))
    # The native UI displays Chinese operator text; CI's minimal Linux fonts
    # render it as square glyphs. Strip only those 2D annotations from this
    # evidence PNG, not the 3D physical MARKING lines or the application UI.
    for annotation in tuple(ax.texts):
        annotation.remove()
    from matplotlib.lines import Line2D
    fig.suptitle(
        f"WHD / {tier_count} NFB TIER(S) / Full assembly 3D contact MARKING",
        fontsize=15,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=COLOR_JOINT, linewidth=3,
                   label="Inner-door frame / divider contact"),
            Line2D([0], [0], color=COLOR_EAR, linewidth=3,
                   label="Base fixing-plate weld contact"),
        ],
        loc="lower center", ncol=2, fontsize=9, frameon=False,
    )
    for azimuth, elevation, name in ((-52, 24, "isometric"), (12, 19, "inner_front"), (78, 17, "side_contact")):
        ax.view_init(elev=elevation, azim=azimuth)
        fig.savefig(root / f"3d_{name}.png", bbox_inches="tight")
    return {"joint": joint_segments, "ear": len(renderer.last_receiving_ear_marking_segments),
            "physical_ear_count": len(renderer.last_formed_ear_display_ids)}


def capture_all(output_root):
    from tests.test_receiving_two_tier_physical_base_parts import _two_tier
    results = {}
    for label, factory, tiers in (
        ("single_tier", _assembled, 1),
        ("double_tier", _two_tier, 2),
    ):
        dest = Path(output_root) / label
        dest.mkdir(parents=True, exist_ok=True)
        snapshot, geometry, _emitted = _prepared(factory)
        sheet = _save_2d(snapshot, geometry, tiers, dest)
        assembly = _save_3d(snapshot, geometry, tiers, dest)
        results[label] = {"sheets": sheet, "assembly": assembly}
        print("FULL_RECEIVING_MARKING_CAPTURE_OK", label, results[label])
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/full_receiving_marking")
    args = parser.parse_args()
    capture_all(args.output)


if __name__ == "__main__":
    main()
