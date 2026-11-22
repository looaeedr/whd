# -*- coding: utf-8 -*-
"""#3317 illustrated Vault Tail V geometry, 2D SOURCE CHECK only.

The user's November 22 corrected reference establishes TWO 90-degree side
openings with tips at the actual perpendicular BEND stations, and a fully
retained 48 mm bottom lip. Its W500/D150/T2/FW25 and 15/15/16/48 dimensions
are EXPLICIT SAMPLE values. The drawing visually bisects each 90-degree V;
for this sample only, the outer side endpoints are (0,33),(0,63) and their
right-side reflection. Do not generalize these coordinates to another job.

This authorizes an exactly sourced FLAT CUTTING CHECK; it does not prove
that two physical T cut walls meet after folding, nor authorize machining.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .contracts import EndCapPartSpec, PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_factory_mother_check import (
    _factory_original_shape, _selected_original_corner_component,
)
from .v_miter_operator_gui_check import _physical_corner_bends


@dataclass(frozen=True)
class TailIllustratedSideV90Flat:
    source_spec: EndCapPartSpec
    original_scene: DrawingScene
    result_scene: DrawingScene
    original_factory_material: Polygon
    result_material: Polygon
    original_factory_restored_mother: Polygon
    cut_wedges: tuple
    opening_source_points_xy: tuple
    status: str = "USER_ILLUSTRATED_2D_V90_VERIFIED_FOLDED_FIT_NOT_VERIFIED"
    manufacturing_approved: bool = False


def project_tail_illustrated_side_v90_flat(
    spec: EndCapPartSpec, render: PartRenderData,
) -> TailIllustratedSideV90Flat:
    """One very specific confirmed image -> true Factory source CUTTING.

    Keep ALL original hole/mark/BEND primitive objects unchanged; replace
    exactly one structural exterior CUTTING. Never invent a BEND to the apex.
    """
    if (not isinstance(spec,EndCapPartSpec) or not spec.is_tail
            or not isinstance(render,PartRenderData)
            or not isinstance(render.scene,DrawingScene)):
        raise GeometryError("TAIL_IMAGE_V90_REAL_FACTORY_TAIL_REQUIRED")
    if spec.corner_policy is not None or spec.model_name not in ("金庫型", "VAULT"):
        raise GeometryError("TAIL_IMAGE_V90_VAULT_INTRINSIC_ONLY")
    required=(
        ("width",500.0),("depth",150.0),("thickness",2.0),
        ("frame_width",25.0),("fold_left",15.0),
        ("fold_right",15.0),("fold_top",16.0),("fold_bottom",48.0),
    )
    tol=float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    if any(
        getattr(spec,key) is None or
        not math.isclose(float(getattr(spec,key)),target,rel_tol=0,abs_tol=tol)
        for key,target in required
    ):
        raise GeometryError("TAIL_IMAGE_V90_EXAMPLE_DIMENSIONS_MISMATCH")
    # Vault includes three legitimate CUTTING circles and one rectangular
    # CUTTING hole. The generic single-contour V trial helper rejects them:
    # never discard these source features just to satisfy a preview helper.
    factory,width,height,_=_factory_original_shape(spec)
    outer=tuple(
        p for p in render.scene.primitives
        if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"
        and p.closed and len(p.points)>=3
        and abs(Polygon([(q.x,q.y) for q in p.points])
                .symmetric_difference(factory).area)<=tol
    )
    if (abs(width-522)>tol or abs(height-233)>tol or len(outer)!=1):
        raise GeometryError("TAIL_IMAGE_V90_FACTORY_SOURCE_DIFFERENT")
    original=Polygon([(p.x,p.y) for p in outer[0].points])
    if factory.symmetric_difference(original).area>tol:
        raise GeometryError("TAIL_IMAGE_V90_FACTORY_OUTER_CHANGED")
    mother=box(0,0,width,height)
    old_cuts=tuple(_selected_original_corner_component(
        original,mother,key
    ) for key in ("bottom_left","bottom_right"))
    restored=original.union(unary_union(old_cuts))
    if restored.geom_type!="Polygon" or not restored.is_valid:
        raise GeometryError("TAIL_IMAGE_V90_RESTORED_FACTORY_INVALID")
    openings=[]
    wedges=[]
    for key in ("bottom_left","bottom_right"):
        real=_physical_corner_bends(render.scene,original,key)
        # Fold stations, not physical guide ENDPOINTS: the original
        # side BEND begins at y=49 and bottom BEND at x=16/506.
        vertical,horizontal=real[:2]
        apex=(float(vertical.p1.x),float(horizontal.p1.y))
        side_x=0.0 if key=="bottom_left" else width
        if (abs(apex[1]-48)>tol or
                abs(apex[0]-(15 if key=="bottom_left" else width-15))>tol):
            raise GeometryError("TAIL_IMAGE_V90_REAL_APEX_CHANGED")
        delta=abs(side_x-apex[0])
        low=(side_x,apex[1]-delta)
        high=(side_x,apex[1]+delta)
        u=(low[0]-apex[0],low[1]-apex[1])
        v=(high[0]-apex[0],high[1]-apex[1])
        if (abs(u[0]*v[0]+u[1]*v[1])>tol or
                not math.isclose(delta,15.0,abs_tol=tol)):
            raise GeometryError("TAIL_IMAGE_V90_ANGLE_NOT_90")
        wedge=Polygon((low,apex,high))
        if not wedge.is_valid or wedge.area<=tol or wedge.difference(restored).area>tol:
            raise GeometryError("TAIL_IMAGE_V90_OPENING_OUTSIDE_SOURCE")
        openings.append((key,low,apex,high))
        wedges.append(wedge)
    corrected=restored.difference(unary_union(wedges))
    if (corrected.geom_type!="Polygon" or corrected.interiors or
            not corrected.is_valid or corrected.is_empty or
            corrected.difference(mother).area>tol):
        raise GeometryError("TAIL_IMAGE_V90_NOT_ONE_CONTINUOUS_BLANK")
    allowed=unary_union((*old_cuts,*wedges))
    if original.symmetric_difference(corrected).difference(
        allowed.buffer(tol)
    ).area>tol:
        raise GeometryError("TAIL_IMAGE_V90_UNRELATED_FACTORY_GEOMETRY_CHANGED")
    originals=tuple(
        p for p in render.scene.primitives
        if (isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"
            and p.closed
            and abs(Polygon([(q.x,q.y) for q in p.points])
                    .symmetric_difference(original).area)<=tol)
    )
    if len(originals)!=1:
        raise GeometryError("TAIL_IMAGE_V90_OUTER_CUTTING_NOT_UNIQUE")
    unchanged=tuple(p for p in render.scene.primitives if p is not originals[0])
    result=DrawingScene([
        PolylinePrimitive(
            points=tuple(Vec2(float(x),float(y))
                         for x,y in corrected.exterior.coords[:-1]),
            layer="CUTTING",closed=True,
            semantic_id="OUTER_BOUNDARY",
        ),
        *unchanged,
    ])
    if any(p is not q for p,q in zip(result.primitives[1:],unchanged)):
        raise GeometryError("TAIL_IMAGE_V90_ORIGINAL_FEATURE_IDENTITY_LOST")
    return TailIllustratedSideV90Flat(
        source_spec=spec,original_scene=render.scene,result_scene=result,
        original_factory_material=original,result_material=corrected,
        original_factory_restored_mother=restored,
        cut_wedges=tuple(wedges),opening_source_points_xy=tuple(openings),
    )
