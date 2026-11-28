"""Identity-only regression for the existing certified Receiving C divider."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.door_dividers import derive_box_body_dividers, divider_part_profiles
from ae_engine.receiving_horizontal_divider_owner import OCCUPANCY
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

DIMENSIONS = {"w": 800., "h": 1600., "d": 350., "t": 2.}
KEY = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"


def fresh(mode="set_bay"):
    return api.fresh_receiving_mode(mode, {k: DIMENSIONS[k] for k in ("w", "h", "d")}, thickness=2.)


def bay(snapshot, si=0, bi=0):
    return snapshot["receiving_layout"]["sets"][si]["bays"][bi]


def reopen(tmp_path, name, snapshot):
    path = write_project(tmp_path / (name + ".p6fold"), {"schema": PROJECT_SCHEMA, "snapshot": snapshot})
    return read_project(path)["snapshot"]


def edit(snapshot, door, si=0, bi=0):
    source = deepcopy(snapshot)
    source["receiving_layout"] = api.update_receiving_bay(
        snapshot["receiving_layout"], set_index=si, bay_index=bi, door_state=door,
    )
    return source


def receipt(s, si=0, bi=0, expected=None):
    return api.open_receiving_horizontal_divider_owner_receipt(
        s, KEY, set_index=si, bay_index=bi, expected=expected,
    )


def remove_door_row(door):
    remap = api.remap_receiving_door_layout_after_delete(
        operation="delete_row", column_index=0, row_index=0,
        inner_doors=door.get("inner_doors", []),
        cell_sources={"door_layout_handle_edges": door.get("door_handle_edges", {})},
    )
    return {**deepcopy(door), "door_layout_columns": [[800., [1600.]]],
            "inner_doors": remap["inner_doors"],
            "door_handle_edges": remap["cell_sources"]["door_layout_handle_edges"]}


def certified_dxf(s, tmp_path, label, *, modal_error="C_DIVIDER_SAVED_WORKSPACE_REQUIRED"):
    s = api.project_receiving_bay_legacy_aliases(s, set_index=0, bay_index=0)
    d = {k: s[k] for k in DIMENSIONS}
    kwargs = dict(confirmation="fresh_family_confirmed", confirmed_door_layout_columns=s["door_layout_columns"])
    part = api.build_receiving_factory_confirmed_inner_door_lower_support(d, **kwargs)
    actual = derive_box_body_dividers(s["door_layout_columns"], depth=s["d"], thickness=s["t"],
                                     frame_width=s["fw"], layout_scope=s["door_layout_scope"],
                                     handle_edges=s.get("door_handle_edges"), model_name=s["model"])
    assert actual == (part,) and part.stable_id == KEY
    render = api.resolve_receiving_factory_confirmed_lower_divider_final_scene(d, box_body_render_data=None, **kwargs)
    assert render.metadata["divider_assembly_relief"]["candidate_status"] == "CERTIFIED_REGISTRY_VERIFIED"
    profile = divider_part_profiles((part,))[KEY]
    geometry = ResolvedManufacturingGeometry((ResolvedManufacturingPart(KEY, render, x_profile=tuple(profile["X"]), y_profile=tuple(profile["Y"])),))
    path = Path(api.save_selected_resolved_manufacturing_dxf(s, geometry, {"box_body": True, "door": False}, tmp_path / label)[KEY])
    doc = ezdxf.readfile(path)
    assert doc.header["$INSUNITS"] == 4 and not doc.audit().errors
    assert api.verify_saved_part_render_data_dxf(render, path).ok
    assert len(doc.modelspace()) == 10
    # Owner introduction is NOT a grant of normal MARKING permission.
    # Factory-only stock lacks the saved replay; legacy stock also lacks an owner.
    with pytest.raises(ValueError, match=f"^{modal_error}$"):
        api.open_selected_ordinary_marking_modal_source(s, geometry, KEY)
    return render, api.open_selected_physical_marking_preview(geometry, KEY)


def test_actual_save_as_delete_recreate_rejects_old_receipt_and_preserves_certified_dxf(tmp_path):
    source = reopen(tmp_path, "before", fresh())
    old = receipt(source)
    original = deepcopy(bay(source)["door_state"])
    first_render, first_preview = certified_dxf(source, tmp_path, "before_dxf")
    alias = reopen(tmp_path, "save_as", source)
    assert receipt(alias, expected=old) == old
    assert bay(alias)["base_plate_owner_id"] != old.owner_id
    deleted = reopen(tmp_path, "deleted", edit(alias, remove_door_row(original)))
    assert bay(deleted)[OCCUPANCY] is None
    with pytest.raises(ValueError, match="RECEIVING_HORIZONTAL_DIVIDER_OWNER_STALE"):
        receipt(deleted, expected=old)
    recreated = reopen(tmp_path, "recreated", edit(deleted, original))
    new = receipt(recreated)
    assert new.part_key == old.part_key and new.bay_id == old.bay_id and new.owner_id != old.owner_id
    with pytest.raises(ValueError, match="RECEIVING_HORIZONTAL_DIVIDER_OWNER_STALE"):
        receipt(recreated, expected=old)
    second_render, second_preview = certified_dxf(recreated, tmp_path, "recreated_dxf")
    assert first_preview == second_preview
    assert first_render.material.equals(second_render.material)
    assert first_render.scene == second_render.scene
    assert receipt(reopen(tmp_path, "recreated_save_as", recreated), expected=new) == new
    # Branching from the same saved alias must not recycle a counter ID.
    branch = edit(edit(alias, remove_door_row(original)), original)
    assert receipt(branch).owner_id != new.owner_id


def test_distinct_bays_and_recycled_bay_slot(tmp_path):
    source = fresh()
    source["receiving_layout"] = api.resize_receiving_operator_topology_with_removed_ids(source["receiving_layout"], set_index=0, bay_count=2)[0]
    source = reopen(tmp_path, "two", source)
    a, b = receipt(source), receipt(source, bi=1)
    assert a.part_key == b.part_key and a.owner_id != b.owner_id
    with pytest.raises(ValueError, match="OWNER_STALE"):
        receipt(source, bi=1, expected=a)
    door = deepcopy(bay(source, bi=1)["door_state"])
    removed = edit(source, remove_door_row(door), bi=1)
    assert receipt(removed, expected=a) == a
    restored = reopen(tmp_path, "other-rebuilt", edit(removed, door, bi=1))
    assert receipt(restored, expected=a) == a
    assert receipt(restored, bi=1).owner_id != b.owner_id
    previous = receipt(restored, bi=1)
    restored["receiving_layout"] = api.resize_receiving_operator_topology_with_removed_ids(restored["receiving_layout"], set_index=0, bay_count=1)[0]
    restored["receiving_layout"] = api.resize_receiving_operator_topology_with_removed_ids(restored["receiving_layout"], set_index=0, bay_count=2)[0]
    assert receipt(restored, expected=a) == a
    assert receipt(restored, bi=1).owner_id != previous.owner_id


def test_legacy_no_mint_on_open_save_or_edit(tmp_path):
    source = fresh()
    bay(source).pop(OCCUPANCY)
    legacy = reopen(tmp_path, "legacy", source)
    original = deepcopy(bay(legacy)["door_state"])
    for s in (legacy, reopen(tmp_path, "legacy_save_as", legacy), edit(edit(legacy, remove_door_row(original)), original)):
        assert OCCUPANCY not in bay(s)
        with pytest.raises(ValueError, match="OWNER_REQUIRED"):
            receipt(s)
    certified_dxf(legacy, tmp_path, "legacy_dxf",
                  modal_error="PHYSICAL_MARKING_DURABLE_OWNER_REQUIRED")


def test_quantity_projection_has_no_owner(tmp_path):
    source = reopen(tmp_path, "quantity", fresh("quantity"))
    assert OCCUPANCY not in bay(source)
    with pytest.raises(ValueError, match="OWNER_SCOPE_UNSUPPORTED"):
        receipt(source)


def test_owner_read_rejects_wrong_slot_and_duplicate_record(tmp_path):
    source = fresh()
    bad = deepcopy(source)
    bay(bad)[OCCUPANCY]["part_key"] = "box_body:divider:other:HORIZONTAL:C0_R0|R1"
    with pytest.raises(ValueError, match="OWNER_INVALID"):
        reopen(tmp_path, "bad", bad)
    source["receiving_layout"] = api.resize_receiving_operator_topology_with_removed_ids(source["receiving_layout"], set_index=0, bay_count=2)[0]
    bay(source, bi=1)[OCCUPANCY] = deepcopy(bay(source)[OCCUPANCY])
    with pytest.raises(ValueError, match="OWNER_DUPLICATE"):
        reopen(tmp_path, "duplicate", source)


def test_same_boundary_geometry_edit_preserves_owner_but_no_other_topology_grant(tmp_path):
    source = fresh()
    old = receipt(source)
    door = deepcopy(bay(source)["door_state"])
    resized_door = {**door, "door_layout_columns": [[800., [1000., 600.]]]}
    changed = reopen(tmp_path, "height", edit(source, resized_door))
    assert receipt(changed, expected=old) == old
    unsupported = {**door, "door_layout_columns": [[800., [500., 600., 500.]]]}
    changed = reopen(tmp_path, "three_rows", edit(changed, unsupported))
    assert bay(changed)[OCCUPANCY] is None
    with pytest.raises(ValueError, match="OWNER_STALE"):
        receipt(changed, expected=old)
    recreated = edit(changed, door)
    assert receipt(recreated).owner_id != old.owner_id


def test_singleton_save_projection_cannot_mint_from_uncommitted_grid(tmp_path):
    source = fresh()
    old = receipt(source)
    door = deepcopy(bay(source)["door_state"])
    removed = remove_door_row(door)
    live = {**source, **removed}
    projected = api.project_receiving_single_bay_door_controls(live)
    assert projected["sets"][0]["bays"][0][OCCUPANCY] is None
    assert receipt(source, expected=old) == old  # pure projection did not mutate input
    deleted = reopen(tmp_path, "projected_deleted", {**live, "receiving_layout": projected})
    with pytest.raises(ValueError, match="OWNER_STALE"):
        receipt(deleted, expected=old)
    uncommitted = {**deleted, **door}
    projected = api.project_receiving_single_bay_door_controls(uncommitted)
    assert projected["sets"][0]["bays"][0][OCCUPANCY] is None
    assert api.project_receiving_single_bay_door_controls(uncommitted) == projected
    # Only the actual committed Bay editor creates the next occupant.
    assert receipt(edit(deleted, door)).owner_id != old.owner_id
