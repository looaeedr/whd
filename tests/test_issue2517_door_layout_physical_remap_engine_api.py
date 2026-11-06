# -*- coding: utf-8 -*-
"""#2517 physical Door-grid deletion and saved hole ownership are Engine-only."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import door_layout_host_adapter


def _source():
    cells = {"door_layout_features": {
        "0:0": [{"hole": "upper"}], "0:1": [{"hole": "lower"}],
        "1:0": [{"hole": "right"}],
    }}
    rows = [
        {"cell_key": "0:0", "stable_id": "upper", "layers": 1},
        {"cell_key": "0:1", "stable_id": "lower", "layers": 2},
        {"cell_key": "1:0", "stable_id": "c2r1", "layers": 1},
    ]
    parts = {
        "inner_door:upper:panel": [{"hole": "panel upper"}],
        "inner_door:lower:panel": [{"hole": "panel lower"}],
        "inner_door:c2r1:panel": [{"hole": "panel right"}],
        "door_c1_r1": [{"hole": "upper"}],
        "door_c1_r2": [{"hole": "lower"}],
        "door_c2_r1": [{"hole": "right"}],
        "unrelated": ["unchanged"],
    }
    faces = {
        "inner_door:upper:panel": ["upper face"],
        "inner_door:lower:panel": ["lower face"],
        "inner_door:c2r1:panel": ["right face"],
    }
    return rows, cells, parts, faces


def test_engine_resolves_authoritative_receiving_inner_door_ids():
    assert [manufacturing_api.receiving_inner_door_stable_id_for_cell(k)
            for k in ("0:0", "0:1", "1:0", "2:3")] == [
                "upper", "lower", "c2r1", "c3r4",
            ]
    with pytest.raises(ValueError):
        manufacturing_api.receiving_inner_door_stable_id_for_cell("-1:0")


def test_headless_delete_row_rekeys_panel_holes_and_all_physical_workspaces():
    rows, cells, parts, faces = _source()
    physical = {
        "surface": parts, "workspace": deepcopy(parts),
        "workspace_face": faces, "designer": deepcopy(parts),
        "designer_face": deepcopy(faces),
    }
    frozen = deepcopy((rows, cells, physical))
    result = manufacturing_api.remap_receiving_door_layout_after_delete(
        operation="delete_row", column_index=0, row_index=0,
        inner_doors=rows, cell_sources=cells, physical_sources=physical,
    )
    assert (rows, cells, physical) == frozen
    assert result["inner_doors"] == [
        {"cell_key": "0:0", "stable_id": "upper", "layers": 2},
        {"cell_key": "1:0", "stable_id": "c2r1", "layers": 1},
    ]
    assert result["identity_changes"] == {
        "upper": None, "lower": "upper",
    }
    assert result["cell_sources"]["door_layout_features"] == {
        "0:0": [{"hole": "lower"}], "1:0": [{"hole": "right"}],
    }
    for name in ("surface", "workspace", "designer"):
        state = result["physical_sources"][name]
        assert state["inner_door:upper:panel"] == [{"hole": "panel lower"}]
        assert "inner_door:lower:panel" not in state
        assert state["door_c1_r1"] == [{"hole": "lower"}]
        assert "door_c1_r2" not in state
        assert state["door_c2_r1"] == [{"hole": "right"}]
        assert state["unrelated"] == ["unchanged"]
    for name in ("workspace_face", "designer_face"):
        state = result["physical_sources"][name]
        assert state["inner_door:upper:panel"] == ["lower face"]
        assert "inner_door:lower:panel" not in state
        assert state["inner_door:c2r1:panel"] == ["right face"]


def test_headless_delete_column_rekeys_right_panel_to_upper_and_preserves_source():
    rows, cells, parts, faces = _source()
    before = deepcopy((rows, cells, parts, faces))
    result = manufacturing_api.remap_receiving_door_layout_after_delete(
        operation="delete_column", column_index=0, inner_doors=rows,
        cell_sources=cells, physical_sources={"workspace": parts, "face": faces} if False
        else {"workspace": parts, "workspace_face": faces},
    )
    assert (rows, cells, parts, faces) == before
    assert result["inner_doors"] == [
        {"cell_key": "0:0", "stable_id": "upper", "layers": 1},
    ]
    assert result["physical_sources"]["workspace"]["inner_door:upper:panel"] == [
        {"hole": "panel right"},
    ]
    assert result["physical_sources"]["workspace"]["door_c1_r1"] == [
        {"hole": "right"},
    ]
    assert "inner_door:lower:panel" not in result["physical_sources"]["workspace"]


@pytest.mark.parametrize("operation,col,row", [
    ("delete_column", True, None), ("delete_row", 0, None),
    ("delete_row", -1, 0), ("delete_row", 0, False),
    ("not-an-operation", 0, None), ("delete_column", 0, 1),
])
def test_invalid_grid_operation_fails_closed(operation, col, row):
    rows, cells, parts, _ = _source()
    frozen = deepcopy((rows, cells, parts))
    with pytest.raises(ValueError):
        manufacturing_api.remap_receiving_door_layout_after_delete(
            operation=operation, column_index=col, row_index=row,
            inner_doors=rows, cell_sources=cells,
            physical_sources={"workspace": parts},
        )
    assert (rows, cells, parts) == frozen


def test_conflicting_physical_source_cannot_silently_overwrite_saved_hole():
    rows = [{"cell_key": "0:1", "stable_id": "lower"}]
    sources = {
        "inner_door:upper:panel": ["stale upper"],
        "inner_door:lower:panel": ["new upper"],
    }
    before = deepcopy((rows, sources))
    with pytest.raises(ValueError, match="身份衝突"):
        manufacturing_api.remap_receiving_door_layout_after_delete(
            operation="delete_row", column_index=0, row_index=0,
            inner_doors=rows, physical_sources={"workspace": sources},
        )
    assert (rows, sources) == before


class _Workspace:
    def __init__(self, parts, faces):
        self.parts = deepcopy(parts)
        self.faces = deepcopy(faces)

    def part_features_snapshot(self):
        return deepcopy(self.parts)

    def part_face_features_snapshot(self):
        return deepcopy(self.faces)

    def replace_part_features(self, value):
        self.parts = deepcopy(value)

    def replace_part_face_features(self, value):
        self.faces = deepcopy(value)


def test_gui_host_delegates_entire_physical_transaction_to_one_engine_port(monkeypatch):
    rows, cells, parts, faces = _source()
    surface = deepcopy(parts)
    workspace = _Workspace(parts, faces)
    designer = _Workspace(parts, faces)
    host = SimpleNamespace(
        receiving_inner_doors=deepcopy(rows), surface_features=surface,
        workspace_controller=workspace,
        fold_designer_app=SimpleNamespace(designer_workspace=designer),
        door_layout_features=deepcopy(cells["door_layout_features"]),
        door_layout_indicator_states={}, door_layout_indicator_box_features={},
        door_layout_indicator_door_features={}, door_layout_handle_edges={},
    )
    calls = []
    real = manufacturing_api.remap_receiving_door_layout_after_delete

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(
        manufacturing_api, "remap_receiving_door_layout_after_delete", record,
    )
    door_layout_host_adapter._remap_door_layout_owned_data(
        host, operation="delete_row", column_index=0, row_index=0,
    )
    assert len(calls) == 1
    assert host.receiving_inner_doors[0]["stable_id"] == "upper"
    assert host.door_layout_features["0:0"] == [{"hole": "lower"}]
    for state in (surface, workspace.parts, designer.parts):
        assert state["inner_door:upper:panel"] == [{"hole": "panel lower"}]
        assert state["door_c1_r1"] == [{"hole": "lower"}]
    for state in (workspace.faces, designer.faces):
        assert state["inner_door:upper:panel"] == ["lower face"]
