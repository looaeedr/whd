"""#3317 REAL WHD Tail original/legacy guess/confirmed constraints 2D.

Only projection from actual EndCapPartSpec / Factory / FinalScene geometry.
All six comparison panels use identical physical mm XY scale. No
fabrication DXF, fabricated asymmetrical V, 3D, R/BA gap or root estimate.
"""
from __future__ import annotations

import json
import math
from xml.sax.saxutils import escape

from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive,
)


def _num(x):
    x=float(x)
    if not math.isfinite(x):
        raise ValueError("WHD #3317 audit nonfinite coordinate")
    return x


def _xy(p):
    return (_num(p.x),_num(p.y))


def _line_coords(p):
    return " ".join(f"{_num(x):.5f},{_num(y):.5f}" for x,y in p)


def _polys(polygon):
    if polygon.is_empty:
        return ()
    if polygon.geom_type=="Polygon":
        return (polygon,)
    return tuple(part for part in getattr(polygon,"geoms",())
                 if part.geom_type=="Polygon" and part.area>0)


def _polygon_svg(polygon, *, color, opacity, border="none", dash=""):
    segments=[]
    for piece in _polys(polygon):
        perimeter=_line_coords(piece.exterior.coords)
        d="M "+" L ".join(perimeter.split())+" Z"
        for hole in piece.interiors:
            d+=" M "+" L ".join(_line_coords(hole.coords).split())+" Z"
        segments.append(
            f'<path d="{d}" fill="{color}" fill-opacity="{opacity}" '
            f'fill-rule="evenodd" stroke="{border}" stroke-width=".23" '
            f'{dash}/>'
        )
    return "".join(segments)


def _source_marks(audit):
    rows=[]
    for primitive in audit.original_scene_primitives:
        if isinstance(primitive,LinePrimitive):
            a,b=_xy(primitive.p1),_xy(primitive.p2)
            color="#135dc4" if primitive.layer=="BEND" else "#748393"
            rows.append(
                f'<line x1="{a[0]:.5f}" y1="{a[1]:.5f}" '
                f'x2="{b[0]:.5f}" y2="{b[1]:.5f}" '
                f'stroke="{color}" stroke-width=".45" '
                f'stroke-dasharray="{("1.4,.7" if primitive.layer=="BEND" else "1,1")}"/>'
            )
        elif isinstance(primitive,CirclePrimitive):
            x,y=_xy(primitive.center)
            rows.append(
                f'<circle cx="{x:.5f}" cy="{y:.5f}" '
                f'r="{_num(primitive.radius):.5f}" '
                'fill="none" stroke="#516b7e" stroke-width=".24"/>'
            )
        elif isinstance(primitive,PolylinePrimitive) and primitive.layer!="CUTTING":
            d="M "+" L ".join(
                f"{_num(p.x):.5f},{_num(p.y):.5f}" for p in primitive.points
            )
            if primitive.closed: d+=" Z"
            rows.append(
                f'<path d="{d}" fill="none" '
                'stroke="#7891a1" stroke-width=".2"/>'
            )
    return "".join(rows)


def _plot_row(audit,row,mode):
    orig=audit.original_factory_cutting
    parts=[]
    if mode=="factory":
        parts.append(_polygon_svg(orig,color="#79b599",opacity=".66",
                                  border="#126947"))
        parts.append(_polygon_svg(
            row.actual_factory_removed_corner,color="url(#cutHatch)",
            opacity=".85",border="#bc3152",
        ))
    elif mode=="legacy":
        parts.append(_polygon_svg(orig,color="#9cafa3",opacity=".45",
                                  border="#758c79",
                                  dash='stroke-dasharray="1,1"'))
        parts.append(_polygon_svg(
            audit.historical_symmetric_cutting,color="#ffc66b",
            opacity=".46",border="#b36910",
        ))
        parts.append(_polygon_svg(
            row.historical_added_vs_factory,color="#1cb8b3",
            opacity=".60",border="#00857f",
        ))
        parts.append(_polygon_svg(
            row.historical_removed_vs_factory,color="#eb5b64",
            opacity=".60",border="#ad2134",
        ))
        parts.append(_polygon_svg(
            row.historical_symmetric_removed_wedge,color="none",
            opacity="1",border="#bd2834",
            dash='stroke-dasharray="1.5,.8"',
        ))
        for pt in (row.historical_low_outer,row.historical_high_outer):
            x,y=_xy(pt)
            parts.append(
                f'<circle cx="{x:.4f}" cy="{y:.4f}" r=".8" '
                'fill="#dc2031" stroke="white" stroke-width=".2"/>'
            )
    else:
        parts.append(_polygon_svg(orig,color="#79b599",opacity=".66",
                                  border="#126947"))
        parts.append(_polygon_svg(
            row.actual_factory_removed_corner,color="url(#cutHatch)",
            opacity=".85",border="#bc3152",
        ))
        # A cyan dotted line marks only the known outer side's X station.
        # Unknown y-low/y-high are NOT invented or plotted as rays.
        x=row.outer_side_x_mm
        parts.append(
            f'<line x1="{x:.4f}" y1="0" '
            f'x2="{x:.4f}" y2="78" '
            'stroke="#027eae" stroke-width=".50" stroke-dasharray="1,1"/>'
        )
    parts.append(_source_marks(audit))
    # Original physical crease endpoints and NOMINAL station intersection.
    for key,axis,ends in audit.original_factory_bend_rows:
        if key!=row.corner:
            continue
        for x,y in ends:
            parts.append(
                f'<circle cx="{_num(x):.4f}" cy="{_num(y):.4f}" '
                'r=".58" fill="white" stroke="#165ac3" stroke-width=".32"/>'
            )
    ax,ay=_xy(row.nominal_apex)
    parts.append(
        f'<circle cx="{ax:.5f}" cy="{ay:.5f}" r=".75" '
        'stroke="white" stroke-width=".25" fill="#182fa1"/>'
    )
    return "".join(parts)


