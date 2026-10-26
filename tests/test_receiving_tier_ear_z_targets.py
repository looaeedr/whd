# -*- coding: utf-8 -*-
"""#1503 installed ear Z target must never become fictitious formed weld proof."""
from copy import deepcopy
import pytest

from ae_engine.assembly_placement import resolve_base_plate_placement
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_tier_ear_z_targets import (
    resolve_receiving_tier_ear_contact_targets,
    resolve_receiving_tier_base_z_targets,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def test_one_tier_source_base_back_skin_is_only_a_target_not_formed_ear():
    snap = _assembled()
    targets = resolve_receiving_tier_ear_contact_targets(snap)
    assert len(targets) == 2
    physical = receiving_base_plate_values(snap)
    front, _ = receiving_base_actual_local_nfb_skins(snap, physical)
    position = resolve_base_plate_placement(snap, "base_plate").world_offset
    target_z = position[2] + front - snap["t"]
    assert [x.ear_id for x in targets] == [
        "base_plate:fixing_plate:left", "base_plate:fixing_plate:right"
    ]
    assert [x.fixing_hole_world_x_mm for x in targets] == [-335.0, 335.0]
    assert [x.side_inside_weld_x_mm for x in targets] == [-398.0, 398.0]
    for row in targets:
        assert row.fixing_hole_world_y_mm == pytest.approx((180.,320.))
        assert row.base_back_skin_world_z_mm == pytest.approx(target_z)
        assert row.target_ear_contact_world_z_mm == pytest.approx(target_z)
        assert row.base_skin_z_source_verified
        assert not row.source_bend_verified
        assert not row.formed_weld_contact_verified
        assert not row.side_plate_marking_export_approved
        assert not row.manufacturing_ready


def test_source_skin_z_tracks_inner_door_inset_not_operator_switch_x():
    before = resolve_receiving_tier_ear_contact_targets(_assembled(offset=80))
    after = resolve_receiving_tier_ear_contact_targets(_assembled(offset=95))
    assert all(
        a.target_ear_contact_world_z_mm - b.target_ear_contact_world_z_mm
        == pytest.approx(15.)
        for a,b in zip(before,after)
    )
    changed = _assembled()
    for hole,x in zip(changed["nfb_config"]["holes"],(-150.,80.)):
        hole.update(
            manual_x_state="CONFIRMED", manual_x_mm=x,
            datum_revision="SOURCE-X-REV1", datum_snapshot={"w":800,"t":2},
        )
    changed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed["nfb_config"]
    )
    assert resolve_receiving_tier_ear_contact_targets(changed) == before


def test_each_tier_uses_identical_real_skin_z_formula_and_own_source_depth():
    rows = resolve_receiving_tier_ear_contact_targets(_two_tier())
    assert len(rows) == 4
    assert [x.parent_base_id for x in rows] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1", "base_plate:nfb_layer:1",
    ]
    assert [x.ear_id for x in rows] == [
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    ]
    assert [x.fixing_hole_world_x_mm for x in rows] == [-335,335,-335,335]
    assert [x.fixing_hole_world_y_mm for x in rows] == [
        (400.,540.),(400.,540.),(-100.,40.),(-100.,40.)
    ]
    depths = resolve_receiving_tier_base_z_targets(_two_tier())
    assert [x.layer_index for x in depths] == [0, 1]
    assert all(x.physical_skin_z_resolved for x in depths)
    assert all(x.world_offset_z_mm is not None for x in depths)
    assert len({x.source_depths_mm for x in depths}) == 2
    assert len({x.world_offset_z_mm for x in depths}) == 2
    assert len({x.target_ear_contact_world_z_mm for x in rows}) == 1
    for row in rows:
        corresponding = depths[row.layer_index]
        assert row.base_back_skin_world_z_mm == pytest.approx(
            corresponding.base_back_skin_world_z_mm
        )
        # Selected 72-mm tier remains a valid Base Plate preview, but it does
        # NOT move the fixed-ear reference away from brand maximum 107 mm.
        assert row.target_ear_contact_world_z_mm == pytest.approx(
            depths[0].base_back_skin_world_z_mm
        )
        # Each tier uses its own CENTER return; both installed support skins
        # now land on the fixed brand maximum Z, not on selected-model Z.
        assert row.base_skin_z_source_verified
        assert not row.source_bend_verified
        assert not row.formed_weld_contact_verified
        assert not row.side_plate_marking_export_approved
        assert not row.manufacturing_ready


