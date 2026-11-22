"""Render actual Engine #3317 Tail CHECK 2D/3D; no stand-in geometry.

Input is the exact VMiterTailDualVSourceCheck from one PartSpec/FinalScene.
Returns one ZIP (flat.svg, folded.obj, folded.png, diagnostics.json).
No DXF and no manufacturing gate changes.
"""
from __future__ import annotations

import io
import json
import math
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive, TextPrimitive,
)


def _finite(v):
    x = float(v)
    if not math.isfinite(x):
        raise ValueError("WHD dual V actual Engine coordinate is not finite")
    return x


def _src_point(p):
    return (_finite(p.x), _finite(p.y))


def _svg_flat(check):
    outline = tuple(_src_point(p) for p in check.corrected_outline)
    orig = tuple(_src_point(p) for p in check.original_outline)
    xmin = min(x for x, y in orig)
    xmax = max(x for x, y in orig)
    ymin = min(y for x, y in orig)
    ymax = max(y for x, y in orig)
    width, height = xmax-xmin, ymax-ymin
    if min(width, height) <= 0:
        raise ValueError("WHD source outline has nonpositive dimensions")

    def contour(points, stroke, *, dash=""):
        d = "M " + " L ".join(f"{x:.6f},{y:.6f}" for x,y in points) + " Z"
        return (f'<path d="{d}" stroke="{stroke}" stroke-width="0.8" '
                f'fill="none" {dash}/>')
    # Explicitly show the precise same-source corner material NOT folded
    # by the original finite bottom BEND. Never paint a guessed rectangle:
    # these filled paths are sourced from Engine polygons themselves.
    rows = []
    for source_region in check.out_of_bottom_span_corner_contours_xy:
        region=tuple(_src_point(p) for p in source_region)
        d="M "+" L ".join(f"{x:.6f},{y:.6f}" for x,y in region)+" Z"
        rows.append(f'<path d="{d}" fill="#f5cc72" fill-opacity="0.32" stroke="none"/>')
    rows.extend([contour(orig, "#AAAAAA", dash='stroke-dasharray="3,2"'),
                 contour(outline, "#252525")])
    for primitive in check.original_other_primitives:
        col = (
            "#275C94" if getattr(primitive, "layer", "") == "BEND"
            else "#5C8170" if getattr(primitive, "layer", "") == "CUTTING"
            else "#888888"
        )
        if isinstance(primitive, PolylinePrimitive):
            points=tuple(_src_point(p) for p in primitive.points)
            d="M "+" L ".join(f"{x:.6f},{y:.6f}" for x,y in points)
            if primitive.closed: d+=" Z"
            rows.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="0.6"/>')
        elif isinstance(primitive, CirclePrimitive):
            x,y=_src_point(primitive.center)
            rows.append(f'<circle cx="{x:.6f}" cy="{y:.6f}" r="{primitive.radius:.6f}" '
                        f'fill="none" stroke="{col}" stroke-width="0.6"/>')
        elif isinstance(primitive, LinePrimitive):
            x1,y1=_src_point(primitive.p1)
            x2,y2=_src_point(primitive.p2)
            rows.append(f'<line x1="{x1:.6f}" y1="{y1:.6f}" '
                        f'x2="{x2:.6f}" y2="{y2:.6f}" stroke="{col}" stroke-width="0.6"/>')
        elif isinstance(primitive, TextPrimitive):
            # Existing text remains at its original physical coordinates.
            x,y=_src_point(primitive.insert)
            rows.append(f'<text transform="translate({x:.6f},{y:.6f}) scale(1,-1)" '
                        f'font-size="{primitive.char_height}" fill="{col}">{escape(primitive.text)}</text>')
        else:
            raise TypeError("Unknown WHD Factory source primitive")
    (bend_start,bend_end)=check.bottom_bend_span_x_mm
    bend_y=check.left_apex.y
    # Mark the original WHD BEND with its REAL finite endpoints.
    rows.append(
        f'<line x1="{bend_start:.6f}" y1="{bend_y:.6f}" '
        f'x2="{bend_end:.6f}" y2="{bend_y:.6f}" '
        f'stroke="#0859bd" stroke-width="1.5"/>'
    )
    for pos in (bend_start,bend_end):
        rows.append(f'<circle cx="{pos:.6f}" cy="{bend_y:.6f}" r="1.8" '
                    f'fill="white" stroke="#0859bd" stroke-width="1"/>')
    def annotation(x,y,string):
        # SVG source Y is flipped only in the common transform: flip text
        # back locally so real-millimeter labels remain readable.
        rows.append(
            f'<text transform="translate({x:.6f},{y:.6f}) scale(1,-1)" '
            f'font-size="6.1" fill="#222">{escape(string)}</text>'
        )
    annotation(bend_start+4,bend_y+8,
               f"BOTTOM BEND: X={bend_start:g} to {bend_end:g} mm")
    annotation(bend_start+1,bend_y-9,"START")
    annotation(bend_end-17,bend_y-9,"END")
    annotation(bend_start-15,bend_y-22,"NO Y FOLD")
    annotation(bend_end+2,bend_y-22,"NO Y FOLD")
    # Real vertical side BEND starts at Y=49, not the nominal V apex Y=48.
    # Plot start/end guides from the authoritative FinalScene, never infer
    # from the candidate diagonal cut or from a stretched bbox.
    for anchor_x, span, sign in (
        (check.left_apex.x,check.side_bend_span_y_mm[0],1),
        (check.right_apex.x,check.side_bend_span_y_mm[1],-1),
    ):
        for edge in span:
            rows.append(f'<circle cx="{anchor_x:.6f}" cy="{edge:.6f}" '
                        f'r="1.3" fill="#177957" stroke="white" stroke-width="0.4"/>')
        if sign>0:
            annotation(anchor_x+5,span[0]+18,
                       f"SIDE BEND START Y={span[0]:g} mm")
        else:
            annotation(anchor_x-120,span[0]+18,
                       f"SIDE BEND START Y={span[0]:g} mm")
    for apex, hits in ((check.left_apex, check.left_outer_v_hits),
                       (check.right_apex, check.right_outer_v_hits)):
        x,y=_src_point(apex)
        for p in hits:
            xx,yy=_src_point(p)
            rows.append(f'<line x1="{x:.6f}" y1="{y:.6f}" x2="{xx:.6f}" '
                        f'y2="{yy:.6f}" stroke="#C4513C" stroke-width="1.1"/>')
    transform=f"translate(0,{ymin+ymax:.6f}) scale(1,-1)"
    header=(f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{xmin-16:.3f} {ymin-16:.3f} {width+32:.3f} {height+32:.3f}" '
            f'width="1000" height="{int(1000*(height+32)/(width+32))}">')
    return (header+'<rect width="100%" height="100%" fill="white"/>'
            f'<title>WHD Tail dual V CHECK: one original Factory source, mm</title>'
            f'<g transform="{transform}">{"".join(rows)}</g></svg>').encode("utf-8")


