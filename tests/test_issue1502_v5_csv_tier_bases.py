# -*- coding: utf-8 -*-
"""V5 CSV two NFB tiers: same physical CUTTING algorithm twice, never fake DXF proof."""
from dataclasses import replace
import pytest

from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_live_base_preview import (
    preview_v5_on_existing_receiving_tier_bases,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from tests.test_issue1502_existing_base_nfb_assembly import _snapshot, _upper_base


def _setup(x_first=-100., x_second=100.):
    snap = _snapshot()
    snap["receiving_inner_door_layer_heights_mm"] = [330, 830]
    holes = (
        NfbV5ConfiguredInnerDoorHole(
            "nfb:csv:top", "士林", "nfbv5:士林:2P400",
            x_first, layer_count=2, slot_index=0,
        ),
        NfbV5ConfiguredInnerDoorHole(
            "nfb:csv:bottom", "士林", "nfbv5:士林:3P125SN",
            x_second, layer_count=2, slot_index=1,
        ),
    )
    door = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    bases = {
        i: replace(_upper_base("LEFT_FLAT_SIDE"),
                   physical_id=f"base_plate:nfb_layer:{i}")
        for i in range(2)
    }
    return snap, door, holes, bases


def _run(snap, door, holes, bases):
    return preview_v5_on_existing_receiving_tier_bases(
        snap, "upper", door=door, configured_holes=holes, base_specs=bases,
    )


def _screws(result):
    return sorted(
        (p.source_id, round(p.center.x, 6), round(p.center.y, 6))
        for p in result.render_data.scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"
    )


def _structural(result):
    return tuple(
        p for p in result.render_data.scene.primitives
        if isinstance(p, PolylinePrimitive)
        and p.layer == "CUTTING" and p.closed
    )


def test_each_csv_nfb_tier_has_own_real_plate_only_own_four_screws():
    snap, door, holes, bases = _setup()
    result = _run(snap, door, holes, bases)
    assert [x.part_id for x in result] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert [x.hole_ids for x in result] == [
        ("nfb:csv:top",), ("nfb:csv:bottom",),
    ]
    assert [x.render_data.metadata["nfb_v5_tier_slot_index"] for x in result] == [0, 1]
    assert [x.render_data.metadata["nfb_v5_source_models"] for x in result] == [
        (("士林", "2P400"),), (("士林", "3P125SN"),),
    ]
    assert all(len(_screws(x)) == 4 and len(_structural(x)) == 5
               for x in result)
    assert all(not x.manufacturing_ready for x in result)
    assert all(x.render_data.metadata["nfb_trial_export_approved"] is False
               and x.render_data.metadata["nfb_base_mfg2_release_approved"] is False
               for x in result)


def test_shifting_one_csv_nfb_only_moves_its_own_screw_cutting():
    snap, door, holes, bases = _setup()
    first = _run(snap, door, holes, bases)
    shifted_snap, shifted_door, shifted_holes, shifted_bases = _setup(-65., 100.)
    shifted = _run(shifted_snap, shifted_door, shifted_holes, shifted_bases)
    for a,b in zip(_screws(first[0]), _screws(shifted[0])):
        assert a[0] == b[0]
        assert b[1]-a[1] == pytest.approx(35.)
        assert b[2] == pytest.approx(a[2])
    assert _screws(first[1]) == _screws(shifted[1])
    assert [_structural(v) for v in first] == [_structural(v) for v in shifted]


def test_wrong_tier_identity_and_missing_tier_cannot_create_preview():
    snap, door, holes, specs = _setup()
    wrong = dict(specs)
    wrong[1] = replace(specs[1], physical_id="base_plate:nfb_layer:0")
    with pytest.raises(ValueError, match="不是本層原始"):
        _run(snap, door, holes, wrong)
    with pytest.raises(ValueError, match="集合與已有開關"):
        _run(snap, door, holes, {0: specs[0]})


def test_door_full_proof_cannot_be_reused_after_other_tier_changes():
    snap, door, holes, specs = _setup()
    changed = (holes[0], replace(holes[1], world_x_mm=125.))
    with pytest.raises(ValueError, match="已驗證孔位與目前裝配座標不一致"):
        _run(snap, door, changed, specs)


def test_single_csv_tier_uses_identical_real_base_algorithm_and_fixed_ears():
    snap = _snapshot()
    holes = (
        NfbV5ConfiguredInnerDoorHole(
            "nfb:csv:single", "士林", "nfbv5:士林:2P400",
            35., layer_count=1, slot_index=0,
        ),
    )
    door = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    base = replace(_upper_base("LEFT_FLAT_SIDE"),
                   physical_id="base_plate:nfb_layer:0")
    result = preview_v5_on_existing_receiving_tier_bases(
        snap, "upper", door=door, configured_holes=holes,
        base_specs={0: base},
    )
    assert len(result) == 1
    assert result[0].part_id == "base_plate:nfb_layer:0"
    assert result[0].hole_ids == ("nfb:csv:single",)
    assert result[0].render_data.metadata["nfb_v5_tier_slot_index"] == 0
    assert len(_screws(result[0])) == 4
    assert len(_structural(result[0])) == 5
    assert result[0].manufacturing_ready is False


def test_single_csv_tier_cannot_consume_wrong_actual_plate():
    snap = _snapshot()
    holes = (
        NfbV5ConfiguredInnerDoorHole(
            "nfb:csv:single", "士林", "nfbv5:士林:2P400",
            0., layer_count=1, slot_index=0,
        ),
    )
    door = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    incorrect = replace(_upper_base("LEFT_FLAT_SIDE"),
                        physical_id="base_plate:nfb_layer:1")
    with pytest.raises(ValueError, match="不是本層原始"):
        preview_v5_on_existing_receiving_tier_bases(
            snap, "upper", door=door, configured_holes=holes,
            base_specs={0: incorrect},
        )


def test_all_csv_tiers_share_exact_door_source_sha_and_reject_stale_door():
    snap, door, holes, specs = _setup()
    normal = _run(snap, door, holes, specs)
    expected = door.render_data.metadata["nfb_v5_source_csv_sha256"]
    assert expected and len(expected[0][1]) == 64
    assert all(x.render_data.metadata["nfb_v5_source_csv_sha256"] == expected
               for x in normal)
    wrong_source = replace(
        door.render_data,
        metadata={
            **door.render_data.metadata,
            "nfb_v5_source_csv_sha256": (("士林", "0" * 64),),
        },
    )
    with pytest.raises(ValueError, match="來源版本不同"):
        _run(snap, replace(door, render_data=wrong_source), holes, specs)
