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
    assert len(segments) == len(plotted) == part_count * 3
    assert len({pair for pair in segments}) == len(segments)
    from ae_engine.receiving_fixed_plate_side_contact import EAR_FOLD_HINT_LENGTH_MM
    assert EAR_FOLD_HINT_LENGTH_MM == 20.0
    for index, source in enumerate(formed):
        top, left_hint, right_hint = segments[index * 3:index * 3 + 3]
        a, b = top
        assert a[0] == pytest.approx(b[0])
        assert abs(a[0]) == pytest.approx(398.0)
        assert a[2] == pytest.approx(b[2])
        assert a[2] == pytest.approx(source.parent_base_back_skin_world_z_mm)
        assert abs(a[1] - b[1]) == pytest.approx(256.0)
        for end, hint in ((a, left_hint), (b, right_hint)):
            assert hint[0] == pytest.approx(end)
            assert hint[1][0] == pytest.approx(end[0])
            assert hint[1][1] == pytest.approx(end[1])
            assert end[2] - hint[1][2] == pytest.approx(20.0)
        # No bottom horizontal marking connecting the two short fold hints.
        assert all(
            not (abs(u[2] - (a[2] - 20.0)) < 1e-6
                 and abs(v[2] - (a[2] - 20.0)) < 1e-6)
            for u, v in (top, left_hint, right_hint)
        )
    assert all(kw["color"] == "#facc15" and kw["zorder"] == 30
               for _xyz, kw in plotted)


def test_hidden_box_body_side_does_not_receive_floating_3d_markings():
    renderer, plotted = _renderer()
    formed = _formed(_assembled())
    left = renderer._draw_receiving_ear_side_markings(
        formed, visible_side_piece_keys={"box_body:left_side"}
    )
    assert len(left) == len(plotted) == 3
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
