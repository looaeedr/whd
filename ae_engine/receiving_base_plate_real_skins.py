# -*- coding: utf-8 -*-
"""Actual Receiving Base Plate core physical skins from its own FinalScene.

The assembly position must align the real outward NFB mounting *skin* with the
inner-door's source-verified physical skin.  It must never use the stock return
length, unfolded outline, or whole folded-envelope centre as the contact face.
"""
from __future__ import annotations

from functools import lru_cache
from math import isfinite


@lru_cache(maxsize=32)
def _source_base_local_nfb_skins(
    w, height, thickness, shrink_top, shrink_bottom, shrink_left,
    shrink_right, bend, pattern, depth_pair,
):
    """Return actual locally centered FRONT skin Z of deep/shallow NFB webs.

    Cache key consists ONLY of immutable manufacturing source dimensions and
    selected NFB depth pair; editing any dimension recomputes the FinalScene.
    No live project/global mutable state is stored in this cache.
    """
    from .contracts import BasePlatePartSpec
    from .manufacturing_api import build_part_render_data
    from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
    from .assembly_geometry import folded_mesh_with_flat_uv_from_polygon, world_skin_with_flat_uv
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
    spec = BasePlatePartSpec(
        width=w, height=height, thickness=thickness,
        shrink_top=shrink_top, shrink_bottom=shrink_bottom,
        shrink_left=shrink_left, shrink_right=shrink_right,
        bend=bend, model_name="受電箱", receiving_bend_pattern=pattern,
        receiving_nfb_depth_pair_mm=depth_pair, physical_id="base_plate",
    )
    render = build_part_render_data(spec)
    physical = {
        "h":height, "base_plate_shrink_top":shrink_top,
        "base_plate_shrink_bottom":shrink_bottom,
        "base_plate_shrink_left":shrink_left,
        "base_plate_shrink_right":shrink_right,
        "base_plate_bend":bend, "receiving_bend_pattern":pattern,
        "receiving_nfb_depth_pair_mm":depth_pair,
    }
    profiles = receiving_base_plate_3d_profiles(
        {"w":w,"t":thickness}, physical,
    )
    mapped = folded_mesh_with_flat_uv_from_polygon(
        render.material, profiles["X"], profiles["Y"],
        fold_guides=render.fold_guides,
    )
    if not mapped:
        raise ValueError("RECEIVING_BASE_NO_SOURCE_FOLDED_MESH")
    skins = world_skin_with_flat_uv(
        mapped, "base_plate", (w, height, 350.0),
        sheet_thickness=thickness,
    )
    if not skins:
        raise ValueError("RECEIVING_BASE_NO_TRUE_SKINS")
    xbounds = [0.0]
    for row in profiles["X"]:
        xbounds.append(xbounds[-1] + float(row["len"]))
    if pattern == RECEIVING_BASE_PATTERN_CENTER:
        # Inner two source-side BEND stations bound the central NFB web.
        x0, x1 = xbounds[2] + thickness/2.0, xbounds[3] - thickness/2.0
        guides = tuple(g for g in render.fold_guides if g.axis == "x")
        if len(guides) != 4:
            raise ValueError("RECEIVING_BASE_SOURCE_SIDE_GUIDES_MISSING")
        y0=max(float(g.span_start) for g in guides)
        y1=min(float(g.span_end) for g in guides)
    else:
        x0, x1 = 0.0, float(render.unfolded_topology.width)
        y0,y1 = float(bend), float(render.unfolded_topology.height)-float(bend)
    eps=1e-6
    def front_at_region(x_min,x_max):
        eligible = [
            tri for tri in skins
            if all(x_min-eps <= float(p[0]) <= x_max+eps
                   and y0-eps <= float(p[1]) <= y1+eps for p in tri.flat)
        ]
        if not eligible:
            raise ValueError("RECEIVING_BASE_ACTUAL_MOUNTING_FACE_MISSING")
        zs=[float(vertex[2]) for tri in eligible for vertex in tri.world]
        if not all(isfinite(z) for z in zs):
            raise ValueError("RECEIVING_BASE_NONFINITE_WORLD_SKIN")
        # All physical NFB web triangles selected here must lie on exactly
        # two parallel T-separated skins; not a sloped or incomplete fold.
        if abs((max(zs)-min(zs))-thickness)>eps:
            raise ValueError("RECEIVING_BASE_MOUNTING_FACE_NOT_PLANAR")
        return max(zs)
    deep_front = front_at_region(x0,x1)
    shallow_front = None
    if pattern == RECEIVING_BASE_PATTERN_CENTER and depth_pair is not None:
        left=front_at_region(xbounds[0],xbounds[1])
        right=front_at_region(xbounds[4],xbounds[5])
        if abs(left-right)>eps:
            raise ValueError("RECEIVING_BASE_SHALLOW_FACES_NOT_COPLANAR")
        shallow_front = left
        expected=float(depth_pair[0])-float(depth_pair[1])
        if abs((shallow_front-deep_front)-expected)>eps:
            raise ValueError("RECEIVING_BASE_FOLDED_NFB_FACE_DEPTH_PARITY_FAILED")
    return deep_front,shallow_front


def receiving_base_actual_local_nfb_skins(snapshot, physical):
    """Read the exact physical configured Base Plate source and cached true skin."""
    pair=physical.get("receiving_nfb_depth_pair_mm")
    if pair is not None:
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(float(x))
                       for x in pair)):
            raise ValueError("RECEIVING_BASE_INVALID_NFB_DEPTH_PAIR")
        pair=tuple(float(x) for x in pair)
    numeric_values = (
        snapshot["w"], physical["h"], snapshot["t"],
        physical["base_plate_shrink_top"],
        physical["base_plate_shrink_bottom"],
        physical["base_plate_shrink_left"],
        physical["base_plate_shrink_right"],
        physical["base_plate_bend"],
    )
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(float(v))
        for v in numeric_values
    ):
        raise ValueError("RECEIVING_BASE_NONFINITE_SOURCE_DIMENSIONS")
    return _source_base_local_nfb_skins(
        float(snapshot["w"]),float(physical["h"]),float(snapshot["t"]),
        float(physical["base_plate_shrink_top"]),
        float(physical["base_plate_shrink_bottom"]),
        float(physical["base_plate_shrink_left"]),
        float(physical["base_plate_shrink_right"]),
        float(physical["base_plate_bend"]),
        str(physical["receiving_bend_pattern"]),pair,
    )