def test_draft_or_stale_selection_never_creates_ear_contact():
    snap = _two_tier()
    snap["nfb_config_submitted"] = False
    assert resolve_receiving_tier_ear_contact_targets(snap) == ()
    snap = _two_tier()
    snap["_receiving_runtime_selection"]["bay_id"] = "stale"
    assert resolve_receiving_tier_ear_contact_targets(snap) == ()


def test_two_tiers_nfb_horizontal_x_does_not_change_either_skin_z():
    snap = _two_tier()
    before = resolve_receiving_tier_base_z_targets(snap)
    for hole, x in zip(snap["nfb_config"]["holes"], (125., -110.)):
        hole.update(
            manual_x_state="CONFIRMED", manual_x_mm=x,
            datum_revision="SOURCE-X-REV1", datum_snapshot={"w": 800, "t": 2},
        )
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    after = resolve_receiving_tier_base_z_targets(snap)
    assert [r.world_offset_z_mm for r in before] == pytest.approx(
        [r.world_offset_z_mm for r in after]
    )
    assert all(r.physical_skin_z_resolved for r in after)


def test_current_set_without_legacy_switch_brand_uses_each_v5_csv_source():
    """Actual modern Set schema has no switch_brand: per-switch CSV is owner."""
    snap = _two_tier()
    snap["receiving_layout"]["sets"][0].pop("switch_brand", None)
    pairs = (
        ("士林", "nfbv5:士林:2P400", 107.),
        ("東元", "nfbv5:東元:3P125SN", 68.),
    )
    for hole, (brand, model, _depth) in zip(snap["nfb_config"]["holes"], pairs):
        hole["source_brand"] = brand
        hole["model_filename"] = model
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    base = resolve_receiving_tier_base_z_targets(snap)
    assert [t.layer_index for t in base] == [0, 1]
    assert [t.source_depths_mm for t in base] == [(107.,), (68.,)]
    assert all(t.physical_skin_z_resolved for t in base)
    assert len({t.world_offset_z_mm for t in base}) == 2
    # Two different brands have no approved shared fixing-ear Z anchor;
    # never take the maximum of selected switches across brands.
    with pytest.raises(ValueError, match="EAR_Z_MIXED_BRANDS_REQUIRE_APPROVED_RULE"):
        resolve_receiving_tier_ear_contact_targets(snap)


def test_v5_csv_missing_depth_or_cross_brand_blocks_only_affected_tier_z():
    snap = _two_tier()
    snap["receiving_layout"]["sets"][0].pop("switch_brand", None)
    holes = snap["nfb_config"]["holes"]
    holes[0].update(source_brand="士林", model_filename="nfbv5:士林:2P400")
    holes[1].update(source_brand="東元", model_filename="nfbv5:東元:2P400")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    # The CURRENT approved fixing-plate Z is a single BRANDED ear anchor,
    # not per-tier NFB Z. Mixed brands lack a shared physical support rule;
    # even though tier 0 has a valid 107-mm source, no assembled support
    # or preview DXF may borrow that permission for tier 1.
    before = deepcopy(snap)
    with pytest.raises(ValueError, match="EAR_Z_MIXED_BRANDS_REQUIRE_APPROVED_RULE"):
        resolve_receiving_tier_base_z_targets(snap)
    assert snap == before
    # A cross-brand identity is not silently repaired by using other CSV.
    holes[1]["model_filename"] = "nfbv5:士林:2P400"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    before = deepcopy(snap)
    with pytest.raises(ValueError, match="EAR_Z_BRAND_IDENTITY_DRIFT"):
        resolve_receiving_tier_base_z_targets(snap)
    assert snap == before


