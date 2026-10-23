# -*- coding: utf-8 -*-
"""Actual raster regression: no triangle seam with translucent 3D sheet skin."""
import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pathlib import Path

from phase6_final_scene_mesh_display import gridless_mesh_collection

TRIANGLES = (
    ((0., 0., 0.), (1., 0., 0.), (1., 1., 0.)),
    ((0., 0., 0.), (1., 1., 0.), (0., 1., 0.)),
)


def _render_sheet(opacity):
    fig = Figure(figsize=(4., 4.), facecolor="black")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("black")
    ax.set_axis_off()
    mesh = gridless_mesh_collection(
        TRIANGLES, facecolor="#3884db", opacity=opacity,
    )
    ax.add_collection3d(mesh)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_zlim(-0.1, 0.1)
    ax.view_init(elev=90, azim=-90)
    FigureCanvasAgg(fig).draw()
    return np.asarray(fig.canvas.buffer_rgba())[:, :, :3], mesh


def test_semitransparent_3d_mesh_is_one_color_even_across_diagonal():
    pixels, mesh = _render_sheet(0.55)
    visible = pixels[np.any(pixels != 0, axis=2)]
    colors, counts = np.unique(visible, axis=0, return_counts=True)
    # Old Matplotlib alpha-on-each-triangle produces 198 extra-color pixels
    # at the diagonal with this exact geometry, on Windows Matplotlib 3.11.
    assert len(colors) == 1, (colors, counts)
    assert np.all(np.abs(colors[0].astype(int) - (30, 72, 119)) <= 2)
    assert mesh.get_agg_filter() is not None
    assert len(visible) > 30000


def test_opaque_skins_and_opacity_validation():
    pixels, mesh = _render_sheet(1.0)
    assert mesh.get_agg_filter() is None
    visible = pixels[np.any(pixels != 0, axis=2)]
    assert len(np.unique(visible, axis=0)) == 1
    for opacity in (-0.1, 1.1, float("nan")):
        with pytest.raises(ValueError):
            gridless_mesh_collection(TRIANGLES, facecolor="#3884db", opacity=opacity)


def test_all_final_scene_surface_entrances_composite_before_alpha():
    # The production renderer must not re-introduce an old per-triangle path.
    source = (Path(__file__).resolve().parents[1] / "phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    # The PAD physical-preview skin is a new legitimate surface entrance.
    # Assert composited paths, not an exact number of preview categories.
    assert source.count("gridless_mesh_collection(") >= 6
    assert "pad_artist = gridless_mesh_collection(" in source
    assert "ax.add_collection3d(pad_artist)" in source
    assert "Poly3DCollection(" not in source
    assert "last_formed_ear_display_ids" in source
    for kept in ("_draw_cutting_hole_rims(", "_draw_endcap_cutting_hole_rims(",
                 "_draw_scene_bends(", "_draw_box_body_structure_bends("):
        assert kept in source
