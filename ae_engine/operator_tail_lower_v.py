# -*- coding: utf-8 -*-
"""#3317 single-source, preview-only lower bilateral V for verified Vault Tail.

The physical source is the current PartSpec and actual CUTTING/BEND; the
former 522 x 233 mm / T2 example is a regression case, NEVER a whitelist. Existing
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
TAIL_LOWER_V_UNSUPPORTED = "此板件的實際 CUTTING、有限 BEND、折邊歸屬或原孔不符合雙 V 求解；請核對幾何原因，不以尺寸／板件名稱限制"


def normalize_operator_tail_lower_v_choice(raw) -> str:
    """Strict Engine project/GUI decoder; old projects stay unchanged."""
    if raw is None or raw == TAIL_LOWER_V_ORIGINAL:
        return TAIL_LOWER_V_ORIGINAL
    if type(raw) is str and raw == TAIL_LOWER_V_V90:
        return TAIL_LOWER_V_V90
    raise ValueError("下方左右截角只接受原樣／V 型；未知專案值不可默默套用")


def _validated_spec(spec):
    from .contracts import EndCapPartSpec
    if not isinstance(spec, EndCapPartSpec):
        raise ValueError("V_MITER_LOWER_REQUIRES_PHYSICAL_ENDCAP_SOURCE")
    values=("width","depth","thickness","frame_width",
            "fold_left","fold_right","fold_top","fold_bottom")
    import math
    if any(
        type(getattr(spec,key,None)) not in (int,float)
        or not math.isfinite(getattr(spec,key))
        or getattr(spec,key)<=0 for key in values
    ):
        raise ValueError("V_MITER_LOWER_PHYSICAL_DIMENSIONS_INVALID")
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
        import math
        req=("w","d","t","fw","yl1","yr1","ytop1","ybottom1")
        try:
            acceptable=all(
                type(raw[key]) in (int,float) and
                math.isfinite(raw[key]) and raw[key]>0
                for key in req
            )
        except (KeyError,ValueError,TypeError,OverflowError):
            acceptable=False
        if not acceptable:
            raise ValueError("V_MITER_LOWER_MISSING_OR_INVALID_PHYSICAL_FOLD_SOURCE")
        result[TAIL_LOWER_V_SNAPSHOT_KEY]=value
    else:
        # Removing the OPTIONAL key exactly restores pre-feature project
        # semantics (and keeps legacy projects byte-identical where possible).
        result.pop(TAIL_LOWER_V_SNAPSHOT_KEY,None)
    return result


def project_operator_tail_lower_v_preview_render(
    spec, render_data=None, *, choice: str, resolved_render_data=None,
):
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

    if render_data is None:
        # Headless compatibility only. The GUI MUST forward its exact
        # canonical physical FinalScene, including original authored holes.
        scene=_build_end_cap_scene(
            w=spec.width,d=spec.depth,t=spec.thickness,
            fw=spec.frame_width,yl1=spec.fold_left,yr1=spec.fold_right,
            ytop1=spec.fold_top,ybottom1=spec.fold_bottom,
            is_tail=bool(spec.is_tail),model_name=spec.model_name,
        )
        base=PartRenderData(
            scene=scene,material=material_polygon_from_final_scene(scene),
            fold_guides=fold_guides_from_final_scene(scene),
            metadata={"source":"WHD_ACTUAL_FACTORY_SOURCE"},
        )
    elif not isinstance(render_data,PartRenderData):
        raise ValueError("V_MITER_LOWER_ACTUAL_RENDER_SOURCE_REQUIRED")
    else:
        base=render_data
    flat=project_tail_illustrated_side_v90_flat(spec,base)
    unmodified_v_source=flat
    preserved_relief=()
    if resolved_render_data is not None:
        from .v_miter_tail_relief_replay import (
            replay_independent_lower_v_relief,
        )
        flat,preserved_relief=replay_independent_lower_v_relief(
            flat,original_render=base,resolved_render=resolved_render_data,
        )
    solid=project_tail_v90_full_t_no_ba(flat,first_axis="x")
    if solid.manufacturing_approved:
        raise GeometryError("V_MITER_LOWER_PREVIEW_UNEXPECTED_EXPORT_APPROVAL")
    formed=tuple(
        tuple(solid.vertices_xyz[i] for i in indices)
        for indices in solid.indexed_triangle_faces
    )
    # Solved independent relief metadata must survive the preview toggle.
    # The V-specific preview keys below always override release status.
    inherited_meta=dict(
        getattr(resolved_render_data,"metadata",{}) or {}
    ) if resolved_render_data is not None else dict(base.metadata or {})
    return PartRenderData(
        scene=flat.result_scene,
        material=solid.source_material_with_holes,
        fold_guides=fold_guides_from_final_scene(flat.result_scene),
        metadata={
            **inherited_meta,
            "tail_lower_v_independent_relief_replayed":flat is not unmodified_v_source,
            "tail_lower_v_independent_relief_source_count":(
                len(preserved_relief)+(1 if flat is not unmodified_v_source else 0)
            ),
            "source":"WHD_ACTUAL_FACTORY_CUTTING_AND_FINITE_BEND",
            "tail_lower_v_choice":"v90",
            "tail_lower_v_preview_only":True,
            "tail_lower_v_full_t_mesh":formed,
            "tail_lower_v_physical_t":float(spec.thickness),
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
        raise GeometryError("V_MITER_LOWER_GUI_PREVIEW_T_MESH_MISSING")
    return rows


def reject_tail_lower_v_preview_for_dxf(render_data):
    if (getattr(render_data,"metadata",{}) or {}).get("tail_lower_v_preview_only"):
        raise ValueError("V 型下方左右截角尚未核准加工 DXF；只能預覽 2D／3D")
