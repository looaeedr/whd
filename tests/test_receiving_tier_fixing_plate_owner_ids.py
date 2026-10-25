# -*- coding: utf-8 -*-
"""#1503: 2 NFB tiers => 2 independently mounted bases + 4 ear source previews."""
from copy import deepcopy
import pytest

from ae_engine.receiving_base_fixing_plate import (
    MANUFACTURING_STATUS,
    receiving_base_fixing_plate_previews,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def test_two_tiers_have_four_distinct_child_ear_ids_in_their_own_base():
    snap=_two_tier()
    ears=receiving_base_fixing_plate_previews(snap,available_parts=("base_plate",))
    assert len(ears)==4
    assert [e.part_id for e in ears]==[
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    ]
    assert [e.parent_part_id for e in ears]==[
        "base_plate:nfb_layer:0","base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1","base_plate:nfb_layer:1",
    ]
    assert [e.side for e in ears]==["left","right","left","right"]
    assert all(e.stock_thickness_mm==2 for e in ears)
    assert all(e.nominal_source_outline_mm==(256.,105.) for e in ears)
    assert all(e.applicable_slot_pair_indexes==(1,2) for e in ears)
    assert len({e.part_id for e in ears})==4
    assert all(e.manufacturing_status==MANUFACTURING_STATUS
               and not e.manufacturing_ready for e in ears)
    # BEND exists in revised source, but signed 3D forming / weld still unverified.
    assert ears[0].nominal_fold_from_weld_edge_mm==pytest.approx(23)


def test_legacy_one_tier_still_returns_one_pair_of_original_child_ids():
    snap=_assembled()
    ears=receiving_base_fixing_plate_previews(snap,available_parts=("base_plate",))
    assert [e.part_id for e in ears]==[
        "base_plate:fixing_plate:left","base_plate:fixing_plate:right",
    ]
    assert [e.parent_part_id for e in ears]==["base_plate","base_plate"]


def test_invalid_or_unsubmitted_nfb_layer_owner_never_creates_four_false_ears():
    snap=_two_tier()
    snap["_receiving_runtime_selection"]["set_id"]="stale"
    assert receiving_base_fixing_plate_previews(
        snap,available_parts=("base_plate",))==()
    snap=_two_tier()
    snap["nfb_config_submitted"]=False
    result=receiving_base_fixing_plate_previews(
        snap,available_parts=("base_plate",))
    assert len(result)==2
    assert all(e.parent_part_id=="base_plate" for e in result)


def test_two_tier_source_children_visible_with_real_layer_part_keys():
    snap=_two_tier()
    ears=receiving_base_fixing_plate_previews(
        snap,available_parts=(
            "base_plate:nfb_layer:0","base_plate:nfb_layer:1",
        ))
    assert len(ears)==4



def test_navigation_tier_ears_nested_under_own_plate_not_the_other():
    from phase6_part_navigation import project_hierarchy, operator_part_label
    keys=(
        "base_plate","base_plate:nfb_layer:0",
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:nfb_layer:1",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    )
    rows=project_hierarchy(keys)
    direct={
        row.part_key:(row.parent_key,row.depth)
        for row in rows
    }
    assert direct["base_plate:fixing_plate:nfb_layer:0:left"]==(
        "base_plate:nfb_layer:0",1
    )
    assert direct["base_plate:fixing_plate:nfb_layer:1:right"]==(
        "base_plate:nfb_layer:1",1
    )
    assert operator_part_label("base_plate:nfb_layer:0")=="底板（NFB 第1層）"
    assert operator_part_label(
        "base_plate:fixing_plate:nfb_layer:1:right"
    )=="底板固定片（第2層右）"


def test_two_nfb_tiers_have_four_independent_source_cutting_blanks_and_xyz():
    """W800 source EARs are already defined, not PAD/unknown geometry."""
    from ae_engine.receiving_base_fixing_plate_geometry import (
        SOURCE_DXF_SHA256, build_fixing_plate_source_render_data,
    )
    from ae_engine.receiving_tier_ear_assembly_xy import (
        resolve_receiving_tier_ear_mating_xy,
    )
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_ear_contact_targets,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    snapshot = _two_tier()
    xy = {row.ear_id: row for row in resolve_receiving_tier_ear_mating_xy(snapshot)}
    contacts = {
        row.ear_id: row for row in resolve_receiving_tier_ear_contact_targets(snapshot)
    }
    assert len(xy) == len(contacts) == 4
    renders = {}
    for part_id, target in xy.items():
        material = build_fixing_plate_source_render_data(part_id, snapshot=snapshot)
        renders[part_id] = material
        meta = material.metadata
        assert material.unfolded_topology.piece_id == part_id
        assert meta["stable_id"] == part_id
        assert meta["source_dxf_sha256"] == SOURCE_DXF_SHA256
        assert meta["source_cutting_verified"] is True
        assert meta["thickness"] == 2
        assert meta["source_flat_dimensions"] == (256, 105)
        assert meta["xy_mating_proven"] is True
        assert meta["parent_base_id"] == target.parent_base_id
        assert meta["nfb_layer_index"] == target.layer_index
        assert meta["nominal_slot_pair_indexes"] == (1, 2)
        assert meta["nominal_weld_inside_skin_x_mm"] == pytest.approx(
            target.side_inside_weld_x_mm,
        )
        assert meta["nominal_base_fixing_hole_world_x_mm"] == pytest.approx(
            target.selected_slot_column_x_mm,
        )
        assert meta["nominal_base_fixing_hole_world_y_mm"] == pytest.approx(
            target.selected_slot_pair_world_y_mm,
        )
        assert meta["base_back_skin_world_z_mm"] == pytest.approx(
            contacts[part_id].base_back_skin_world_z_mm,
        )
        assert meta["ear_contact_target_world_z_mm"] == pytest.approx(
            contacts[part_id].target_ear_contact_world_z_mm,
        )
        assert meta["base_skin_z_source_verified"] is True
        assert meta["formed_geometry_verified"] is False
        assert meta["weld_z_verified"] is False
        assert meta["manufacturing_ready"] is False
        assert len([p for p in material.scene.primitives
                    if isinstance(p, PolylinePrimitive)
                    and p.layer == "CUTTING" and p.closed]) == 5
        assert len(material.fold_guides) == 1
        assert material.fold_guides[0].position == 23.0
        assert material.metadata["source_bend_verified"] is True
        assert material.metadata["formed_direction_verified"] is False
    assert len(renders) == 4
    assert len({id(p.scene) for p in renders.values()}) == 4
    assert len({id(p.material) for p in renders.values()}) == 4
    assert [renders[k].metadata["nfb_layer_index"] for k in renders] == [0, 0, 1, 1]
    assert [renders[k].metadata["nominal_base_fixing_hole_world_x_mm"]
            for k in renders] == [-335., 335., -335., 335.]


def test_tier_fixing_plate_rejects_stale_or_missing_physical_owner():
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
    )
    valid = _two_tier()
    part = "base_plate:fixing_plate:nfb_layer:0:left"
    with pytest.raises(ValueError, match="NEEDS_CURRENT_SOURCE_SNAPSHOT"):
        build_fixing_plate_source_render_data(part)
    stale = deepcopy(valid)
    stale["_receiving_runtime_selection"]["bay_id"] = "stale-bay"
    with pytest.raises(ValueError, match="CABINET_MISMATCH"):
        build_fixing_plate_source_render_data(part, snapshot=stale)
    with pytest.raises(ValueError, match="CABINET_MISMATCH"):
        build_fixing_plate_source_render_data(
            "base_plate:fixing_plate:nfb_layer:7:left", snapshot=valid,
        )


def test_single_tier_source_flat_render_still_uses_real_original_one_pair():
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
    )
    snapshot = _assembled()
    for side, x in (("left", -335.0), ("right", 335.0)):
        part = f"base_plate:fixing_plate:{side}"
        render = build_fixing_plate_source_render_data(part, snapshot=snapshot)
        assert render.metadata["nominal_base_fixing_hole_world_x_mm"] == x
        assert render.metadata["parent_base_id"] == "base_plate"
        assert render.metadata["nfb_layer_index"] == 0
        assert render.metadata["nominal_base_fixing_hole_world_y_mm"] == (180., 320.)
        assert render.metadata["base_skin_z_source_verified"] is True
        assert not render.metadata["formed_geometry_verified"]
        assert not render.metadata["manufacturing_ready"]


@pytest.mark.parametrize("malformed", [42, True, object()])
def test_r5_83_fixing_preview_rejects_corrupt_input_containers(malformed):
    """No unhandled TypeError or fake ear when preview DTO/list is corrupt."""
    assert receiving_base_fixing_plate_previews(
        malformed, available_parts=("base_plate",),
    ) == ()
    assert receiving_base_fixing_plate_previews(
        _assembled(), available_parts=malformed,
    ) == ()


@pytest.mark.parametrize("malformed", [42, True, object()])
def test_r5_83_corrupt_two_tier_door_inventory_cannot_mint_four_ear_owners(malformed):
    """Source-owned NFB tier ear identity requires one actual upper Door."""
    source = _two_tier()
    source["inner_doors"] = malformed
    assert receiving_base_fixing_plate_previews(
        source, available_parts=("base_plate",),
    ) == ()
    # Real two-tier input still projects exactly four independent ears.
    correct = receiving_base_fixing_plate_previews(
        _two_tier(), available_parts=("base_plate",),
    )
    assert len(correct) == 4
    assert len({ear.part_id for ear in correct}) == 4
