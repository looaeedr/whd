# -*- coding: utf-8 -*-
"""Gridless 3D sheet skin: composite a part before applying transparency.

Matplotlib draws triangles of a translucent Poly3DCollection separately. Its
rasterizer leaves visible diagonal seams even with edgecolor='none' and
antialiaseds=False. The defect is in presentation, not manufacturing meshes.
"""
from __future__ import annotations

import math
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def gridless_mesh_collection(triangles, *, facecolor, opacity: float):
    """Shaded physical faces, with one composited alpha mask per part.

    Render each triangle opaque into an offscreen artist filter; then apply
    the requested part transparency to the *whole* raster. This removes
    interior triangle seams without changing holes, skin geometry, BEND or
    MARKING, or turning a translucent panel permanently opaque.

    In Matplotlib Agg, an agg-filter alpha is applied in two compositing
    stages. sqrt(opacity) restores the operator-requested net opacity.
    """
    target = float(opacity)
    if not math.isfinite(target) or not 0.0 <= target <= 1.0:
        raise ValueError("3D sheet opacity must be finite and between 0 and 1")
    artist = Poly3DCollection(
        triangles,
        facecolor=facecolor,
        edgecolor="none",
        linewidths=0.0,
        antialiaseds=False,
        alpha=1.0,
    )
    if target < 1.0:
        composite_alpha = math.sqrt(target)

        def composite_whole_part(image, _dpi):
            pixels = image.copy()
            pixels[..., 3] *= composite_alpha
            return pixels, 0, 0

        artist.set_agg_filter(composite_whole_part)
    return artist