def tail_flat_source_audit_report(audit, *, snapshot_baseline: str | None=None):
    def p2(x):return [_num(x.x),_num(x.y)]
    def contour(poly):
        return [
            [[_num(x),_num(y)] for x,y in piece.exterior.coords]
            for piece in _polys(poly)
        ]
    rows=[]
    for c in audit.corner_rows:
        rows.append({
            "corner":c.corner,
            "original_nominal_apex_xy_mm":p2(c.nominal_apex),
            "apex_source":"ACTUAL_X_Y_BEND_STATION_INTERSECTION_NOT_EXTRA_BEND",
            "real_finite_side_BEND_endpoints_xy_mm":c.real_side_bend_xy,
            "real_finite_bottom_BEND_endpoints_xy_mm":c.real_bottom_bend_xy,
            "same_side_outer_x_mm":c.outer_side_x_mm,
            "original_factory_removed_relief_area_mm2":_num(
                c.actual_factory_removed_corner.area
            ),
            "original_factory_removed_relief_outline_xy_mm":contour(
                c.actual_factory_removed_corner
            ),
            "historical_only_symmetric_V_lower_outer_y_mm":
                _num(c.historical_low_outer.y),
            "historical_only_symmetric_V_upper_outer_y_mm":
                _num(c.historical_high_outer.y),
            "historical_only_symmetric_removed_area_mm2":_num(
                c.historical_symmetric_removed_wedge.area
            ),
            "old_hypothesis_added_vs_original_mm2":_num(
                c.historical_added_vs_factory.area
            ),
            "old_hypothesis_removed_vs_original_mm2":_num(
                c.historical_removed_vs_factory.area
            ),
            "old_hypothesis_added_contours_xy_mm":contour(
                c.historical_added_vs_factory
            ),
            "old_hypothesis_removed_contours_xy_mm":contour(
                c.historical_removed_vs_factory
            ),
            "confirmed_lower_opening_y_mm":None,
            "confirmed_upper_opening_y_mm":None,
            "confirmed_two_angled_cut_edges_xy":None,
            "confirmed_new_cutting_polygon":None,
            "confirmed_retained_and_removed_new_stock":None,
            "candidate_status":c.status,
        })
    return {
        "source":"WHD EndCapPartSpec -> Factory/FinalScene -> original CUTTING and BEND",
        "part_spec":dict(audit.spec_identity),
        "snapshot_baseline_selection":snapshot_baseline,
        "snapshot_is_individual_user_project":False,
        "source_match":audit.source_proof_status,
        "current_2d_Factory_original_area_mm2":_num(
            audit.original_factory_cutting.area
        ),
        "factory_original_outline_xy_mm":contour(
            audit.original_factory_cutting
        ),
        "source_original_BEND_lines_xy_mm":audit.original_factory_bend_rows,
        "historical_symmetric_only_outline_xy_mm":contour(
            audit.historical_symmetric_cutting
        ),
        "all_original_scene_primitive_count":len(audit.original_scene_primitives),
        "numerical_source_tolerance_mm":audit.numerical_geometry_tolerance_mm,
        "strict_V_contract":{
            "outer_opening_side":"LEFT_OUTER_FOR_LEFT_AND_RIGHT_OUTER_FOR_RIGHT",
            "nominal_apex":"PHYSICAL_X_Y_BEND_STATIONS_INTERSECTION",
            "two_sloping_cut_edges":"REQUIRED_BUT_NOT_YET_RESOLVED",
            "asymmetric_slopes":"ALLOWED_NOT_AUTOMATICALLY_45_DEGREES",
            "actual_opening_coordinates":"UNKNOWN_UNRESOLVED",
        },
        "left_and_right":rows,
        "current_factory_cutting_changed":False,
        "drawing_status":"ORIGINAL_PROVEN_OLD_HYPOTHESIS_REJECTED_NEW_V_UNKNOWN",
        "manufacturing_DXF":"NOT_ALLOWED",
        "3D_or_formed_gap_from_legacy_assumption":"NOT_RUN_NOT_USER_SPEC",
    }


