# -*- coding: utf-8 -*-
"""#1502 V5 CSV model screw X never moves the real plate or four EAR slots."""
import pytest

from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_live_base_preview import (
    preview_v5_on_existing_receiving_base,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from tests.test_issue1502_existing_base_nfb_assembly import (
    _snapshot, _upper_base,
)

MODEL = "nfbv5:士林:2P400"


def _trial(pattern, positions):
    snap = _snapshot()
    holes = tuple(
        NfbV5ConfiguredInnerDoorHole(
            physical_hole_id=f"nfb:v5:{i}",
            brand="士林", model_ref=MODEL,
            world_x_mm=float(x), layer_count=1, slot_index=0,
        ) for i,x in enumerate(positions)
    )
    door = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    base = preview_v5_on_existing_receiving_base(
        snap, "upper", door=door, configured_holes=holes,
        base_spec=_upper_base(pattern),
    )
    return door, base


def _screws(result):
    return tuple(sorted(
        (p.source_id, round(p.center.x, 6), round(p.center.y, 6), p.radius)
        for p in result.render_data.scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"
    ))


def _structural_cutting(result):
    return tuple(
        p for p in result.render_data.scene.primitives
        if isinstance(p, PolylinePrimitive)
        and p.layer == "CUTTING" and p.closed
    )


@pytest.mark.parametrize("pattern", (
    "LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE",
))
def test_v5_csv_two_nfb_x_shift_changes_only_eight_screws_not_base_ear_mounts(pattern):
    door_before, before = _trial(pattern, (-100., 100.))
    door_after, after = _trial(pattern, (-65., 135.))
    assert len(_screws(before)) == len(_screws(after)) == 8
    for old, new in zip(_screws(before), _screws(after)):
        assert new[0] == old[0]
        assert new[1] - old[1] == pytest.approx(35.)
        assert new[2] == pytest.approx(old[2])
        assert new[3] == pytest.approx(old[3])
    assert _structural_cutting(before) == _structural_cutting(after)
    assert len(_structural_cutting(before)) == 5
    assert before.part_id == after.part_id == "base_plate"
    assert not before.manufacturing_ready and not after.manufacturing_ready
    assert before.render_data.metadata["nfb_base_mfg2_release_approved"] is False
    assert all(p.status == "NFB_V5_PANEL_UV_GEOMETRY_UNVERIFIED"
               for p in before.patterns + after.patterns)
    assert door_before.hole_ids == door_after.hole_ids
    assert door_before.render_data.metadata["nfb_v5_source_csv_sha256"] == (
        before.render_data.metadata["nfb_v5_source_csv_sha256"]
    )
    assert door_after.render_data.metadata["nfb_v5_source_csv_sha256"] == (
        after.render_data.metadata["nfb_v5_source_csv_sha256"]
    )


def test_v5_csv_one_switch_off_center_still_keeps_base_and_ears_fixed():
    _, result = _trial("LEFT_FLAT_SIDE", (100.,))
    assert len(_screws(result)) == 4
    assert len(_structural_cutting(result)) == 5
    assert result.part_id == "base_plate"
    assert result.render_data.metadata["nfb_trial_export_approved"] is False
