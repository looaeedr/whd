# -*- coding: utf-8 -*-
"""#2517 Receiving physical Door source selection is Engine-owned."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, update_receiving_bay, project_receiving_bay_legacy_aliases,
)


def _snapshot(columns=None, enabled=True):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        door_state={
            "multi_door_enabled": enabled,
            "door_layout_columns": (columns if columns is not None
                                    else [[800.0, [1000.0, 600.0]]]),
            "door_layout_scope": "receiving-main",
            "inner_doors": [],
        },
    )
    return {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout, "w": 800, "h": 1600, "d": 350,
        "t": 2.0, "fw": 29.0,
    }


def test_engine_selects_same_authoritative_bay_two_door_cells_without_mutation():
    snapshot = _snapshot()
    before = deepcopy(snapshot)
    selection = api.project_receiving_operator_door_cell_sources(
        snapshot, set_index=0, bay_index=0,
    )
    assert selection is not None
    projected, cells = selection
    assert projected == project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=0,
    )
    assert tuple((c.column_index, c.row_index) for c in cells) == ((0, 0), (0, 1))
    assert snapshot == before
    projected["door_layout_columns"][0][1][0] = 999
    assert snapshot == before


@pytest.mark.parametrize("columns,enabled", [
    ([[800.0, [1600.0]]], False),
    ([[800.0, [800.0, 400.0, 400.0]]], True),
    ([[400.0, [1000.0, 600.0]], [400.0, [1000.0, 600.0]]], True),
])
def test_unsupported_door_topology_does_not_fabricate_two_face_preview(columns, enabled):
    assert api.project_receiving_operator_door_cell_sources(
        _snapshot(columns, enabled), set_index=0, bay_index=0,
    ) is None


def _part(key, scene):
    return SimpleNamespace(
        part_key=key, render_data=SimpleNamespace(scene=scene),
    )


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING"))
def test_assembly_pair_order_comes_from_exact_engine_part_identity(family):
    upper, lower = object(), object()
    resolved = SimpleNamespace(parts=[
        _part("door_c1_r2", lower), _part("head", object()),
        _part("door_c1_r1", upper),
    ])
    result = api.project_receiving_initial_door_source_scenes(
        {"model": family}, resolved,
    )
    assert result == (upper, lower)


def test_missing_source_and_non_receiving_are_not_invented():
    upper = object()
    partial = SimpleNamespace(parts=[_part("door_c1_r1", upper)])
    assert api.project_receiving_initial_door_source_scenes(
        {"model": "受電箱"}, partial,
    ) == ()
    assert api.project_receiving_initial_door_source_scenes(
        {"model": "金庫型"}, partial,
    ) == ()
    assert api.project_receiving_initial_door_source_scenes(
        {"model": "受電箱"}, None,
    ) == ()


def test_receiving_composition_does_not_derive_physical_door_source_in_gui():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/fold_designer_composition_receiving.py").read_text(encoding="utf-8")
    existing = source.split("    def existing_door_marks(", 1)[1].split(
        "    def cached_initial_door_marks(", 1
    )[0]
    cached = source.split("    def cached_initial_door_marks(", 1)[1].split(
        "    def resize_sets(", 1
    )[0]
    assert "manufacturing_api.project_receiving_operator_door_cell_sources(" in existing
    assert "project_receiving_bay_legacy_aliases(" not in existing
    assert "derive_door_layout_cells(" not in existing
    assert "manufacturing_api.project_receiving_initial_door_source_scenes(" in cached
    assert "door_c1_r1" not in cached and "door_c1_r2" not in cached
    assert "受電箱" not in cached