def test_quantity_frozen_integral_indices_restore_but_stable_ids_stay_guarded():
    """Phase6 Real-DTO 0.0 is an identity 0 only with exact saved Set/Bay."""
    from ae_engine.receiving_tier_ear_z_targets import _current_brand_config
    snap = _two_tier()
    original = _current_brand_config(snap)
    snap["active_mode"] = "quantity"
    selected = snap["_receiving_runtime_selection"]
    selected["set_index"] = 0.0
    selected["bay_index"] = 0.0
    assert _current_brand_config(snap) == original
    # Do not mutate project authority while interpreting the request DTO.
    assert selected["set_index"] == 0.0
    assert selected["bay_index"] == 0.0

    for value in (0.5, -1.0, float("nan"), float("inf"), True):
        altered = deepcopy(snap)
        altered["_receiving_runtime_selection"]["set_index"] = value
        with pytest.raises(ValueError, match="EAR_Z_SET_IDENTITY_DRIFT"):
            _current_brand_config(altered)
    for key, value, pattern in (
        ("set_id", "stale-set", "EAR_Z_SET_IDENTITY_DRIFT"),
        ("bay_id", "stale-bay", "EAR_Z_BAY_IDENTITY_DRIFT"),
    ):
        altered = deepcopy(snap)
        altered["_receiving_runtime_selection"][key] = value
        with pytest.raises(ValueError, match=pattern):
            _current_brand_config(altered)

    # There is no indiscriminate relaxation for non-quantity callers.
    setbay = deepcopy(snap)
    setbay["active_mode"] = "set_bay"
    with pytest.raises(ValueError, match="EAR_Z_SET_IDENTITY_DRIFT"):
        _current_brand_config(setbay)


def test_ear_brand_max_depth_uses_entire_csv_not_selected_125sn():
    from ae_engine.receiving_tier_ear_z_targets import (
        committed_receiving_ear_brand_max_depth_mm,
    )
    from ae_engine.receiving_nfb_numeric_catalog import brand_max_depth_mm
    assert brand_max_depth_mm("士林") == 107.0
    assert brand_max_depth_mm("東元") == 103.0
    assert brand_max_depth_mm("伍菱") == 107.0
    snap = _assembled()
    holes = snap["nfb_config"]["holes"]
    for hole in holes:
        hole["model_filename"] = "nfbv5:士林:2P125SN"
        hole["source_brand"] = "士林"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    assert committed_receiving_ear_brand_max_depth_mm(snap) == 107.0
    holes[0]["model_filename"] = "nfbv5:士林:3P125SN"
    holes[1]["model_filename"] = "nfbv5:士林:2P400"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    assert committed_receiving_ear_brand_max_depth_mm(snap) == 107.0


def test_brand_max_ear_contact_is_invariant_when_selected_tier_depth_changes():
    snap = _two_tier()
    original = resolve_receiving_tier_ear_contact_targets(snap)
    assert len(original) == 4
    assert len({row.target_ear_contact_world_z_mm for row in original}) == 1
    for hole in snap["nfb_config"]["holes"]:
        hole.update(source_brand="士林", model_filename="nfbv5:士林:2P125SN")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    shallow = resolve_receiving_tier_ear_contact_targets(snap)
    assert len(shallow) == 4
    assert [row.target_ear_contact_world_z_mm for row in shallow] == pytest.approx(
        [row.target_ear_contact_world_z_mm for row in original]
    )
    # Both 68-mm tiers must rebuild their own CENTER support returns to
    # the unchanged 107-mm ear anchor, even though the core working skins
    # have 68-mm NFB clearances.  This is not a weld/MFG release.
    assert all(row.base_skin_z_source_verified for row in shallow)
    assert all(not row.manufacturing_ready for row in shallow)
