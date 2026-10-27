# -*- coding: utf-8 -*-
"""Evidence from actual Receiving mother-sheet solver, not orphan EAR-only capture."""
import pytest

from ae_engine.manufacturing_scene_access import owner_render_data
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tools.receiving_ear_marking_capture import (
    _prepared, _save_2d, _assembled_parts,
)


@pytest.mark.parametrize("factory,tiers", ((_assembled, 1), (_two_tier, 2)))
def test_source_solved_frame_divider_and_ear_all_in_real_2d_sheets(
    factory, tiers, tmp_path,
):
    snap, resolved, emitted = _prepared(factory)
    assert len(emitted) == 7
    actual_frame = {
        (row.locator_part_id, row.attached_part_id) for row in emitted
    }
    assert ("head", "inner_door:upper:top_frame") in actual_frame
    assert ("box_body:left_side", "inner_door:upper:left_frame") in actual_frame
    assert ("box_body:right_side", "inner_door:upper:right_frame") in actual_frame
    assert sum(row.attached_part_id.startswith("box_body:divider:")
               for row in emitted) == 2

    results = _save_2d(snap, resolved, tiers, tmp_path)
    assert set(results) == {"left_side", "right_side", "head", "divider"}
    for side in ("left_side", "right_side"):
        assert results[side]["joint"] == 2
        assert results[side]["ear"] >= 3 * tiers
    assert results["head"]["joint"] == 1
    assert results["divider"]["joint"] == 2
    assert len(tuple(tmp_path.glob("2d_*.png"))) == 4
    # The display is a copy; all original side CUTTING and source metadata survive.
    body = resolved.part("box_body").render_data
    assert len(tuple(body.pieces)) >= 2
    for side in ("left_side", "right_side"):
        owner = owner_render_data(resolved, "box_body:" + side)
        assert len(owner.metadata.get("joint_markings") or ()) == 2


@pytest.mark.parametrize("factory,tiers", ((_assembled, 1), (_two_tier, 2)))
def test_3d_capture_has_actual_base_for_every_nfb_tier_and_all_frame_owners(
    factory, tiers,
):
    snap, resolved, emitted = _prepared(factory)
    parts = _assembled_parts(snap, resolved, tiers)
    keys = {p.part_key for p in parts}
    assert {"box_body", "head", "inner_door:upper:left_frame",
            "inner_door:upper:right_frame", "inner_door:upper:top_frame"}.issubset(keys)
    assert any(p.part_key.startswith("box_body:divider:") for p in parts)
    bases = {k for k in keys if k == "base_plate" or k.startswith("base_plate:nfb_layer:")}
    assert len(bases) == tiers
    assert all(p.render_data is not None for p in parts)
