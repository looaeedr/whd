# -*- coding: utf-8 -*-
"""Receiving EAR display MARKING: one physical contact, same source as 2D UV."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _formed(snapshot):
    adapter = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_ear_display_cache = None
    adapter.last_formed_ear_display_blocker = None
    return adapter._formed_ear_assembly_preview(
        snapshot, {"base_plate", "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"}
    )


def _renderer():
    plotted = []
    axis = SimpleNamespace(plot=lambda *args, **kw: plotted.append((args, kw)))
    return Phase6FinalSceneRenderer(SimpleNamespace(ax3d=axis)), plotted


@pytest.mark.parametrize("factory,part_count", ((_assembled, 2), (_two_tier, 4)))
def test_assembly_3d_marking_follows_source_formed_contact_without_mesh_edges(factory, part_count):
    formed = _formed(factory())
    renderer, plotted = _renderer()
    segments = renderer._draw_receiving_ear_side_markings(formed)
    assert len(formed) == part_count
    assert len(segments) == len(plotted) == part_count
    assert len({pair for pair in segments}) == len(segments)
    for a, b in segments:
        assert a[0] == pytest.approx(b[0])
        assert abs(a[0]) == pytest.approx(398.0)
        # Installed top line is exactly the owning Base Plate's lower Z.
        assert a[2] == pytest.approx(b[2])
        assert abs(a[1]-b[1]) == pytest.approx(256.)
    for (a, b), source in zip(segments, formed):
        assert a[2] == pytest.approx(source.parent_base_back_skin_world_z_mm)
    assert all(kw["color"] == "#facc15" and kw["zorder"] == 30
               for _xyz, kw in plotted)
    # One true installation line, not four sides of a bend-length rectangle.
    assert len({tuple(round(v, 4) for v in p) for a,b in segments for p in (a,b)}) == part_count * 2


def test_hidden_box_body_side_does_not_receive_floating_3d_markings():
    renderer, plotted = _renderer()
    formed = _formed(_assembled())
    left = renderer._draw_receiving_ear_side_markings(
        formed, visible_side_piece_keys={"box_body:left_side"}
    )
    assert len(left) == len(plotted) == 1
    assert all(a[0] == pytest.approx(-398.) for a, b in left)
    renderer2, plotted2 = _renderer()
    assert renderer2._draw_receiving_ear_side_markings(
        formed, visible_side_piece_keys=(),
    ) == ()
    assert plotted2 == []


def test_invalid_source_bend_is_rejected_not_drawn_as_certified_mark():
    renderer, plotted = _renderer()
    formed = _formed(_assembled())
    with pytest.raises(ValueError, match="EAR_SIDE_CONTACT_SOURCE_FORMING_NOT_VERIFIED"):
        renderer._draw_receiving_ear_side_markings(
            (replace(formed[0], source_bend_verified=False), formed[1])
        )
    assert plotted == []
