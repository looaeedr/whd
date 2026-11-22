# -*- coding: utf-8 -*-
"""#3317: corrected Vault Tail lower V *NO BA* sharp Fold Profile readback.

The user has explicitly rejected any BA for this specimen. Reuse WHD's
existing sharp-profile mapping and actual finite corrected BEND scene.
Red and blue source V edges are kept separate. The user's stated
coincident nominal sharp target is a comparison oracle, NEVER a weld,
an approved T=2 formed solid, or a claim that manufacturing faces meet.

Do not use v_miter_trial_defaults, bend allowance, or a guessed inner R.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString

from .sheetmetal_geometry_core import GeometryError


@dataclass(frozen=True)
class TailSharpNoBAVCorner:
    corner: str
    upper_source_mid_xy: tuple[float,float]
    lower_source_mid_xy: tuple[float,float]
    apex_source_xy: tuple[float,float]
    upper_current_whd_sharp_xyz: tuple[float,float,float]
    lower_current_whd_sharp_xyz: tuple[float,float,float]
    user_nominal_sharp_target_xyz: tuple[float,float,float]
    current_two_midpoint_distance_mm: float
    upper_target_error_mm: float
    lower_target_error_mm: float


@dataclass(frozen=True)
class TailSharpNoBAWitness:
    corners: tuple[TailSharpNoBAVCorner,...]
    source_blank_mm: tuple[float,float]
    nominal_outside_mm: tuple
    physical_sheet_thickness_mm: float
    geometry_model: str = "EXISTING_WHD_FINITE_BEND_SHARP_PROFILE_NO_BA_CHECK"
    outside_measurement_status: str = "NOMINAL_PROFILE_ONLY_T2_SOLID_NOT_RECONSTRUCTED"
    cut_wall_contact_status: str = "NOT_PROVEN_FROM_SHARP_MIDPOINTS"
    manufacturing_approved: bool = False


def project_tail_sharp_no_ba_v_witness(flat) -> TailSharpNoBAWitness:
    """Read same source's X/Y fold guides; compare REAL sharp vs user target.

    Uses the canonical WHD material Fold Profile and the actual finite BEND
    masks. Does not move an out-of-guide corner through a fictitious guide;
    any required extra rigid-body continuation must be proved from material
    adjacency and the changing second-fold axis, not invented here.
    """
    from .v_miter_tail_user_image_source import TailIllustratedSideV90Flat
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .endcap_xy_readback import fold_material_segment_outside_length
    from .assembly_geometry_folded_mesh import (
        _profile_geometry, _prepare_profile_mapper,
    )
    from .manufacturing_render_data import fold_guides_from_final_scene

    if not isinstance(flat,TailIllustratedSideV90Flat) or flat.manufacturing_approved:
        raise GeometryError("TAIL_SHARP_NO_BA_VERIFIED_SOURCE_REQUIRED")
    spec=flat.source_spec
    from .v_miter_tail_no_ba_sequential import (
        stations_from_real_flat,exact_tail_y_fold_profile_from_original_bends,
    )
    st=stations_from_real_flat(flat)
    if (not math.isfinite(spec.thickness) or spec.thickness<=0
            or len(flat.opening_source_points_xy)!=2
            or len(flat.side_bend_source_extensions)!=2):
        raise GeometryError("V_MITER_LOWER_ONE_SHEET_T_SOURCE_REQUIRED")
    guides=fold_guides_from_final_scene(flat.result_scene)
    for axis,station,start,end in (
            ("x",st.left_x,st.ymin,st.left_side_end),
            ("x",st.right_x,st.ymin,st.right_side_end),
            ("y",st.bottom_y,st.bottom_guide_start,st.bottom_guide_end)):
        if sum(
            g.axis==axis and abs(g.position-station)<1e-7
            and abs(g.span_start-start)<1e-7
            and abs(g.span_end-end)<1e-7 for g in guides
        )!=1:
            raise GeometryError("TAIL_SHARP_NO_BA_CORRECTED_FINITE_BEND_REQUIRED")
    snapshot={
        "model":spec.model_name,"w":spec.width,"d":spec.depth,
        "t":spec.thickness,"fw":spec.frame_width,
        "yl1":spec.fold_left,"yr1":spec.fold_right,
        "ybottom1":spec.fold_bottom,"ytop1":spec.fold_top,
    }
    p=build_endcap_xy_fold_profiles(snapshot,part_key="tail")
    # Source-exact Y Fold is local to this V preview; the editor's legacy
    # integer UI lengths and the original upper rule stay unchanged.
    p["Y"]=list(exact_tail_y_fold_profile_from_original_bends(flat,st))
    by_x={row.get("phase6_key"):row for row in p["X"]}
    by_y={row.get("phase6_key"):row for row in p["Y"]}
    nominal=(
        ("main_face_w",float(fold_material_segment_outside_length(by_x["endcap_w_core"]))),
        ("main_face_d",float(fold_material_segment_outside_length(by_y["endcap_d_core"]))),
        ("side_left",float(fold_material_segment_outside_length(by_x["yl1"]))),
        ("side_right",float(fold_material_segment_outside_length(by_x["yr1"]))),
        ("bottom",float(fold_material_segment_outside_length(by_y["ybottom1"]))),
    )
    xb,xf=_profile_geometry(p["X"])
    yb,yf=_profile_geometry(p["Y"])
    if (abs(xb[0]-st.xmin)>1e-7 or abs(xb[-1]-st.xmax)>1e-7
            or abs(yb[0]-st.ymin)>1e-7 or abs(yb[-1]-st.ymax)>1e-7):
        raise GeometryError("V_MITER_LOWER_FOLD_PROFILE_SOURCE_SIZE_MISMATCH")
    map_x=_prepare_profile_mapper(
        p["X"],axis="x",fold_guides=guides,geometry=(xb,xf),
    )
    map_y=_prepare_profile_mapper(
        p["Y"],axis="y",fold_guides=guides,geometry=(yb,yf),
    )
    def whd_mid_xy_to_xyz(xy):
        x,y=map(float,xy)
        mx,zx=map_x(x,y)
        my,zy=map_y(y,x)
        result=(float(mx),float(my),float(zx+zy))
        if any(not math.isfinite(v) for v in result):
            raise GeometryError("TAIL_SHARP_NO_BA_NONFINITE_WHD_FOLD")
        return result
    corners=[]
    for name,lower,apex,upper in flat.opening_source_points_xy:
        target_x=st.left_x if name=="bottom_left" else st.right_x
        outer_x=st.xmin if name=="bottom_left" else st.xmax
        delta=abs(outer_x-target_x)
        if (name not in ("bottom_left","bottom_right")
                or math.dist(apex,(target_x,st.bottom_y))>1e-7
                or math.dist(lower,(outer_x,st.bottom_y-delta))>1e-7
                or math.dist(upper,(outer_x,st.bottom_y+delta))>1e-7):
            raise GeometryError("V_MITER_LOWER_ACTUAL_CUT_EDGE_OR_BEND_TOPOLOGY_CHANGED")
        if any(
            LineString((apex,p)).difference(flat.result_material.boundary.buffer(1e-7)).length>1e-7
            for p in (lower,upper)
        ):
            raise GeometryError("TAIL_SHARP_NO_BA_V_NOT_ACTUAL_CUTTING")
        a=tuple((apex[i]+upper[i])/2 for i in range(2))
        b=tuple((apex[i]+lower[i])/2 for i in range(2))
        base=whd_mid_xy_to_xyz(apex)
        def anchored(uv):
            candidate=whd_mid_xy_to_xyz(uv)
            return tuple(float(candidate[i]-base[i]+(target_x,st.bottom_y,0.)[i])
                         for i in range(3))
        current_a=anchored(a)
        current_b=anchored(b)
        # Geometric sharp-fold mating oracle from THIS corner flange reach,
        # not from any specimen's image coordinates.
        user_target=(target_x,st.bottom_y+delta/2.,delta/2.)
        corners.append(TailSharpNoBAVCorner(
            corner=name,upper_source_mid_xy=a,lower_source_mid_xy=b,
            apex_source_xy=tuple(apex),
            upper_current_whd_sharp_xyz=current_a,
            lower_current_whd_sharp_xyz=current_b,
            user_nominal_sharp_target_xyz=user_target,
            current_two_midpoint_distance_mm=float(math.dist(current_a,current_b)),
            upper_target_error_mm=float(math.dist(current_a,user_target)),
            lower_target_error_mm=float(math.dist(current_b,user_target)),
        ))
    return TailSharpNoBAWitness(
        corners=tuple(corners),
        source_blank_mm=(st.xmax-st.xmin,st.ymax-st.ymin),
        nominal_outside_mm=nominal,
        physical_sheet_thickness_mm=float(spec.thickness),
    )
