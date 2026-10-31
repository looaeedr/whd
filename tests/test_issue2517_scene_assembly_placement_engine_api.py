"""#2517: manufacturing assembly placement dispatch is a public Engine API."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import assembly_placement as owner
from phase6_manufacturing_geometry import (
    _phase6_door_part_assembly_placement as gui_door,
    _phase6_assembly_placement_for_part as gui_scene,
    _PHASE6_ASSEMBLY_PLACEMENTS,
)
from tests.test_phase6_t16_receiving_placement import _snapshot as receiving_snapshot
from tests.test_issue37_vault_baseplate_placement import _vault_snapshot


def test_canonical_engine_is_sole_scene_dispatch_owner_and_gui_delegates():
    assert api.resolve_scene_assembly_placement is owner.resolve_scene_assembly_placement
    assert api.resolve_legacy_door_cell_scene_placement is owner.resolve_legacy_door_cell_scene_placement
    assert api.SCENE_ASSEMBLY_PLACEMENTS is _PHASE6_ASSEMBLY_PLACEMENTS
    assert "manufacturing_api.resolve_scene_assembly_placement(" in inspect.getsource(gui_scene)
    assert "manufacturing_api.resolve_legacy_door_cell_scene_placement(" in inspect.getsource(gui_door)
    assert "from phase6_" not in inspect.getsource(owner)


def test_vault_door_cells_use_engine_offsets_and_preserve_original_raw_input():
    source = {
        "model": "金庫型", "w": 500.0, "h": 600.0,
        "door_layout_columns": [[200.0, [250.0, 350.0]], [300.0, [600.0]]],
    }
    saved = deepcopy(source)
    for key, expected in (
        ("door_c2_r1", (100.0, 0.0, 0.0)),
        ("door_c1_r2", (-150.0, -125.0, 0.0)),
    ):
        result = api.resolve_scene_assembly_placement(source, key)
        assert result == ("front", expected)
        assert result == gui_scene(source, key)
        assert result == gui_door(source, key)
    assert source == saved
    assert json.loads(json.dumps(source)) == source


def test_receiving_real_topology_uses_existing_engine_native_placements():
    source = receiving_snapshot()
    snapshot_before = deepcopy(source)
    for key in ("door_c1_r1", "base_plate", "inner_door:upper:panel"):
        placement = owner.resolve_assembly_placement(source, key)
        result = api.resolve_scene_assembly_placement(source, key)
        assert result == (placement.placement_kind, placement.world_offset)
        assert gui_scene(source, key) == result
    assert source == snapshot_before


def test_vault_base_plate_uses_same_engine_placement_without_z_guess():
    source = _vault_snapshot()
    placement = owner.resolve_assembly_placement(source, "base_plate")
    assert api.resolve_scene_assembly_placement(source, "base_plate") == (
        placement.placement_kind, placement.world_offset,
    )
    assert api.resolve_scene_assembly_placement(source, "base_plate:fixing_plate:1") == (
        "standalone", (0.0, 0.0, 0.0),
    )


def test_saved_legacy_divider_offset_is_validated_and_never_recomputed_from_ui():
    key = "box_body:divider:custom:VERTICAL:one"
    source = {
        "model": "金庫型",
        "assembly_placements": {
            key: {"placement_kind": "stored", "world_offset": [-12.5, 24.0, 3.0]},
        },
    }
    before = deepcopy(source)
    assert api.resolve_scene_assembly_placement(source, key) == (
        "stored", (-12.5, 24.0, 3.0),
    )
    assert source == before
    for bad in ([True, 24.0, 3.0], [float("nan"), 0, 0], ["oops", 0, 0]):
        broken = deepcopy(source)
        broken["assembly_placements"][key]["world_offset"] = bad
        with pytest.raises(ValueError):
            api.resolve_scene_assembly_placement(broken, key)


@pytest.mark.parametrize("field,value", [
    ("w", True), ("h", False), ("w", float("nan")), ("h", float("inf")),
])
def test_legacy_door_outer_axis_invalid_values_fail_closed(field, value):
    source = {
        "model": "金庫型", "w": 500.0, "h": 600.0,
        "door_layout_columns": [[500.0, [600.0]]],
    }
    source[field] = value
    with pytest.raises(ValueError):
        api.resolve_scene_assembly_placement(source, "door_c1_r1")
    with pytest.raises(ValueError):
        gui_scene(source, "door_c1_r1")
