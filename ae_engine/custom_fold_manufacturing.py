"""Manufacturing for standalone one-axis folds, through StripFoldChain."""
import math
from collections.abc import Mapping
from .contracts import CustomFoldPartSpec
from .sheetmetal_geometry import FoldSegment, StripFoldChain, Vec2, BendLine, build_strip_outline, build_strip_bend_segments
from .sheetmetal_part_adapters import StructuralGeometryResult
from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives, resolved_features_to_primitives
from .sheetmetal_feature_surface import feature_surface_from_outline, resolve_surface_features, RectGuide
from .sheetmetal_features import legacy_hole_to_feature
from .manufacturing_render_data import PartRenderData, MaterialSegment, UnfoldedBlankTopology, material_polygon_from_final_scene, fold_guides_from_final_scene

def _validate(spec):
    if not isinstance(spec,CustomFoldPartSpec) or spec.fold_axis not in {"X","Y"}:
        raise ValueError("custom Fold axis must be X or Y")
    if not spec.physical_id.startswith("custom:"):
        raise ValueError("custom physical ID is required")
    for value in (spec.thickness,spec.transverse_length):
        if isinstance(value,bool) or not math.isfinite(float(value)) or value<=0:
            raise ValueError("custom thickness/span must be finite and positive")
    rows=spec.fold_profile
    if len(rows)<2 or rows[-1].angle not in (None,0):
        raise ValueError("custom Fold needs a terminal row with no bend")
    for row in rows:
        if not math.isfinite(row.length) or row.length<=0:
            raise ValueError("custom material segment must be finite and positive")
        if row.angle is not None and (not math.isfinite(row.angle) or abs(row.angle)!=90):
            raise ValueError("custom Fold supports explicit 90 degree bends")
    if not any(row.angle in (-90,90) for row in rows[:-1]):
        raise ValueError("custom Fold requires a real bend")

def custom_fold_structural_result(spec):
    _validate(spec)
    chain=StripFoldChain(tuple(FoldSegment(row.phase6_key or f"segment_{i}",row.length)
                             for i,row in enumerate(spec.fold_profile)),spec.transverse_length)
    outline=tuple(build_strip_outline(chain))
    bends=tuple(bend for bend,row in zip(build_strip_bend_segments(chain),spec.fold_profile)
                if row.angle not in (None,0))
    width,height=chain.total_width,chain.height
    if spec.fold_axis=="Y":
        outline=tuple(Vec2(p.y,p.x) for p in outline)
        bends=tuple(BendLine(b.name,Vec2(b.p1.y,b.p1.x),Vec2(b.p2.y,b.p2.x)) for b in bends)
        width,height=height,width
    return StructuralGeometryResult(outline=outline,bends=bends,width=width,height=height,topology=chain)

def custom_fold_feature_context(spec):
    structural=custom_fold_structural_result(spec)
    # Editor coordinates are the authoritative material plane. Guide the
    # semantic core, never derive a fabricated assembly plane from a 3D bbox.
    rows=spec.fold_profile
    core=next((i for i,row in enumerate(rows) if row.core),len(rows)//2)
    start=sum(row.length for row in rows[:core]);end=start+rows[core].length
    guide=RectGuide(Vec2(start,0),Vec2(end,spec.transverse_length),"custom_finished_face") if spec.fold_axis=="X" else RectGuide(Vec2(0,start),Vec2(spec.transverse_length,end),"custom_finished_face")
    return feature_surface_from_outline(spec.physical_id,structural.outline),structural.width,structural.height,guide

def build_custom_fold_render_data(spec):
    structural=custom_fold_structural_result(spec)
    scene=DrawingScene();scene.extend(structural_result_to_primitives(structural))
    surface,width,height,guide=custom_fold_feature_context(spec)
    features=tuple(legacy_hole_to_feature(dict(f)) if isinstance(f,Mapping) else f for f in spec.features)
    scene.extend(resolved_features_to_primitives(resolve_surface_features(surface,features,width,height)))
    folded=tuple(MaterialSegment(spec.fold_axis,row.phase6_key or f"segment_{i}",row.length,"CUSTOM_FOLD_PROFILE") for i,row in enumerate(spec.fold_profile))
    other="Y" if spec.fold_axis=="X" else "X"
    flat=(MaterialSegment(other,"custom_span",spec.transverse_length,"CUSTOM_MANUAL_SPAN"),)
    return PartRenderData(scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        unfolded_topology=UnfoldedBlankTopology(piece_id=spec.physical_id,
            x_segments=folded if spec.fold_axis=="X" else flat,
            y_segments=folded if spec.fold_axis=="Y" else flat,source="CUSTOM_FOLD_PROFILE"),
        metadata={"stable_id":spec.physical_id,"fold_axis":spec.fold_axis,"assembly_placement":"unassigned",
                  "outside_lengths":tuple(row.formed_length if row.formed_length is not None else row.length for row in spec.fold_profile)})
