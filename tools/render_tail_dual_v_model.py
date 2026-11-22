"""Render actual Engine #3317 Tail CHECK 2D/3D; no stand-in geometry.

Input is the exact VMiterTailDualVSourceCheck from one PartSpec/FinalScene.
Returns one ZIP (flat.svg, true-T section.svg, folded.obj, folded.png, diagnostics.json).
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
    # A genuinely DIFFERENT mating proposal from ORIGINAL source:
    # green area is existing bottom broad T skin's UV source, not a new
    # V/CUTTING or side fold. Orange line remains real side V cutting.
    for corner in check.corners:
        trial=corner.alternative_existing_stock_contact_trial
        for tri in trial.bottom_broad_source_triangles_xy:
            pts=tuple((_finite(x),_finite(y)) for x,y in tri)
            d="M "+" L ".join(f"{x:.6f},{y:.6f}" for x,y in pts)+" Z"
            rows.append(
                f'<path d="{d}" fill="#1a9b65" fill-opacity=".22" '
                'stroke="none"/>'
            )
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
    annotation(bend_start-9,bend_y+33,
               "GREEN: EXISTING BOTTOM T BROAD SURFACE SOURCE (NOT CUTTING)")
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
        for i,p in enumerate(hits):
            xx,yy=_src_point(p)
            # Lower true V CUTTING leg belongs to the bottom fold
            # (blue); upper leg belongs to the side fold (orange).
            col=("#175fb1" if i == 0 else "#c35920")
            rows.append(f'<line x1="{x:.6f}" y1="{y:.6f}" x2="{xx:.6f}" '
                        f'y2="{yy:.6f}" stroke="{col}" stroke-width="1.2"/>')
    # Purple points are only the inverse of a HYPOTHETICAL formed
    # R/BA plane intersection; do not add these to CUTTING. Their source
    # position and side-fold ownership come directly from the same
    # CHECK report and original FinalScene BEND spans.
    for corner in check.corners:
        for z, uv_side, uv_bottom, _s_gap, _b_gap, _guide_gap in (
            corner.inverse_straight_contact_flat_trace_mm
        ):
            if not math.isfinite(z):
                raise ValueError("WHD non-finite inverse slice")
            rows.append(
                f'<circle cx="{_finite(uv_side[0]):.6f}" '
                f'cy="{_finite(uv_side[1]):.6f}" r="1.0" '
                'fill="none" stroke="#862c99" stroke-width="0.7"/>'
            )
        sample=corner.inverse_straight_contact_flat_trace_mm[0]
        annotation(_finite(sample[1][0])+2, _finite(sample[1][1])-3,
                   "RBA inverse: NOT SIDE-FOLDED STOCK")
        # Root arcs are NOT manufacturing cut lines. The trace is
        # backprojected from the hypothetical COMMON formed RBA arc; an
        # interior crossing diagnoses an impossible simple V notch
        # before invoking any source CUTTING operation.
        side_root,bottom_root=corner.inverse_root_arc_source_traces_xy
        for trace,color in ((side_root,"#862c99"),(bottom_root,"#1e8b87")):
            line="M "+" L ".join(
                f"{_finite(x):.6f},{_finite(y):.6f}" for x,y in trace
            )
            rows.append(
                f'<path d="{line}" fill="none" stroke="{color}" '
                'stroke-width="0.8" stroke-dasharray="2,1.5"/>'
            )
        for cross_x,cross_y in corner.inverse_root_nonapex_crossings_xy:
            rows.append(
                f'<circle cx="{_finite(cross_x):.6f}" '
                f'cy="{_finite(cross_y):.6f}" r="2.0" '
                'fill="none" stroke="#cf203a" stroke-width="0.9"/>'
            )
            annotation(_finite(cross_x)+1.8,_finite(cross_y)-6,
                       "RBA root inverse CROSSES: CHECK, not CUTTING")
    transform=f"translate(0,{ymin+ymax:.6f}) scale(1,-1)"
    header=(f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{xmin-16:.3f} {ymin-16:.3f} {width+32:.3f} {height+32:.3f}" '
            f'width="1000" height="{int(1000*(height+32)/(width+32))}">')
    return (header+'<rect width="100%" height="100%" fill="white"/>'
            f'<title>WHD Tail dual V CHECK: one original Factory source, mm</title>'
            f'<g transform="{transform}">{"".join(rows)}</g></svg>').encode("utf-8")



def _true_t_cut_section_segments(faces, station_z):
    """Actual 3D T-solid tagged cut-wall triangles intersected by Z station.

    No CAD guessing: every line here comes from the genuine paired V
    CUTTING wall in the R/BA 3D solid, never a whole-flange silhouette.
    """
    segments=[]
    tol=1e-7
    for triangle in faces:
        hits=[]
        for start,end in zip(triangle,(*triangle[1:], triangle[0])):
            a,b=[_finite(v) for v in start],[_finite(v) for v in end]
            if abs(a[2]-b[2]) < tol:
                if abs(a[2]-station_z)<tol:
                    hits.extend(((a[0],a[1]),(b[0],b[1])))
                continue
            t=(station_z-a[2])/(b[2]-a[2])
            if -tol<=t<=1+tol:
                hits.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
        unique=[]
        for p in hits:
            if not any(math.dist(p,q)<tol for q in unique):
                unique.append(p)
        if len(unique)>=2:
            a,b=max(((p,q) for i,p in enumerate(unique)
                     for q in unique[i+1:]),key=lambda v:math.dist(*v))
            if math.dist(a,b)>tol:
                segments.append((a,b))
    return tuple(segments)


def _svg_true_t_sections(check):
    """Two distinct left/right cut-face cross-sections at the SAME T/R/BA z.

    The proposed 90-degree plane intersection is displayed only as a
    HYPOTHETICAL datum; 3D cut walls and nearest gap witnesses use the
    actual Engine mesh. Root collisions are separate from upper seam gap.
    """
    panels=[]
    for i,row in enumerate(check.corners):
        if not row.sampled_cut_face_nearest_xyz:
            raise ValueError("WHD dual V missing measured true-T face stations")
        station_z_source,status,gap,side_pt,bottom_pt = (
            row.sequential_final_seam_sections[0]
        )
        fraction=.25
        if status != "MEASURED" or gap is None or side_pt is None or bottom_pt is None:
            raise ValueError("WHD dual V true-T face section not measured")
        station_z=_finite(side_pt[2])
        if abs(station_z-_finite(bottom_pt[2]))>1e-6:
            raise ValueError("WHD dual V measured side/bottom not in same Z section")
        apex = check.left_apex if row.corner == "bottom_left" else check.right_apex
        orig_x,orig_y=_src_point(apex)
        x0=205+430*i
        y0=210
        scale=5.0
        def pxy(p):
            return (x0+(_finite(p[0])-orig_x)*scale,
                    y0-(_finite(p[1])-orig_y)*scale)
        def fxy(p):
            a,b=pxy(p)
            return f"{a:.4f},{b:.4f}"
        panels.append(
            f'<g font-family="sans-serif" font-size="13" fill="#292929">'
            f'<text x="{10+430*i}" y="30" font-size="18">'
            f'{escape(row.corner)}: WHOLE ONE SHEET RBA/T; '
            f'FIRST {row.first_bend_axis.upper()}</text>'
            f'<text x="{10+430*i}" y="49">Z={station_z:.3f} mm '
            f'; real cut-face gap={_finite(gap):.3f} mm</text>'
            f'<text x="{10+430*i}" y="67">Root surface intersections: '
            f'{row.model_interference_pairs} pairs (NOT proven penetration)</text>'
            f'<text x="{10+430*i}" y="84">Fixed patch straight Y floor: '
            f'{_finite(row.straight_section_y_domain_witness_mm[2]):.3f} mm'
            f' (ownership check only)</text>'
            f'<line x1="{x0-130}" y1="{y0}" '
            f'x2="{x0+130}" y2="{y0}" stroke="#b6b6b6"/>'
            f'<line x1="{x0}" y1="{y0-145}" '
            f'x2="{x0}" y2="{y0+145}" stroke="#b6b6b6"/>'
            f'<circle cx="{x0}" cy="{y0}" r="3" fill="#444"/>'
            f'<text x="{x0+6}" y="{y0+14}" font-size="11">'
            f'original BEND intersection ({orig_x:g},{orig_y:g})</text>'
            '</g>'
        )
        for faces,color in (
            (row.sequential_second_side_cut_faces,"#c35920"),
            (row.sequential_second_bottom_cut_faces,"#175fb1"),
        ):
            lines=_true_t_cut_section_segments(faces,station_z)
            if not lines:
                raise ValueError("WHD dual V actual true-T section has no cut walls")
            for a,b in lines:
                panels.append(
                    f'<path d="M {fxy(a)} L {fxy(b)}" stroke="{color}" '
                    'stroke-width="2" fill="none"/>'
                )
        panels.append(
            f'<line x1="{pxy(side_pt)[0]:.4f}" '
            f'y1="{pxy(side_pt)[1]:.4f}" '
            f'x2="{pxy(bottom_pt)[0]:.4f}" '
            f'y2="{pxy(bottom_pt)[1]:.4f}" '
            'stroke="#d00000" stroke-width="2" stroke-dasharray="5,3"/>'
        )
        for v,color in ((side_pt,"#c35920"),(bottom_pt,"#175fb1")):
            x,y=pxy(v)
            panels.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" '
                          f'r="3.5" fill="{color}"/>')
        datum=row.actual_joint_axis_xyz[0]
        x,y=pxy(datum)
        panels.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r="6" '
                      'stroke="#862c99" fill="none" stroke-dasharray="3,3"/>')
        panels.append(
            f'<text x="{10+430*i}" y="367" font-family="sans-serif" '
            'font-size="12" fill="#444">Orange: actual side upper V T-wall; '
            'blue: bottom lower V T-wall</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 860 410" width="1290" height="615">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<title>WHD Tail exact source left/right true-T cut face sections; '
        'CHECK only</title>'
        +''.join(panels)+
        '<text x="15" y="398" font-size="12" fill="#862c99">'
        'Purple circle: hypothetical 90-degree RBA plane intersection '
        '(NOT verified contact); red dashed segment: true cut-wall gap'
        '</text></svg>'
    ).encode("utf-8")




def _svg_alternative_original_surface_sections(check):
    """The NEW physical side-cut to retained-bottom T broad face on one sheet.

    Each section is sliced from the paired actual Engine 3D T-solid, not a
    CAD drawing guess, and is paired with the SAME source UV overlay.
    """
    rows=[]
    for i,corner in enumerate(check.corners):
        cand=corner.alternative_existing_stock_contact_trial
        apex=check.left_apex if corner.corner=="bottom_left" else check.right_apex
        x0=205+430*i
        y0=211
        scale=5.0
        def pxy(point):
            return (x0+(_finite(point[0])-_finite(apex.x))*scale,
                    y0-(_finite(point[1])-_finite(apex.y))*scale)
        def textxy(point):
            x,y=pxy(point)
            return f"{x:.4f},{y:.4f}"
        measured=next(
            (r for r in cand.sampled_section_z_gap_mm if r[1]=="MEASURED"),
            None
        )
        gap_msg=("No common same-Z measured section"
                 if measured is None else
                 f"Z={measured[0]:.3f} mm gap={measured[2]:.3f} mm")
        rows.append(
            f'<text x="{12+430*i}" y="27" font-family="sans-serif" '
            f'font-size="19" fill="#333">'
            f'{escape(corner.corner)}: alternative physical-face pair</text>'
            f'<text x="{12+430*i}" y="47" font-family="sans-serif" '
            f'font-size="14" fill="#333">{escape(gap_msg)}</text>'
            f'<text x="{12+430*i}" y="65" font-family="sans-serif" '
            f'font-size="12" fill="#555">Orange: original side V CUT wall; '
            f'green: retained bottom T broad outer skin</text>'
            f'<line x1="{x0-135}" y1="{y0}" '
            f'x2="{x0+130}" y2="{y0}" stroke="#bbb"/>'
            f'<line x1="{x0}" y1="{y0-130}" '
            f'x2="{x0}" y2="{y0+130}" stroke="#bbb"/>'
            f'<circle cx="{x0}" cy="{y0}" r="3" fill="#333"/>'
        )
        if measured is None:
            continue
        z,_,gap,side_pt,bottom_pt,_shortcut=measured
        for faces,color in (
            (cand.side_true_t_faces,"#d16b23"),
            (cand.bottom_true_t_broad_faces,"#16885b"),
        ):
            lines=_true_t_cut_section_segments(faces,z)
            for a,b in lines:
                rows.append(
                    f'<path d="M {textxy(a)} L {textxy(b)}" '
                    f'stroke="{color}" stroke-width="2" fill="none"/>'
                )
        if side_pt is not None and bottom_pt is not None:
            ax,ay=pxy(side_pt)
            bx,by=pxy(bottom_pt)
            rows.append(
                f'<path d="M {ax:.4f},{ay:.4f} L {bx:.4f},{by:.4f}" '
                'stroke="#bb1535" stroke-width="2.2" '
                'stroke-dasharray="5,3" fill="none"/>'
            )
        rows.append(
            f'<text x="{12+430*i}" y="373" font-family="sans-serif" '
            f'font-size="12" fill="#ad2539">CHECK only: not a new V CUTTING '
            f'or machining acceptance</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 860 410" width="1290" height="615">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<title>WHD same-sheet original-side-V-wall to retained-bottom-outer-T '
        'alternative source physical section CHECK</title>'
        +''.join(rows)+'</svg>'
    ).encode("utf-8")


def _svg_alternative_original_overlay_and_section(check):
    """Annotated original Factory + current V + NOT CUTTING candidate overlay."""
    src=_svg_flat(check).decode("utf-8")
    section=_svg_alternative_original_surface_sections(check).decode("utf-8")
    def inside(document):
        if not document.startswith("<svg ") or not document.endswith("</svg>"):
            raise ValueError("WHD alternate CHECK requires source SVG")
        return document.split(">",1)[1].rsplit("</svg>",1)[0]
    orig=tuple(_src_point(p) for p in check.original_outline)
    xmin=min(x for x,y in orig)
    ymin=min(y for x,y in orig)
    xmax=max(x for x,y in orig)
    ymax=max(y for x,y in orig)
    vbox=f"{xmin-16:.3f} {ymin-16:.3f} {xmax-xmin+32:.3f} {ymax-ymin+32:.3f}"
    order=", ".join(
        f"{name} FIRST {axis.upper()}"
        for name,axis in check.operator_first_bend_axes
    )
    notes=[
        "GREY: Factory original CUTTING; BLACK: current nominated V; "
        "BLUE: actual finite BEND; GREEN: EXISTING bottom source patch.",
        "ALTERNATIVE pair = real side upper V CUT WALL (orange) "
        "versus existing bottom outer T BROAD FACE (green).",
        "The green area is NOT assigned to the side fold, "
        "and the proposal is NOT another approved V CUTTING outline.",
        "No new stock, source point, tip, BEND, hole, 15/15/48, "
        "kerf, clearance or manufacturing tolerance has been added.",
        "Stage order only changes intermediate views: original UV is "
        "exclusive to X or Y; final 3D remains same for both orders.",
        "Seam / actual volume penetration / root process "
        "are SEPARATE gates; see one-run JSON.",
    ]
    out=[
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1910 860" width="1910" height="860">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<title>WHD #3317 Factory original-current V vs source-proven '
        'ALTERNATIVE real mating surfaces; CHECK only</title>'
        '<text x="24" y="34" font-family="sans-serif" font-size="21" '
        'fill="#282828">#3317: source-backed alternative surface '
        'pair - candidate CHECK, NOT a new V</text>'
        f'<text x="26" y="57" font-family="sans-serif" font-size="15" '
        f'fill="#555">{escape(order)}</text>'
        '<text x="23" y="99" font-family="sans-serif" font-size="19" '
        'fill="#244b5d">Original Factory UV + current V + existing bottom skin</text>'
        '<text x="956" y="99" font-family="sans-serif" font-size="19" '
        'fill="#244b5d">Actual final T/R/BA face pair - both corners</text>'
        f'<svg x="18" y="115" width="905" height="685" '
        f'viewBox="{vbox}">{inside(src)}</svg>'
        '<svg x="943" y="119" width="930" height="439" '
        'viewBox="0 0 860 410">'
        +inside(section)+'</svg>'
        '<line x1="960" y1="572" x2="1880" y2="572" '
        'stroke="#bbb" stroke-width="1"/>'
    ]
    for i,line in enumerate(notes):
        out.append(
            f'<text x="964" y="{594+i*39}" '
            f'font-family="sans-serif" font-size="12.5" '
            f'fill="#333">{escape(line)}</text>'
        )
    out.append("</svg>")
    return "".join(out).encode("utf-8")


def _svg_same_source_2d_and_true_t_sections(check):
    """One labeled view, derived solely from the *same run's* two Engine SVGs.

    Nested SVG viewports retain exact millimeter source geometry and real
    physical T section coordinates. No unverified V is drawn as CUTTING.
    """
    flat=_svg_flat(check).decode("utf-8")
    sections=_svg_true_t_sections(check).decode("utf-8")
    def content(svg):
        if not svg.startswith("<svg ") or not svg.endswith("</svg>"):
            raise ValueError("WHD composite source SVG invalid")
        return svg.split(">",1)[1].rsplit("</svg>",1)[0]
    orig=tuple(_src_point(p) for p in check.original_outline)
    xmin=min(p[0] for p in orig)
    ymin=min(p[1] for p in orig)
    xmax=max(p[0] for p in orig)
    ymax=max(p[1] for p in orig)
    view=f"{xmin-16:.3f} {ymin-16:.3f} {xmax-xmin+32:.3f} {ymax-ymin+32:.3f}"
    orders=" / ".join(
        f"{corner}: {axis.upper()} FIRST"
        for corner,axis in check.operator_first_bend_axes
    )
    # All numerals below are read from the physical R/BA / exact source
    # model, not guessed geometry or a CAM/shop acceptance limit.
    left=check.corners[0].straight_section_y_domain_witness_mm
    gap=left[2]
    if gap<=0:
        raise ValueError("WHD Tail source obstruction drawing requires positive Y gap")
    notes=(
        f"Side-lip source begins Y={left[0]:.3f} mm; bottom straight "
        f"T-outer ends Y={left[1]:.3f} mm: Y gap floor {gap:.3f} mm.",
        f"Hypothetical seam Y={left[3]:.3f} mm is outside side-fold ownership; "
        "DO NOT transfer bottom-lip stock to side without physical fold proof.",
        "Change candidate: verify tip/crease-end material ownership and ordered "
        "R/BA deformation, OR a different genuinely mating seam. "
        "Keep original 15/15/48, side openings, apexes, holes, BEND.",
        "Root R/BA inverse dashed curves intersect inside original mother stock;",
        "a simple fixed-apex source notch cannot follow both. Check tip/relief",
        "and real first-fold sequence before choosing changed cuts; no DXF.",
        "Four root triangle pairs share a line: NOT proven penetration.",
    )
    header=(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1930 890" width="1930" height="890">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<title>WHD #3317 one Factory sheet: original flat + '
        'measured true-T cut sections; CHECK ONLY</title>'
        '<text x="26" y="35" font-family="sans-serif" font-size="24" '
        'fill="#242424">WHD 封尾 — 同源展開 / 左右實際 V 切面 (CHECK)</text>'
        f'<text x="28" y="62" font-family="sans-serif" font-size="16" '
        f'fill="#434343">{escape(orders)}</text>'
        '<text x="30" y="100" font-family="sans-serif" font-size="20" '
        'fill="#29384d">2D Factory blank + real BEND span (mm)</text>'
        '<text x="995" y="100" font-family="sans-serif" font-size="20" '
        'fill="#29384d">Folded R/BA/T true cut-face sections</text>'
    )
    flat_view=(
        f'<svg x="22" y="112" width="905" height="720" '
        f'viewBox="{view}">{content(flat)}</svg>'
    )
    section_view=(
        '<svg x="970" y="130" width="925" height="460" '
        'viewBox="0 0 860 410">'
        f'{content(sections)}</svg>'
    )
    note_view=['<line x1="970" y1="613" x2="1885" y2="613" '
               'stroke="#b0b0b0" stroke-width="1"/>']
    for i,line in enumerate(notes):
        # Keep six source-grounded lines within the section panel.
        text_line=escape(line)
        note_view.append(
            f'<text x="980" y="{645+i*32}" '
            f'font-family="sans-serif" font-size="14" fill="#333">'
            f'{text_line}</text>'
        )
    return (header+flat_view+section_view+"".join(note_view)+"</svg>").encode("utf-8")



def _one_source_mesh_obj(mesh, *, label):
    """One stage, all mesh vertices from ONE triangulated Factory sheet."""
    out=io.StringIO()
    out.write("# WHD same sheet, finite R/BA/T two-stage CHECK, not CNC\n")
    out.write(f"g {label}\n")
    index=1
    for tri in mesh:
        if len(tri)!=3:
            raise ValueError("WHD same source folded triangle malformed")
        for p in tri:
            out.write("v "+" ".join(f"{_finite(v):.6f}" for v in p)+"\n")
        out.write(f"f {index} {index+1} {index+2}\n")
        index+=3
    return out.getvalue().encode("utf-8")


def _svg_first_then_second_v_tracks(check):
    """Actual same UV points in flat, first, final 3D. No guessed drawing."""
    panels=[]
    for i,row in enumerate(check.corners):
        x=15+i*615
        panels.append(
            f'<text x="{x}" y="33" font-family="sans-serif" '
            f'font-size="21" fill="#222">{escape(row.corner)} '
            f'— FIRST {row.first_bend_axis.upper()}</text>'
        )
        panels.append(
            f'<text x="{x}" y="59" font-family="sans-serif" '
            'font-size="13" fill="#555">All XYZ in mm; same original CUTTING '
            'point at every stage</text>'
        )
        for k,leg in enumerate(("SIDE_UPPER","BOTTOM_LOWER")):
            row_hit=next(t for t in row.sequential_source_cut_edge_tracks
                         if t[1]==leg and t[2]==.5)
            _,_leg,frac,uv,p1,p2,first_t,last_t=row_hit
            y=100+k*195
            color="#c35920" if k==0 else "#175fb1"
            panels.append(
                f'<text x="{x}" y="{y}" fill="{color}" '
                f'font-family="sans-serif" font-size="18">{escape(leg)}</text>'
            )
            for j,(title,point) in enumerate((
                ("SOURCE UV",(uv[0],uv[1],0.0)),
                ("STAGE 1 XYZ",p1),
                ("STAGE 2 XYZ",p2),
            )):
                xx=x+203*j
                panels.append(
                    f'<rect x="{xx}" y="{y+17}" width="186" height="115" '
                    'rx="8" fill="#f6f7f9" stroke="#b5bdc8"/>'
                    f'<text x="{xx+9}" y="{y+41}" font-family="sans-serif" '
                    f'font-size="13" fill="#444">{title}</text>'
                    f'<text x="{xx+9}" y="{y+67}" font-family="monospace" '
                    f'font-size="15" fill="#111">X={_finite(point[0]):.4f}</text>'
                    f'<text x="{xx+9}" y="{y+88}" font-family="monospace" '
                    f'font-size="15" fill="#111">Y={_finite(point[1]):.4f}</text>'
                    f'<text x="{xx+9}" y="{y+109}" font-family="monospace" '
                    f'font-size="15" fill="#111">Z={_finite(point[2]):.4f}</text>'
                )
                if j<2:
                    panels.append(
                        f'<path d="M {xx+188} {y+77} l 10 0" '
                        'stroke="#333" stroke-width="2"/>'
                    )
        panels.append(
            f'<text x="{x}" y="523" font-family="sans-serif" '
            'font-size="13" fill="#902b30">'
            'Root process: finite BEND-end transition NOT verified</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1240 570" width="1488" height="684">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<title>WHD original Tail V edge points after physical FIRST then '
        'SECOND folds; one source mesh; CHECK only</title>'
        +''.join(panels)+'</svg>'
    ).encode("utf-8")


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



def _png_sequential_same_sheet_stages(check):
    """Real one-source meshes after FIRST and SECOND bends, both corners.

    Cropping is a camera-only source-region selection for readable views.
    There is no substitute part geometry, fabricated crease, or mesh edit.
    """
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    if len(check.sequential_same_sheet_stage_models)!=1:
        raise ValueError("WHD stage preview requires one operator first-axis")
    first_axis,seq=check.sequential_same_sheet_stage_models[0]
    fig=Figure(figsize=(12,8),dpi=120)
    FigureCanvasAgg(fig)
    for side_i,(corner,apex,source_opening) in enumerate((
        ("bottom_left",check.left_apex,check.left_outer_v_hits),
        ("bottom_right",check.right_apex,check.right_outer_v_hits),
    )):
        is_left=side_i==0
        x_edge=float(source_opening[0].x)
        ax_x_min=(x_edge-3.0 if is_left else float(apex.x)-19.0)
        ax_x_max=(float(apex.x)+19.0 if is_left else x_edge+3.0)
        y_min=float(source_opening[0].y)-7.0
        y_max=float(source_opening[1].y)+14.0
        for step_i,(stage,skin) in enumerate((
            ("AFTER FIRST",seq.first_formed_skin_triangles),
            ("AFTER SECOND",seq.second_formed_skin_triangles),
        )):
            visible=tuple(
                tri3 for tri2,tri3 in zip(seq.flat_source_triangles,skin)
                if any(ax_x_min <= p[0]<=ax_x_max
                       and y_min<=p[1]<=y_max for p in tri2)
            )
            if not visible:
                raise ValueError("WHD stage preview missing real source triangles")
            ax=fig.add_subplot(2,2,step_i*2+side_i+1,projection="3d")
            faces=tuple(
                tuple(tuple(_finite(v) for v in p) for p in tri)
                for tri in visible
            )
            ax.add_collection3d(
                Poly3DCollection(faces,linewidths=.07,alpha=.85)
            )
            allxyz=tuple(p for tri in faces for p in tri)
            xs,ys,zs=([p[i] for p in allxyz] for i in range(3))
            ax.set_xlim(min(xs)-1,max(xs)+1)
            ax.set_ylim(min(ys)-1,max(ys)+1)
            ax.set_zlim(min(zs)-1,max(zs)+1)
            ax.set_box_aspect(
                (max(xs)-min(xs)+2,max(ys)-min(ys)+2,max(zs)-min(zs)+2),
                zoom=.78,
            )
            ax.view_init(elev=28,azim=-65 if is_left else -116)
            ax.set_xlabel("X (mm)")
            ax.set_ylabel("Y (mm)")
            ax.set_zlabel("Z (mm)")
            ax.set_title(
                f"{corner} / {stage} / FIRST {first_axis.upper()}",
                fontsize=11,
            )
    fig.suptitle(
        "WHD Tail - one original Factory sheet, first and second RBA/T bends (CHECK)",
        fontsize=13,
    )
    out=io.BytesIO()
    fig.savefig(out,format="png",bbox_inches="tight")
    fig.clear()
    return out.getvalue()


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
        def z_span(faces):
            z = [float(vertex[2]) for tri in faces for vertex in tri]
            return [min(z), max(z)] if z else None
        corners.append({
            "corner":row.corner,
            "alternative_mating_pair":{
                "candidate_id":
                    row.alternative_existing_stock_contact_trial.candidate_id,
                "candidate_is_already_approved_V":False,
                "side_surface_original_source":
                    row.alternative_existing_stock_contact_trial.side_surface_source,
                "bottom_surface_original_source":
                    row.alternative_existing_stock_contact_trial.bottom_surface_source,
                "bottom_real_source_area_mm2":
                    row.alternative_existing_stock_contact_trial.bottom_broad_source_area_mm2,
                "bottom_source_triangle_count":
                    len(row.alternative_existing_stock_contact_trial.bottom_broad_source_triangles_xy),
                "side_cut_wall_triangle_count":
                    len(row.alternative_existing_stock_contact_trial.side_true_t_faces),
                "bottom_true_T_broad_skin_triangle_count":
                    len(row.alternative_existing_stock_contact_trial.bottom_true_t_broad_faces),
                "material_validity":
                    row.alternative_existing_stock_contact_trial.source_validity_status,
                "status":
                    row.alternative_existing_stock_contact_trial.seam_mating_status,
                "root_physical_status":
                    row.alternative_existing_stock_contact_trial.root_physical_status,
                "full_span_error":
                    row.alternative_existing_stock_contact_trial.full_span_error,
                "full_span":{
                    "max_sampled_gap_mm":(
                        row.alternative_existing_stock_contact_trial.full_span_coverage.max_sampled_cut_face_gap_mm
                        if row.alternative_existing_stock_contact_trial.full_span_coverage else None
                    ),
                    "upper_bound_mm":(
                        row.alternative_existing_stock_contact_trial.full_span_coverage.max_gap_upper_bound_mm
                        if row.alternative_existing_stock_contact_trial.full_span_coverage else None
                    ),
                    "missing_face_intervals":(
                        row.alternative_existing_stock_contact_trial.full_span_coverage.missing_face_interval_count
                        if row.alternative_existing_stock_contact_trial.full_span_coverage else None
                    ),
                    "unresolved_events":(
                        row.alternative_existing_stock_contact_trial.full_span_coverage.numerically_unresolved_vertex_event_count
                        if row.alternative_existing_stock_contact_trial.full_span_coverage else None
                    ),
                },
                "actual_Z_gap_and_nearest_xyz":[
                    {"z":z,"status":status,"gap_mm":gap,
                     "side_original_V_cut_wall_xyz":sidept,
                     "bottom_existing_T_broad_skin_xyz":bottompt,
                     "off_datum_shortcut":shortcut}
                    for z,status,gap,sidept,bottompt,shortcut
                    in row.alternative_existing_stock_contact_trial.sampled_section_z_gap_mm
                ],
                "actual_CUTTING_changes":"NONE",
            },
            "same_sheet_stage_source_cut_tracks":[
                {"leg":leg,"source_fraction":fraction,"source_uv":uv,
                 "after_first_xyz":first_xyz,"after_second_xyz":final_xyz,
                 "stage1_T_plus_minus_xyz":first_t,
                 "stage2_T_plus_minus_xyz":final_t}
                for _corner,leg,fraction,uv,first_xyz,final_xyz,first_t,final_t
                in row.sequential_source_cut_edge_tracks
            ],
            "sequential_final_true_T_gap_by_actual_z_mm":[
                {"z":z,"status":status,"gap_mm":gap,
                 "side_cut_xyz_mm":side,"bottom_cut_xyz_mm":bottom}
                for z,status,gap,side,bottom
                in row.sequential_final_seam_sections
            ],
            "sequential_inverse_actual_retained_cutting_check":[
                {"z":z,"proposed_side_uv":sideuv,
                 "side_source_exists_on_actual_cutting":side_exists,
                 "side_after_two_folds_xyz":side3,
                 "side_formed_datum_error_mm":side_error,
                 "proposed_bottom_uv":bottomuv,
                 "bottom_source_exists_on_actual_cutting":bottom_exists,
                 "bottom_after_two_folds_xyz":bottom3,
                 "bottom_formed_datum_error_mm":bottom_error,
                 "status":"CHECK_NOT_A_VALID_NEW_CUT_LINE"}
                for z,sideuv,side_exists,side3,side_error,
                    bottomuv,bottom_exists,bottom3,bottom_error
                in row.sequential_inverse_actual_source_trace_mm
            ],
            "sequential_root_process_status":
                row.sequential_root_process_status,
            "sequential_final_full_seam":{
                "sampled_max_gap_mm":(
                    row.sequential_final_full_seam_continuity.max_sampled_cut_face_gap_mm
                    if row.sequential_final_full_seam_continuity else None
                ),
                "upper_bound_mm":(
                    row.sequential_final_full_seam_continuity.max_gap_upper_bound_mm
                    if row.sequential_final_full_seam_continuity else None
                ),
                "lower_bound_mm":(
                    row.sequential_final_full_seam_continuity.max_gap_lower_bound_mm
                    if row.sequential_final_full_seam_continuity else None
                ),
                "missing_intervals":(
                    row.sequential_final_full_seam_continuity.missing_face_interval_count
                    if row.sequential_final_full_seam_continuity else None
                ),
                "vertex_events":(
                    row.sequential_final_full_seam_continuity.numerically_unresolved_vertex_event_count
                    if row.sequential_final_full_seam_continuity else None
                ),
            },
            "sequential_source_true_T_cut_face_z_ranges_mm":{
                "after_first_side":z_span(row.sequential_first_side_cut_faces),
                "after_first_bottom":z_span(row.sequential_first_bottom_cut_faces),
                "after_second_side":z_span(row.sequential_second_side_cut_faces),
                "after_second_bottom":z_span(row.sequential_second_bottom_cut_faces),
            },
            "operator_first_physical_bend_axis":row.first_bend_axis,
            "operator_second_physical_bend_axis":row.second_bend_axis,
            "source_true_T_mating_faces":{
                "side":"upper V original CUTTING -> side X BEND",
                "bottom":"lower V original CUTTING -> bottom Y BEND",
            },
            "side_cut_face_z_mm":z_span(row.side_cut_faces),
            "bottom_cut_face_z_mm":z_span(row.bottom_cut_faces),
            "status":row.model_status,
            "surface_intersection_triangle_pairs":row.model_interference_pairs,
            "surface_intersection_segments_xyz":row.model_interference_segments,
            "root_intersection_topology":row.root_intersection_topology,
            "surface_intersection_pairs_do_not_prove_penetration":True,
            "volume_status":row.model_volume_status,
            "straight_section_y_domain_witness_mm":{
                "side_fold_source_min_y":row.straight_section_y_domain_witness_mm[0],
                "bottom_fold_straight_true_T_outer_max_y":row.straight_section_y_domain_witness_mm[1],
                "minimum_y_projection_gap":row.straight_section_y_domain_witness_mm[2],
                "hypothetical_seam_y":row.straight_section_y_domain_witness_mm[3],
                "scope":"current separated RBA patches, not universal V impossibility",
            },
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
            "actual_true_T_cut_face_nearest_points": [
                {"fraction":frac, "gap_mm":gap, "side_cut_xyz_mm":s,
                 "bottom_cut_xyz_mm":b, "status":status}
                for frac,gap,s,b,status in row.sampled_cut_face_nearest_xyz
            ],
            "side_upper_and_bottom_lower_source_v_lengths_mm":
                row.source_cut_leg_owner_lengths_mm,
            "hypothetical_RBA_inverse_source_coverage":
                row.inverse_flat_source_coverage_mm,
            "hypothetical_RBA_inverse_not_cutting_xyz":
                row.inverse_straight_contact_flat_trace_mm,
            "hypothetical_RBA_root_source_inverses":{
                "side_upper_root_xy":row.inverse_root_arc_source_traces_xy[0],
                "bottom_lower_root_xy":row.inverse_root_arc_source_traces_xy[1],
                "nonapex_crossings_xy":row.inverse_root_nonapex_crossings_xy,
                "status":row.inverse_root_candidate_status,
                "cutting_permission":"NONE",
            },
            "minimum_side_BEND_start_to_hypothetical_y_station_mm":
                max((r[-1] for r in row.inverse_straight_contact_flat_trace_mm),
                    default=None),
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
        "operator_first_bend_axes":check.operator_first_bend_axes,
        "fold_order_contact_scope":"one source triangle mesh, physical first then second RBA/T stage; finite root transition not physically certified",
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
        "one_sheet_two_stage_models":[
            {"operator_first_axis":axis,
             "operator_second_axis":seq.second_axis,
             "source_area_mm2":seq.source_area_mm2,
             "source_triangle_count":len(seq.flat_source_triangles),
             "stage1_triangle_count":len(seq.first_formed_skin_triangles),
             "stage2_triangle_count":len(seq.second_formed_skin_triangles),
             "source_fold_ownership":{
                 "one_fold_per_source_point":seq.source_double_bend_vertices==0,
                 "x_only_source_vertices":seq.source_x_only_vertices,
                 "y_only_source_vertices":seq.source_y_only_vertices,
                 "both_fold_source_vertices":seq.source_double_bend_vertices,
                 "X_then_Y_vs_Y_then_X_final_xyz_max_difference_mm":
                     seq.max_X_then_Y_vs_Y_then_X_final_delta_mm,
                 "order_changes_last_stage_coordinates":False,
             },
             "stage1_T_solid_triangle_count":len(seq.first_thick_solid_triangles),
             "stage2_T_solid_triangle_count":len(seq.second_thick_solid_triangles),
             "first_stage_max_same_source_vertex_jump_mm":
                seq.first_stage_max_duplicate_vertex_jump_mm,
             "final_stage_max_same_source_vertex_jump_mm":
                seq.final_stage_max_duplicate_vertex_jump_mm,
             "root_process_status":seq.root_process_status,
             "manufacturing_status":seq.manufacturing_status,
             "stage1_T_shell_topology":{
                 "boundary_edges":seq.stage1_shell_topology.boundary_edge_count,
                 "nonmanifold_edges":seq.stage1_shell_topology.nonmanifold_edge_count,
                 "nonmanifold_vertices":seq.stage1_shell_topology.nonmanifold_vertex_count,
                 "degenerate_triangles":seq.stage1_shell_topology.degenerate_triangle_count,
                 "edges_manifold_closed":seq.stage1_shell_topology.edges_manifold_closed,
             },
             "stage2_T_shell_topology":{
                 "boundary_edges":seq.stage2_shell_topology.boundary_edge_count,
                 "nonmanifold_edges":seq.stage2_shell_topology.nonmanifold_edge_count,
                 "nonmanifold_vertices":seq.stage2_shell_topology.nonmanifold_vertex_count,
                 "degenerate_triangles":seq.stage2_shell_topology.degenerate_triangle_count,
                 "edges_manifold_closed":seq.stage2_shell_topology.edges_manifold_closed,
             },
             "root_true_T_self_intersection":[
                 {"corner":corner,
                  "stage1_roi_T_triangles":n1,
                  "stage2_roi_T_triangles":n2,
                  "stage1_nonadjacent_pairs_tested":d1.tested_nonadjacent_pairs,
                  "stage1_surface_crossings":d1.crossing_pair_count,
                  "stage1_coplanar_overlap":d1.coplanar_overlap_pair_count,
                  "stage1_work_exhausted":d1.numerical_budget_exhausted,
                  "stage1_first_pair":d1.first_source_triangle_pair,
                  "stage2_nonadjacent_pairs_tested":d2.tested_nonadjacent_pairs,
                  "stage2_surface_crossings":d2.crossing_pair_count,
                  "stage2_coplanar_overlap":d2.coplanar_overlap_pair_count,
                  "stage2_work_exhausted":d2.numerical_budget_exhausted,
                  "stage2_first_pair":d2.first_source_triangle_pair,
                  "status":"ROOT_SELF_SURFACE_CHECK_ONLY_NO_VOLUME_CERTIFICATION"}
                 for corner,d1,d2,n1,n2
                 in seq.root_true_t_self_intersection_by_corner
             ]}
            for axis,seq in check.sequential_same_sheet_stage_models
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
    true_t_section=_svg_true_t_sections(check)
    combined=_svg_same_source_2d_and_true_t_sections(check)
    alt_overlay=_svg_alternative_original_overlay_and_section(check)
    alt_section=_svg_alternative_original_surface_sections(check)
    obj=_actual_obj(check,native=True)
    physical_obj=_actual_obj(check,native=False)
    stage_tracks=_svg_first_then_second_v_tracks(check)
    if len(check.sequential_same_sheet_stage_models)!=1:
        raise ValueError("WHD exported single-sheet stage order not uniquely selected")
    _,seq=check.sequential_same_sheet_stage_models[0]
    first_solid=_one_source_mesh_obj(
        seq.first_thick_solid_triangles,label="FIRST_SOURCE_T_SHEET",
    )
    final_solid=_one_source_mesh_obj(
        seq.second_thick_solid_triangles,label="SECOND_SOURCE_T_SHEET",
    )
    png=_png_actual_mesh(check)
    staged_png=_png_sequential_same_sheet_stages(check)
    report=json.dumps(_model_report(check),ensure_ascii=False,indent=2,
                      sort_keys=True).encode("utf-8")
    stream=io.BytesIO()
    with ZipFile(stream,"w",compression=ZIP_DEFLATED,compresslevel=9) as out:
        out.writestr("WHD_tail_dual_V_same_source_2D.svg",flat)
        out.writestr("WHD_tail_dual_V_true_T_left_right_sections.svg",true_t_section)
        out.writestr("WHD_tail_dual_V_original_2D_and_folded_true_T_sections.svg",combined)
        out.writestr("WHD_tail_dual_V_ALTERNATIVE_original_candidate_overlay_sections.svg",alt_overlay)
        out.writestr("WHD_tail_dual_V_ALTERNATIVE_real_T_broad_face_sections.svg",alt_section)
        out.writestr("WHD_tail_dual_V_actual_folded_model.obj",obj)
        out.writestr("WHD_tail_dual_V_RBA_focused_fold_check.obj",physical_obj)
        out.writestr("WHD_tail_dual_V_same_sheet_AFTER_FIRST_T.obj",first_solid)
        out.writestr("WHD_tail_dual_V_same_sheet_AFTER_SECOND_T.obj",final_solid)
        out.writestr("WHD_tail_dual_V_same_sheet_stage1_stage2_V_tracks.svg",
                     stage_tracks)
        out.writestr("WHD_tail_dual_V_folded_preview.png",png)
        out.writestr("WHD_tail_dual_V_same_sheet_FIRST_SECOND_3D.png",staged_png)
        out.writestr("WHD_tail_dual_V_model_diagnosis.json",report)
    return stream.getvalue()