def _actual_obj(check, *, native=True):
    mesh_groups=(
        (("original_WHD_3D_finite_BEND_span", check.native_original_fold_path_mesh),)
        if native else (
            ("RBA_other_source_parts", check.remaining_flat_solid),
            ("RBA_left_physical_BEND_only", check.side_left_solid),
            ("RBA_right_physical_BEND_only", check.side_right_solid),
            ("RBA_bottom_connected_corner_transition", check.bottom_solid),
        )
    )
    buf=io.StringIO()
    buf.write("# WHD #3317 SAME Factory sheet; 2D/3D Engine source CHECK only\n")
    buf.write("# unit: mm; model status: NOT VERIFIED; not CNC\n")
    index=1
    for group,mesh in mesh_groups:
        buf.write(f"g {group}\n")
        for tri in mesh:
            for vertex in tri:
                if len(vertex)!=3:
                    raise ValueError("WHD 3D triangle is not XYZ")
                buf.write("v "+" ".join(f"{_finite(v):.6f}" for v in vertex)+"\n")
            buf.write(f"f {index} {index+1} {index+2}\n")
            index+=3
    return buf.getvalue().encode("utf-8")


def _png_actual_mesh(check):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig=Figure(figsize=(11,7),dpi=140)
    FigureCanvasAgg(fig)
    ax=fig.add_subplot(111,projection="3d")
    # Render precisely the original WHD 3D fold path. The separate
    # focused RBA mesh is evidence for T/R/BA geometry and NOT used as
    # a substitute for the canonical finite-guide fold preview.
    meshes=(check.native_original_fold_path_mesh,)
    all_points=[]
    for mesh in meshes:
        polygons=[
            tuple(tuple(_finite(q) for q in p) for p in tri)
            for tri in mesh
        ]
        if not polygons:
            raise ValueError("WHD Engine folded mesh empty")
        all_points.extend(point for tri in polygons for point in tri)
        coll=Poly3DCollection(polygons,linewidths=0.05,alpha=0.7)
        ax.add_collection3d(coll)
    x=[p[0] for p in all_points]
    y=[p[1] for p in all_points]
    z=[p[2] for p in all_points]
    ax.set_xlim(min(x),max(x))
    ax.set_ylim(min(y),max(y))
    ax.set_zlim(min(z),max(z)+1)
    ax.set_box_aspect((max(x)-min(x),max(y)-min(y),max(z)-min(z)+1),
                      zoom=0.80)
    ax.view_init(elev=28,azim=-62)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title("WHD 封尾・同源雙 V 折後模型（CHECK，尚未密合）",
                 fontproperties=None)
    buffer=io.BytesIO()
    fig.savefig(buffer,format="png",bbox_inches="tight")
    fig.clear()
    return buffer.getvalue()


