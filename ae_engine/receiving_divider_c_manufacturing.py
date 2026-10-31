# -*- coding: utf-8 -*-
"""Real source C single Receiving Divider FinalScene CUTTING/BEND.

The verified original 受電箱/框.dxf C owns all source CUTTING (including
6 round holes and its independent relief square). Receiving's canonical
divider Fold contract owns BEND positions. No cabinet assembly/Joints,
automatic parent Door layout inference, 3D contact or C/A/B/D mixing.
"""
from __future__ import annotations

from pathlib import Path
from math import isfinite

from .door_dividers import BoxBodyDividerPart
from .manufacturing_render_data import (
    PartRenderData, MaterialSegment, UnfoldedBlankTopology,
    material_polygon_from_final_scene, fold_guides_from_final_scene,
)
from .receiving_frame_baseline import receiving_divider_c_source
from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives
from .sheetmetal_geometry import (
    FoldSegment, StripFoldChain, build_strip_bend_segments,
)
from .sheetmetal_part_adapters import StructuralGeometryResult


def build_receiving_divider_c_render_data(
    divider: BoxBodyDividerPart, *, resource_root: Path,
) -> PartRenderData:
    """Render exactly the installed C source and canonical Receiving Fold."""
    if (not isinstance(divider, BoxBodyDividerPart)
            or divider.model_name != "受電箱"
            or divider.axis != "HORIZONTAL"
            or not isinstance(resource_root, Path)
            or resource_root.is_symlink() or not resource_root.is_dir()):
        raise ValueError("RECEIVING_DIVIDER_C_SOURCE_PART_AND_RESOURCE_REQUIRED")
    chain = StripFoldChain(
        segments=tuple(
            FoldSegment(str(seg.phase6_key or f"divider_segment_{i}"), float(seg.length), 0.0)
            for i, seg in enumerate(divider.fold_profile)
        ),
        height=float(divider.span),
    )
    if (len(divider.fold_profile) != 4
            or len(divider.signed_fold_chain) != 4
            or abs(float(chain.total_width)-158.0) > 0.04
            or not isfinite(float(divider.span))
            or divider.span <= 110):
        raise ValueError("RECEIVING_DIVIDER_C_SOURCE_CANONICAL_FOLD_MISMATCH")
    source_path = resource_root / "基準檔" / "受電箱" / "框.dxf"
    outline, original_cutouts, source = receiving_divider_c_source(
        material_width=float(chain.total_width), span=float(divider.span),
        source_path=source_path,
    )
    structural = StructuralGeometryResult(
        outline=outline, bends=tuple(build_strip_bend_segments(chain)),
        width=float(chain.total_width), height=float(chain.height),
        topology=chain,
    )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural))
    scene.extend(original_cutouts)
    topology = UnfoldedBlankTopology(
        piece_id=divider.stable_id,
        x_segments=tuple(
            MaterialSegment(
                "X", str(row.phase6_key or f"segment_{i}"), float(row.length),
                "RECEIVING_DIVIDER_C_SOURCE",
            ) for i, row in enumerate(divider.fold_profile)
        ),
        y_segments=(MaterialSegment(
            "Y", "divider_span", float(divider.span),
            "DOOR_LAYOUT_BOUNDARY_SOURCE_SPAN",
        ),),
        source="RECEIVING_DIVIDER_C_SOURCE", revision=1,
    )
    material = material_polygon_from_final_scene(scene)
    folds = fold_guides_from_final_scene(scene)
    if (material is None or material.is_empty or not material.is_valid
            or material.area <= 0 or not folds):
        raise ValueError("RECEIVING_DIVIDER_C_FINAL_MATERIAL_INVALID")
    return PartRenderData(
        scene=scene, material=material, fold_guides=folds,
        metadata={
            "stable_id": divider.stable_id, "owner": "box_body",
            "model_name": "受電箱", "axis": divider.axis,
            "boundary_key": divider.boundary_key,
            "adjacent_cells": tuple(divider.adjacent_cells),
            "source_cabinet_family": "受電箱",
            "signed_fold_chain": tuple(divider.signed_fold_chain),
            "material_lengths": tuple(divider.material_lengths),
            "physical_geometry_contract": dict(divider.physical_geometry_contract),
            **source,
        },
        unfolded_topology=topology,
    )
