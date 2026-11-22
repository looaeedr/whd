# -*- coding: utf-8 -*-
"""#3317 single-source, preview-only lower bilateral V for verified Vault Tail.

The ONLY enabled physical source is the operator-confirmed 522 x 233 mm
intrinsic Vault Tail specimen at W500/D150/T2/FW25/15-15-16-48. Existing
upper folds and holes are regenerated from the same original EndCap Factory
scene and remain unchanged. No BA/R is ever synthesized.

This GUI choice is *not* CornerType, a new manufacturing capability, or a
machine-ready DXF. In all other families/sizes, the Engine rejects V.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .sheetmetal_geometry_core import GeometryError
from .manufacturing_render_data import (
    PartRenderData, fold_guides_from_final_scene,
    material_polygon_from_final_scene,
)

TAIL_LOWER_V_SNAPSHOT_KEY = "tail_lower_v_choice"
TAIL_LOWER_V_ORIGINAL = "original"
TAIL_LOWER_V_V90 = "v90"
TAIL_LOWER_V_UNSUPPORTED = "下方左右 V 型只支援已驗證的金庫型封尾 W500、D150、T2、FW25、左右15、上16、下48（522×233 mm）；其他尺寸／箱型不支援"


def normalize_operator_tail_lower_v_choice(raw) -> str:
    """Strict Engine project/GUI decoder; old projects stay unchanged."""
    if raw is None or raw == TAIL_LOWER_V_ORIGINAL:
        return TAIL_LOWER_V_ORIGINAL
    if type(raw) is str and raw == TAIL_LOWER_V_V90:
        return TAIL_LOWER_V_V90
    raise ValueError("下方左右截角只接受原樣／V 型；未知專案值不可默默套用")


def _validated_spec(spec):
    from .contracts import EndCapPartSpec
    if not isinstance(spec, EndCapPartSpec) or not spec.is_tail:
        raise ValueError(TAIL_LOWER_V_UNSUPPORTED)
    values=(
        ("width",500.),("depth",150.),("thickness",2.),
        ("frame_width",25.),("fold_left",15.),("fold_right",15.),
        ("fold_top",16.),("fold_bottom",48.),
    )
    if (spec.model_name not in ("金庫型","VAULT")
            or spec.corner_policy is not None
            or any(
                type(getattr(spec,key,None)) is bool
                or getattr(spec,key,None) is None
                or abs(float(getattr(spec,key))-wanted)>1e-7
                for key,wanted in values
            )):
        raise ValueError(TAIL_LOWER_V_UNSUPPORTED)
    return spec


def project_operator_tail_lower_v_settings(snapshot: Mapping, *, context: str):
    """Return data ONLY for the existing Vault Tail corner group."""
    source=dict(snapshot or {})
    if str(context)!="tail" or source.get("model") not in ("金庫型","VAULT"):
        return None
    return {
        "choice": normalize_operator_tail_lower_v_choice(
            source.get(TAIL_LOWER_V_SNAPSHOT_KEY)
        ),
        "labels": ("原樣","V 型"),
        "label": "下方左右截角",
    }


def commit_operator_tail_lower_v_choice(
    source: Mapping, choice, *, tail_scene_values: Mapping,
) -> dict:
    """Validate *live* physical source before accepting a V UI selection.

    GUI forwards values; all production identity/number rules stay in Engine.
    Failure is atomic: return no modified source and tell operator unsupported.
    """
    value=normalize_operator_tail_lower_v_choice(choice)
    result=dict(source or {})
    if value==TAIL_LOWER_V_V90:
        raw=dict(tail_scene_values or {})
        if raw.get("model") not in ("金庫型","VAULT"):
            raise ValueError(TAIL_LOWER_V_UNSUPPORTED)
        req=(("w",500.),("d",150.),("t",2.),("fw",25.),
             ("yl1",15.),("yr1",15.),("ytop1",16.),("ybottom1",48.))
        try:
            acceptable=all(
                type(raw.get(key)) is not bool and
                abs(float(raw[key])-target)<=1e-7
                for key,target in req
            )
        except (KeyError,ValueError,TypeError,OverflowError):
            acceptable=False
        if not acceptable:
            raise ValueError(TAIL_LOWER_V_UNSUPPORTED)
        result[TAIL_LOWER_V_SNAPSHOT_KEY]=value
    else:
        # Removing the OPTIONAL key exactly restores pre-feature project
        # semantics (and keeps legacy projects byte-identical where possible).
        result.pop(TAIL_LOWER_V_SNAPSHOT_KEY,None)
    return result


def project_operator_tail_lower_v_preview_render(spec, *, choice: str):
    """One Factory source: 2D FinalScene + same-source T2 preview mesh.

    Never project onto the original generic endcap render as a 'nearby'
    alternate 522x233 specimen. Strict spec gate runs before touching it.
    """
    if normalize_operator_tail_lower_v_choice(choice)!=TAIL_LOWER_V_V90:
        raise ValueError("原樣模式不得建立額外 V 預覽")
    spec=_validated_spec(spec)
    from .ae_endcap import _build_end_cap_scene
    from .v_miter_tail_user_image_source import (
        project_tail_illustrated_side_v90_flat,
    )
    from .v_miter_tail_full_t_no_ba import project_tail_v90_full_t_no_ba

    scene=_build_end_cap_scene(
        w=spec.width,d=spec.depth,t=spec.thickness,
        fw=spec.frame_width,yl1=spec.fold_left,yr1=spec.fold_right,
        ytop1=spec.fold_top,ybottom1=spec.fold_bottom,
        is_tail=True,model_name=spec.model_name,
    )
    base=PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"source":"WHD_INTRINSIC_VAULT_TAIL_VERIFIED_522X233"},
    )
    flat=project_tail_illustrated_side_v90_flat(spec,base)
    solid=project_tail_v90_full_t_no_ba(flat,first_axis="x")
    if solid.manufacturing_approved or solid.source_hole_count!=4:
        raise GeometryError("TAIL_V90_GUI_T2_SOURCE_HOLES_NOT_VERIFIED")
    formed=tuple(
        tuple(solid.vertices_xyz[i] for i in indices)
        for indices in solid.indexed_triangle_faces
    )
    return PartRenderData(
        scene=flat.result_scene,
        material=solid.source_material_with_holes,
        fold_guides=fold_guides_from_final_scene(flat.result_scene),
        metadata={
            "source":"WHD_INTRINSIC_VAULT_TAIL_VERIFIED_522X233",
            "tail_lower_v_choice":"v90",
            "tail_lower_v_preview_only":True,
            "tail_lower_v_full_t_mesh":formed,
            "tail_lower_v_nominal_formed_outer_mm":solid.formed_outer_extents_xyz_mm,
            "tail_lower_v_no_ba":True,
        },
        unfolded_topology=None,
    )


def tail_lower_v_preview_mesh(render_data):
    meta=getattr(render_data,"metadata",{}) or {}
    if meta.get("tail_lower_v_choice")!="v90" or meta.get("tail_lower_v_preview_only") is not True:
        return None
    rows=meta.get("tail_lower_v_full_t_mesh")
    if not isinstance(rows,tuple) or not rows:
        raise GeometryError("TAIL_V90_GUI_PREVIEW_T2_MESH_MISSING")
    return rows


def reject_tail_lower_v_preview_for_dxf(render_data):
    if (getattr(render_data,"metadata",{}) or {}).get("tail_lower_v_preview_only"):
        raise ValueError("V 型下方左右截角尚未核准加工 DXF；只能預覽 2D／3D")
