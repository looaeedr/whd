# -*- coding: utf-8 -*-
"""#2383 Receiving EndCap head/tail: actual standalone manufactured sheets.

Factory Receiving D-2T and Phase6 head/tail Fold Profile own physical stock,
BEND and STANDARD/INSERT_OVERLAY corner material. The independently certified
Vault EndCap DXF supplies *only shared source hole identity* as specified by
Receiving's canonical policy, NEVER Vault's D-3T or assembly geometry.
No external source Features, Side/Back WRAP assembly or arbitrary Fold presets.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_ID = re.compile(r"^whd-[0-9a-f]{24}$")
_ROLES = frozenset(("end_cap_head", "end_cap_tail"))
_INPUTS = {
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "frame_width_mm",
    "endcap_yl1_mm", "endcap_yr1_mm",
    "endcap_ytop1_mm", "endcap_ybottom1_mm",
    "endcap_side_rear_bend_mm",
}
_SCALARS = (
    "endcap_yl1_mm", "endcap_yr1_mm",
    "endcap_ytop1_mm", "endcap_ybottom1_mm",
    "endcap_side_rear_bend_mm",
)


def receiving_endcap_spec_from_trusted_part(part: Mapping[str, Any]):
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.cabinet_types import receiving
    from ae_engine.manufacturing_api import resolve_endcap_request
    from phase6_fold_profiles import build_endcap_xy_profiles, profile_to_fold_segments

    if (not isinstance(part, Mapping)
            or set(part) != _INPUTS
            or part.get("kind") not in _ROLES
            or part.get("cabinet_family") != "受電箱"
            or part.get("source_part_ref") != part.get("kind")
            or part.get("dimension_semantics") != "cabinet_outer"):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Receiving head/tail physical source identity or topology unsupported",
        )
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {
        "width", "height", "depth", "thickness",
    }:
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "Receiving EndCap explicit cabinet W/H/D/T required",
        )
    vals = [dims[key] for key in ("width", "height", "depth", "thickness")]
    vals.append(part["frame_width_mm"])
    vals.extend(part[key] for key in _SCALARS)
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in vals):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "nonfinite or boolean EndCap factory inputs")
    w,h,d,t,fw=map(float,vals[:5])
    if (min(w,h,d,t,fw) <= 0 or w <= 4*t or h <= 2*t
            or d <= 4*t or fw <= 2*t or fw >= min(w,d)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving factory EndCap geometry impossible")
    if any(float(part[key]) <= 0 for key in _SCALARS):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving EndCap intrinsic folds must be positive")
    if float(part["endcap_side_rear_bend_mm"]) >= d:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving rear Fold extends beyond depth")
    # Create the factory's own current preset, then replace *every*
    # independently-confirmed scalar. Not an inferred 3D assembly.
    # apply_family_defaults resets factory BOX_BODY_DEFAULTS, so only
    # the later explicit updates establish source W/H/D/T/FW.
    try:
        snapshot = receiving.apply_family_defaults({})
        snapshot.update({
            "model":"受電箱","w":w,"h":h,"d":d,"t":t,"fw":fw,
            "yl1":float(part["endcap_yl1_mm"]),
            "yr1":float(part["endcap_yr1_mm"]),
            "ytop1":float(part["endcap_ytop1_mm"]),
            "ybottom1":float(part["endcap_ybottom1_mm"]),
        })
        is_tail=part["kind"]=="end_cap_tail"
        rows = build_endcap_xy_profiles(
            snapshot,part_key=("tail" if is_tail else "head"),
        )
        x_rows=profile_to_fold_segments(rows["X"])
        y_rows=profile_to_fold_segments(rows["Y"])
        if (not (1 <= len(x_rows) <= 3) or len(y_rows) != 4
                or any(float(seg.length)<=0 or not math.isfinite(float(seg.length))
                       for seg in x_rows+y_rows)
                or tuple(seg.phase6_key for seg in y_rows) not in (
                    ("ytop1","fw","endcap_d_core","ybottom1"),
                    ("ybottom1","endcap_d_core","fw","ytop1"),
                )
                or not any(seg.core=="D-T" for seg in y_rows)):
            raise ValueError("Receiving EndCap Y Fold source topology invalid")
        cp=receiving.endcap_corner_policy(
            frame_width=fw,thickness=t,
            side_rear_bend=float(part["endcap_side_rear_bend_mm"]),
        )
        spec=EndCapPartSpec(
            width=w,height=h,depth=d,thickness=t,frame_width=fw,
            model_name="受電箱",is_tail=is_tail,
            fold_left=float(part["endcap_yl1_mm"]),
            fold_right=float(part["endcap_yr1_mm"]),
            fold_top=float(part["endcap_ytop1_mm"]),
            fold_bottom=float(part["endcap_ybottom1_mm"]),
            fold_profile_x=x_rows,fold_profile_y=y_rows,
            corner_policy=cp,depth_comp_t=float(receiving.endcap_depth_comp_t()),
        )
        resolved=resolve_endcap_request(spec)
        if (resolved.model_name!="受電箱"
                or not math.isclose(resolved.depth_comp_t,2.0,abs_tol=1e-9)
                or resolved.is_tail!=is_tail
                or resolved.corner_policy is None
                or spec.assembly_joints or spec.resolved_assembly_relief_cuts
                or spec.assembly_relief is not None):
            raise ValueError("Receiving EndCap family geometry or assembly source invalid")
        return spec
    except (TypeError, ValueError, ArithmeticError, OverflowError, KeyError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "WHD canonical Receiving EndCap Fold/Corner source unavailable",
        ) from exc


def receiving_endcap_shared_baseline(root):
    """Forward family/source intent; only the Engine decides fixed-hole DXF."""
    from pathlib import Path
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import expected_endcap_feature_baseline

    try:
        return expected_endcap_feature_baseline(
            "受電箱", ManufacturingContext(resource_root=Path(root)),
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise PrepareEvidenceError(
            "WHD_RESOURCE_UNVERIFIED", "Receiving EndCap fixed-hole source unavailable",
        ) from exc


def _render(spec, context):
    from ae_engine.manufacturing_api import build_part_render_data
    from ae_engine.manufacturing_endcap_compat import resolve_endcap_request
    from ae_engine.sheetmetal_drawing import CirclePrimitive

    if spec.model_name!="受電箱" or spec.depth_comp_t!=2.0:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","Receiving 2T EndCap spec required")
    resolved=resolve_endcap_request(spec)
    if resolved.model_name!="受電箱" or resolved.depth_comp_t!=2.0:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","Receiving EndCap geometry changed family")
    try:
        render=build_part_render_data(spec,context)
        material=render.material
        holes=tuple(x for x in render.scene.primitives
                    if isinstance(x,CirclePrimitive) and x.layer=="CUTTING"
                    and getattr(x,"source_type",None)=="baseline_endcap_hole")
        if (material is None or material.is_empty or not material.is_valid
                or float(material.area)<=0 or not render.fold_guides
                or len(holes)!=3 or len({x.source_id for x in holes})!=3):
            raise ValueError("Receving EndCap canonical CUTTING/BEND/source Ø6.4 holes missing")
        x0,y0,x1,y1=map(float,material.bounds)
        if any(not math.isfinite(n) or n<=0 for n in (x1-x0,y1-y0)):
            raise ValueError("Receiving EndCap material envelope impossible")
        return render
    except (TypeError,ValueError,ArithmeticError,OverflowError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED","Receiving head/tail FinalScene does not match shared fixed-hole source",
        ) from exc


def _frame(role,width,height,physical):
    return {
        "frame_id":f"{role}:{physical}:receiving:flat:size-only-v1",
        "coordinate_contract_revision":"1","units":"mm",
        "origin_definition":(
            "WHD Receiving "+role+" D-2T canonical independent unfolded Final Material;"
            " shared certified EndCap Ø6.4 hole source only; no assembly/Feature projection"
        ),
        "origin_xyz_mm":[0.0,0.0,0.0],
        "axis_x":[1.0,0.0,0.0],"axis_y":[0.0,1.0,0.0],
        "normal":[0.0,0.0,1.0],"face_role":"outer",
        "viewed_from":"along_normal",
        "finished_face_dimensions_mm":{"width":width,"height":height},
        "allowed_feature_types":[],
    }


def receiving_endcap_frame(spec,context,*,physical_part_id):
    role="end_cap_tail" if spec.is_tail else "end_cap_head"
    if not isinstance(physical_part_id,str) or _ID.fullmatch(physical_part_id) is None:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","invalid Receiving EndCap physical ID")
    render=_render(spec,context)
    x0,y0,x1,y1=map(float,render.material.bounds)
    return _frame(role,x1-x0,y1-y0,physical_part_id)


def require_receiving_endcap_frame(frame,*,role,physical_part_id):
    if (role not in _ROLES or not isinstance(frame,Mapping)
            or not isinstance(physical_part_id,str)
            or _ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","untrusted Receiving EndCap frame")
    dims=frame.get("finished_face_dimensions_mm")
    if not isinstance(dims,Mapping) or set(dims)!={"width","height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","Receiving EndCap envelope unavailable")
    w,h=dims["width"],dims["height"]
    if any(type(n) not in (int,float) or not math.isfinite(n) or n<=0 for n in (w,h)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","invalid EndCap material bounds")
    if _pure_json(frame)!=_frame(role,float(w),float(h),physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED","Receving EndCap frame was forged")
