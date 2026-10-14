# -*- coding: utf-8 -*-
"""Assembly-only presentation: divider visibility and source-traceable dimensions."""
from __future__ import annotations

from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import pytest

from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot
from phase6_final_scene_contracts import AssemblySceneRenderData, FinalSceneViewRequest
from phase6_final_scene_projection import (
    _phase6_assembly_part_presentation,
    _phase6_assembly_physical_dimension_lines,
)
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from whd_theme import WHD_THEME


def test_divider_contrast_uses_shared_theme_and_is_independent_of_body_alpha():
    assert _phase6_assembly_part_presentation("head", .13) is None
    assert _phase6_assembly_part_presentation("box_body:left_side", .13) is None
    for alpha in (0.05, .35, .85, 1.0):
        assert _phase6_assembly_part_presentation("box_body:divider:abc", alpha) == (
            WHD_THEME["divider_face"], WHD_THEME["divider_edge"], 1.0
        )


def test_source_dimensions_expose_each_formed_leg_and_divider_without_guessing():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    _source, divider = _divider_part(snapshot)
    body_lines = _phase6_assembly_physical_dimension_lines(body, thickness=snapshot["t"])
    divider_lines = _phase6_assembly_physical_dimension_lines(divider, thickness=snapshot["t"])
    assert "24 / 24 / 29 / 350 / 18" in body_lines[0]
    assert "18 / 350 / 29 / 18" in body_lines[1]
    assert "展開外框 158 × 796 mm" in divider_lines[0]
    assert "FW包外 29" in divider_lines[0]
    assert "核心包外 106" in divider_lines[0]
    assert all("包外" in line for line in body_lines)
    assert body.render_data.pieces[0].fold_profile[0].length == pytest.approx(22)
    assert divider.render_data.material.bounds == pytest.approx((0, 0, 158, 796))


def test_real_assembly_renderer_draws_opaque_divider_with_legible_dimensions():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    _source, divider = _divider_part(snapshot)
    fig = Figure(figsize=(12, 8), dpi=80)
    ax = fig.add_subplot(111, projection="3d")
    try:
        renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
        triangles = renderer.render(FinalSceneViewRequest(
            render_data=AssemblySceneRenderData(assembly_parts=(body, divider)),
            x_profile=(), y_profile=(), part_key="assembly",
            finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
            thickness=snapshot["t"], alpha_bend=.45,
        ))
        assert triangles
        texts = "\n".join(text.get_text() for text in ax.texts)
        assert "左側板：折後各段包外 24 / 24 / 29 / 350 / 18" in texts
        assert "中隔：展開外框 158 × 796 mm" in texts
        collections = [col for col in ax.collections if hasattr(col, "get_facecolor")]
        assert len(collections) >= 4
        alphas = [col.get_alpha() for col in collections if col.get_alpha() is not None]
        assert alphas.count(1.0) >= 1
        assert alphas.count(.17) >= 1
        assert not ax.axison, '3D grid/axes should not obscure physical divider'
        anchored = [t for t in ax.texts if t.get_text().startswith('中隔\n')]
        assert len(anchored) == 1
        assert '展開外框 158 × 796 mm' in anchored[0].get_text()
    finally:
        fig.clear()
