# -*- coding: utf-8 -*-
"""#3317: REAL original WHD Tail CUTTING/BEND vs HISTORICAL symmetric V (2D).

No 3D, R/BA seam numbers, fabricated V opening, factory CUTTING change or
machining authority. The two required SAME-SIDE asymmetric rays have NOT
been sourced from user-confirmed geometry and must remain UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from .contracts import EndCapPartSpec, PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_factory_mother_check import (
    _factory_original_shape, _selected_original_corner_component,
)
from .v_miter_material_trial import _single_source_material
from .v_miter_operator_gui_check import _physical_corner_bends


@dataclass(frozen=True)
class TailCornerFlatSourceAudit:
    corner: str
    nominal_apex: Vec2
    outer_side_x_mm: float
    real_side_bend_xy: tuple
    real_bottom_bend_xy: tuple
    actual_factory_removed_corner: Polygon
    historical_symmetric_removed_wedge: Polygon
    historical_low_outer: Vec2
    historical_high_outer: Vec2
    historical_added_vs_factory: object
    historical_removed_vs_factory: object
    confirmed_low_outer_y_mm: None = None
    confirmed_high_outer_y_mm: None = None
    confirmed_source_cut_legs_xy: None = None
    status: str = "UNCONFIRMED_TWO_ANGLED_RAYS_SOURCE_GEOMETRY_REQUIRED"


@dataclass(frozen=True)
class TailFlatSourceAudit:
    original_scene: DrawingScene
    original_factory_cutting: Polygon
    original_factory_mother: Polygon
    historical_symmetric_cutting: Polygon
    original_factory_bend_rows: tuple
    original_scene_primitives: tuple
    corner_rows: tuple[TailCornerFlatSourceAudit, TailCornerFlatSourceAudit]
    spec_identity: tuple
    numerical_geometry_tolerance_mm: float
    source_proof_status: str = "FACTORY_FINALSCENE_ORIGINAL_MATCH"
    candidate_geometry_status: str = "NOT_DETERMINED_NOT_AUTHORIZED_FOR_3D_OR_DXF"


def _original_line_endpoints(bend):
    return (
        (float(bend.p1.x), float(bend.p1.y)),
        (float(bend.p2.x), float(bend.p2.y)),
    )


def project_tail_original_flat_source_audit(
    spec: EndCapPartSpec, render: PartRenderData,
) -> TailFlatSourceAudit:
    """Rebuild the ACTUAL Tail Factory, compare CUTTING, show old V as OLD.

    Only the nominal apex and two same-side openings are confirmed by the
    CURRENT 07 V definition; the opening Ys/leg slopes are not specified.
    This intentionally does NOT expose any candidate CUTTING polygon.
    """
    if (not isinstance(spec, EndCapPartSpec) or not spec.is_tail
            or not isinstance(render, PartRenderData)
            or not isinstance(render.scene, DrawingScene)):
        raise GeometryError("V_MITER_TAIL_FLAT_AUDIT_REAL_TAIL_REQUIRED")
    tol=float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    original=_single_source_material(render.scene)
    factory,width,height,unused_mother_bends=_factory_original_shape(spec)
    if original.symmetric_difference(factory).area > tol:
        raise GeometryError("V_MITER_TAIL_FLAT_FACTORY_FINALSCENE_MISMATCH")
    xmin,ymin,xmax,ymax=map(float,original.bounds)
    if (not math.isclose(xmin,0.0,abs_tol=tol)
            or not math.isclose(ymin,0.0,abs_tol=tol)
            or not math.isclose(xmax,width,abs_tol=tol)
            or not math.isclose(ymax,height,abs_tol=tol)):
        raise GeometryError("V_MITER_TAIL_FLAT_FACTORY_DIMENSION_MISMATCH")
    outer_cutting=tuple(
        p for p in render.scene.primitives
        if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING" and p.closed
    )
    if len(outer_cutting)!=1:
        raise GeometryError("V_MITER_TAIL_FLAT_OUTER_CUTTING_AMBIGUOUS")
    mother=box(0,0,width,height)
    existing_cuts={
        key:_selected_original_corner_component(original,mother,key)
        for key in ("bottom_left","bottom_right")
    }
    restored=original.union(unary_union(tuple(existing_cuts.values())))
    if (restored.geom_type!="Polygon" or not restored.is_valid
            or restored.interiors
            or abs(restored.area-original.area-
                   sum(v.area for v in existing_cuts.values()))>tol):
        raise GeometryError("V_MITER_TAIL_FLAT_FACTORY_CORNER_RESTORE_UNVERIFIED")
    historical_wedges={}
    bends=[]
    rows=[]
    for key in ("bottom_left","bottom_right"):
        vertical,horizontal,side_reach,bottom_reach,side_tip_gap,bottom_tip_gap,real_x,real_y=(
            _physical_corner_bends(render.scene,original,key)
        )
        apex=Vec2(float(vertical.p1.x),float(horizontal.p1.y))
        if (abs(apex.x-horizontal.p1.x)>tol
                or abs(apex.y-vertical.p1.y)>tol):
            raise GeometryError("V_MITER_TAIL_FLAT_APEX_SOURCE_DISAGREES")
        sx=xmin if key.endswith("left") else xmax
        dx=abs(sx-apex.x)
        if dx<=tol:
            raise GeometryError("V_MITER_TAIL_FLAT_SIDE_FLANGE_MISSING")
        # These are the HISTORICAL branch's unsupported +/-45 degree
        # output, not the approved V geometry or a new candidate.
        low=Vec2(sx,apex.y-dx)
        high=Vec2(sx,apex.y+dx)
        legacy=Polygon(((apex.x,apex.y),(low.x,low.y),(high.x,high.y)))
        if (not legacy.is_valid or legacy.area<=tol
                or legacy.difference(restored).area>tol):
            raise GeometryError("V_MITER_TAIL_FLAT_OLD_GUESS_NOT_REPRODUCIBLE")
        historical_wedges[key]=legacy
        bends.append((key,"side",_original_line_endpoints(real_x)))
        bends.append((key,"bottom",_original_line_endpoints(real_y)))
        rows.append(TailCornerFlatSourceAudit(
            corner=key,
            nominal_apex=apex,
            outer_side_x_mm=float(sx),
            real_side_bend_xy=_original_line_endpoints(real_x),
            real_bottom_bend_xy=_original_line_endpoints(real_y),
            actual_factory_removed_corner=existing_cuts[key],
            historical_symmetric_removed_wedge=legacy,
            historical_low_outer=low,
            historical_high_outer=high,
            historical_added_vs_factory=existing_cuts[key].difference(legacy),
            historical_removed_vs_factory=legacy.difference(existing_cuts[key]),
        ))
    wedges=unary_union(tuple(historical_wedges.values()))
    historical=restored.difference(wedges)
    if (historical.geom_type!="Polygon" or not historical.is_valid
            or historical.interiors or historical.is_empty
            or historical.difference(mother).area>tol):
        raise GeometryError("V_MITER_TAIL_FLAT_OLD_GUESS_INVALID")
    # The scene has not been mutated, and NO newly guessed candidate
    # contour is constructed or returned in this source audit.
    return TailFlatSourceAudit(
        original_scene=render.scene,
        original_factory_cutting=original,
        original_factory_mother=restored,
        historical_symmetric_cutting=historical,
        original_factory_bend_rows=tuple(bends),
        original_scene_primitives=tuple(render.scene.primitives),
        corner_rows=(rows[0],rows[1]),
        spec_identity=(
            ("part","tail"),("model_name",spec.model_name),
            ("width",float(spec.width)),("depth",float(spec.depth)),
            ("thickness",float(spec.thickness)),
            ("frame_width",float(spec.frame_width)),
            ("fold_left",spec.fold_left),("fold_right",spec.fold_right),
            ("fold_bottom",spec.fold_bottom),
            ("corner_policy_type",type(spec.corner_policy).__name__),
        ),
        numerical_geometry_tolerance_mm=tol,
    )