def _model_report(check):
    original=check.original_other_primitives
    holes=[]
    for p in original:
        if isinstance(p,CirclePrimitive):
            holes.append({
                "center_mm":list(_src_point(p.center)),
                "radius_mm":_finite(p.radius),
                "layer":p.layer,
                "source_id":p.source_id,
            })
    corners=[]
    for row in check.corners:
        c=row.seam_continuity
        corners.append({
            "corner":row.corner,
            "status":row.model_status,
            "surface_intersection_triangle_pairs":row.model_interference_pairs,
            "surface_intersection_segments_xyz":row.model_interference_segments,
            "volume_status":row.model_volume_status,
            "native_uncut_fold_endpoint_jump_max_mm":
                row.native_uncut_fold_endpoint_jump_max_mm,
            "native_uncut_fold_endpoint_status":
                row.native_uncut_fold_endpoint_status,
            "actual_formed_seam_reach_mm":row.actual_formed_reach_mm,
            "distal_zero_r_vs_rba_shortfall_mm":row.distal_ideal_shortfall_mm,
            "interference_z_range_mm":row.interference_z_range_mm,
            "actual_formed_joint_axis_xyz":row.actual_joint_axis_xyz,
            "topology_contact_failure":row.topology_contact_failure,
            "topological_clearance_lower_bound_mm":row.topological_clearance_lower_bound_mm,
            "source_geometric_gap_floor_at_straight_start_mm":
                row.contact_gap_floor_at_straight_start_mm,
            "source_geometric_gap_floor_at_straight_end_mm":
                row.contact_gap_floor_at_straight_end_mm,
            "any_90deg_asymmetry_best_case_far_gap_floor_mm":
                row.asymmetry_best_case_far_gap_floor_mm,
            "true_cut_face_gap_by_z_mm": [
                {"z":x, "status":status, "gap":gap}
                for x,status,gap in row.sampled_seam_gap_stations_mm
            ],
            "max_sampled_cut_face_gap_mm":(
                c.max_sampled_cut_face_gap_mm if c is not None else None
            ),
            "full_gap_upper_bound_mm":(
                c.max_gap_upper_bound_mm if c is not None else None
            ),
            "full_gap_lower_bound_mm":(
                c.max_gap_lower_bound_mm if c is not None else None
            ),
            "non_measured_intervals_mm":(
                [{"start":i.start_mm,"end":i.end_mm,
                  "status":i.midpoint_section.status}
                 for i in c.intervals if i.midpoint_section.status!="MEASURED"]
                if c is not None else []
            ),
            "unresolved_vertex_events":(
                c.numerically_unresolved_vertex_event_count if c else None
            ),
            "failure_side":row.side_cut_failure,
            "failure_bottom":row.bottom_cut_failure,
            "seam_failure":row.seam_failure,
        })
    return {
        "geometry_source":"WHD current real EndCap PartSpec/FinalScene/Factory",
        "units":"mm",
        "status":"MODEL_NOT_VERIFIED" if any(
            row.model_status!="MODEL_PASS" for row in check.corners
        ) else "MODEL_PASS",
        "scope":"Tail lower left/right; other source components unchanged",
        "original_outline_xy":[list(_src_point(p)) for p in check.original_outline],
        "corrected_outline_xy":[list(_src_point(p)) for p in check.corrected_outline],
        "v_openings": {
            "left":[list(_src_point(p)) for p in check.left_outer_v_hits],
            "right":[list(_src_point(p)) for p in check.right_outer_v_hits],
        },
        "fold_intersections":{
            "left":list(_src_point(check.left_apex)),
            "right":list(_src_point(check.right_apex)),
        },
        "physical_flange_mm":{
            "left":check.side_flange_left_mm,
            "right":check.side_flange_right_mm,
            "bottom":check.bottom_flange_mm,
        },
        "source_holes_unchanged":holes,
        "source_other_primitive_count":len(original),
        "original_WHD_3D_finite_BEND_span_triangle_count":
            len(check.native_original_fold_path_mesh),
        "physical_bottom_BEND_span_x_mm":check.bottom_bend_span_x_mm,
        "physical_left_and_right_side_BEND_span_y_mm":check.side_bend_span_y_mm,
        "retained_stock_outside_bottom_BEND_area_mm2":
            check.retained_out_of_span_corner_area_mm2,
        "out_of_bottom_BEND_original_stock_polygons": [
            [list(_src_point(p)) for p in poly]
            for poly in check.out_of_bottom_span_corner_contours_xy
        ],
        "restored_corner_stock_ownership_mm2": [
            {"corner":corner,"added_total":total,"side_fold":side,
             "bottom_fold":bottom,"not_in_either_lower_fold":remainder}
            for corner,total,side,bottom,remainder
            in check.restored_stock_ownership_mm2
        ],
        "original_WHD_finite_BEND_endpoint_jump_by_corner_mm": [
            {"corner":corner,"samples":[{"source_y":y,"3d_jump":gap}
                for y,gap in samples]}
            for corner,samples in
            check.native_bottom_span_boundary_jump_samples_mm
        ],
        "corners":corners,
        "formal_dxf_export":"NOT_ALLOWED",
    }


def build_tail_dual_v_source_preview_zip(check) -> bytes:
    """Return actual-model evidence; never produces manufacturing files."""
    flat=_svg_flat(check)
    obj=_actual_obj(check,native=True)
    physical_obj=_actual_obj(check,native=False)
    png=_png_actual_mesh(check)
    report=json.dumps(_model_report(check),ensure_ascii=False,indent=2,
                      sort_keys=True).encode("utf-8")
    stream=io.BytesIO()
    with ZipFile(stream,"w",compression=ZIP_DEFLATED,compresslevel=9) as out:
        out.writestr("WHD_tail_dual_V_same_source_2D.svg",flat)
        out.writestr("WHD_tail_dual_V_actual_folded_model.obj",obj)
        out.writestr("WHD_tail_dual_V_RBA_focused_fold_check.obj",physical_obj)
        out.writestr("WHD_tail_dual_V_folded_preview.png",png)
        out.writestr("WHD_tail_dual_V_model_diagnosis.json",report)
    return stream.getvalue()
