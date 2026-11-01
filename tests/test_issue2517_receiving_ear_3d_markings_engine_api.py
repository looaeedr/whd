"""#2517 Receiving EAR assembled SIDE positioning is Engine-owned.

The three world lines are DISPLAY ONLY, never approved side UV/DXF MARKING.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api, project_receiving_ear_side_marking_segments
from ae_engine.receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from ae_engine.receiving_fixed_plate_side_contact import (
    derive_receiving_ear_side_contact_from_formed_skin,
    receiving_ear_positioning_world_segments,
)
from ae_engine.receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _actual_rows(snapshot):
    return tuple(
        build_receiving_formed_fixing_plate_skins(snapshot, owner.ear_id)
        for owner in resolve_receiving_tier_ear_mating_xy(snapshot)
    )


@pytest.mark.parametrize("factory,count", ((_assembled, 2), (_two_tier, 4)))
def test_headless_public_api_preserves_actual_source_world_segments(factory, count):
    rows = _actual_rows(factory())
    assert len(rows) == count
    expected = tuple(
        segment
        for formed in rows
        for segment in receiving_ear_positioning_world_segments(
            derive_receiving_ear_side_contact_from_formed_skin(formed)
        )
    )
    before = repr(rows)
    result = manufacturing_api.project_receiving_ear_side_marking_segments(rows)
    assert result == expected
    assert len(result) == count * 3
    assert len(set(result)) == count * 3
    assert repr(rows) == before
    assert project_receiving_ear_side_marking_segments is (
        manufacturing_api.project_receiving_ear_side_marking_segments
    )
    assert all(len(a) == len(b) == 3 for a, b in result)


def test_visible_physical_side_selection_and_hidden_empty_output():
    rows = _actual_rows(_two_tier())
    for side in ("left", "right"):
        target = f"box_body:{side}_side"
        result = project_receiving_ear_side_marking_segments(
            rows, visible_side_piece_keys={target},
        )
        assert len(result) == 6  # Two tiers, three segments per EAR.
        expected_x = -398.0 if side == "left" else 398.0
        assert all(a[0] == b[0] == pytest.approx(expected_x) for a, b in result)
    assert project_receiving_ear_side_marking_segments(
        rows, visible_side_piece_keys=(),
    ) == ()
    assert project_receiving_ear_side_marking_segments(()) == ()


def test_invalid_owner_cardinality_duplicate_and_unverified_source_fail_closed():
    left, right = _actual_rows(_assembled())
    for bad, error in (
        ((left,), "EAR_ASSEMBLY_MARKING_SOURCE_OWNER_COUNT_INVALID"),
        ((left, left), "EAR_ASSEMBLY_MARKING_SOURCE_OWNER_COUNT_INVALID"),
        ((left, right, left), "EAR_ASSEMBLY_MARKING_SOURCE_OWNER_COUNT_INVALID"),
        ((replace(left, source_bend_verified=False), right),
         "EAR_SIDE_CONTACT_SOURCE_FORMING_NOT_VERIFIED"),
    ):
        with pytest.raises(ValueError, match=error):
            project_receiving_ear_side_marking_segments(bad)
    # Filtering a hidden side must not grant permission to skip source validation.
    with pytest.raises(ValueError, match="EAR_SIDE_CONTACT_SOURCE_FORMING_NOT_VERIFIED"):
        project_receiving_ear_side_marking_segments(
            (left, replace(right, manufacturing_ready=True)),
            visible_side_piece_keys={"box_body:left_side"},
        )


def test_gui_only_displays_public_engine_result(monkeypatch):
    expected = (((1., 2., 3.), (4., 5., 6.)),)
    calls = []
    def fake_engine(skins, *, visible_side_piece_keys=None):
        calls.append((skins, visible_side_piece_keys))
        return expected

    monkeypatch.setattr(
        manufacturing_api, "project_receiving_ear_side_marking_segments",
        fake_engine,
    )
    plotted = []
    axis = SimpleNamespace(plot=lambda *args, **kwargs: plotted.append((args, kwargs)))
    renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=axis))
    assert renderer._draw_receiving_ear_side_markings(
        ("source",), visible_side_piece_keys={"box_body:left_side"},
    ) == expected
    assert calls == [(("source",), {"box_body:left_side"})]
    assert len(plotted) == 1
    assert plotted[0][1]["zorder"] == 30
    source = inspect.getsource(
        Phase6FinalSceneRenderer._draw_receiving_ear_side_markings,
    )
    assert "manufacturing_api.project_receiving_ear_side_marking_segments(" in source
    assert "derive_receiving_ear_side_contact_from_formed_skin" not in source
    assert "receiving_ear_positioning_world_segments" not in source
    assert "row.part_id" not in source