def render_tail_flat_source_comparison_svg(audit):
    """Left and right, THREE physically equal-scale UV panels each."""
    cols=(("factory","FACTORY 原板 CUTTING"),
          ("legacy","OLD GUESS ±45° (非規格)"),
          ("verified","來源已核對 / 真 V 待求"))
    x0=(32,626,1220)
    y0=(105,620)
    panelw,panelh=558,430
    fullx=float(audit.original_factory_mother.bounds[2])
    plot_range_mm=(49.0,86.0)
    out=[
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1810 1140" width="1810" height="1140">'
        '<defs><pattern id="cutHatch" width="5" height="5" '
        'patternUnits="userSpaceOnUse">'
        '<rect width="5" height="5" fill="#ffe1e4"/>'
        '<path d="M-1 1L4 6 M1 -1L6 4" '
        'stroke="#cf6476" stroke-width="1"/></pattern></defs>'
        '<rect width="100%" height="100%" fill="#fff"/>'
        '<text x="26" y="33" font-size="23" font-family="sans-serif" '
        'fill="#202020">#3317 WHD 封尾：原板 / 舊對稱 V 假設 / 來源核對</text>'
        '<text x="26" y="57" font-size="14" font-family="sans-serif" '
        'fill="#4d4d4d">各圖相同 X/Y 比例、原 Factory mm 座標；'
        '綠=原實料，斜紋=Factory 原截角已切除，'
        '青=舊假設額外補回，紅=舊假設額外切除。</text>'
    ]
    for i,c in enumerate(audit.corner_rows):
        if c.corner=="bottom_left":
            viewport=(-6.,-5.,*plot_range_mm)
            side_name="左下"
        else:
            viewport=(fullx-plot_range_mm[0]+6.,-5.,*plot_range_mm)
            side_name="右下"
        sx,sy,sw,sh=viewport
        for j,(mode,colname) in enumerate(cols):
            xx,yy=x0[j],y0[i]
            out.extend([
                f'<text x="{xx}" y="{yy-10}" font-family="sans-serif" '
                f'font-size="17" fill="#23384e">{side_name}：'
                f'{escape(colname)}</text>',
                f'<rect x="{xx}" y="{yy}" width="{panelw}" height="{panelh}" '
                'fill="#fff" stroke="#bcc5ce" stroke-width="1"/>',
                f'<svg x="{xx+4}" y="{yy+4}" width="{panelw-8}" '
                f'height="{panelh-8}" '
                f'viewBox="{sx:.3f} {sy:.3f} {sw:.3f} {sh:.3f}" '
                'preserveAspectRatio="xMidYMid meet">',
                f'<g transform="translate(0,{2*sy+sh:.5f}) scale(1,-1)">',
                _plot_row(audit,c,mode),
                '</g></svg>',
            ])
            # Source-traceable numeric labels OUTSIDE geometry layer.
            bottom=yy+panelh+17
            if mode=="factory":
                legend=(
                    f"原截角已切除 {c.actual_factory_removed_corner.area:.3f} mm²；"
                    f"尖端 ({c.nominal_apex.x:g},{c.nominal_apex.y:g})"
                )
            elif mode=="legacy":
                legend=(
                    f"舊假設開口 Y={c.historical_low_outer.y:g}/"
                    f"{c.historical_high_outer.y:g}；非已核准線"
                )
            else:
                legend=(
                    f"同側外緣 X={c.outer_side_x_mm:g}；"
                    "兩開口 Y 與兩條斜線：未確定"
                )
            out.append(
                f'<text x="{xx+3}" y="{bottom}" '
                f'font-family="sans-serif" font-size="12.5" fill="#25374c">'
                f'{escape(legend)}</text>'
            )
            if mode=="verified":
                out.append(
                    f'<text x="{xx+3}" y="{bottom+19}" '
                    'font-family="sans-serif" font-size="12" fill="#9b2946">'
                    '尚無使用者確認的切線；不畫猜測候選</text>'
                )
    out.extend([
        '<text x="31" y="1122" font-family="sans-serif" font-size="13" '
        'fill="#545454">藍線/藍點＝原有限 BEND／其端點；'
        '深藍點＝兩折線延長站位的名義交會。'
        '此圖不是加工 DXF，沒有任何新 V 斜線獲認證。</text>',
        '</svg>',
    ])
    return "".join(out).encode("utf-8")


def build_tail_flat_audit_pair(audit, *,snapshot_baseline=None):
    report=tail_flat_source_audit_report(
        audit,snapshot_baseline=snapshot_baseline,
    )
    return (
        render_tail_flat_source_comparison_svg(audit),
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"),
    )
