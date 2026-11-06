"""#2517 Fold Designer Door and BasePlate physical cell lookup is Engine API."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api, resolve_fold_designer_payload_topology
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells, door_layout_part_key
from gui_modules.application import fold_designer_manufacturing_projection as gui


def payload(model="金庫型"):
    return {
        "model": model, "w": 500, "h": 400, "d": 200, "t": 2, "fw": 25,
        "door_layout_columns": [[300, [210, 190]], [200, [400]]],
        "features": [{"kind": "operator-feature"}],
        "face_features": {"front": ["existing"]},
    }


@pytest.mark.parametrize("key,expected", [
    ("door_c1_r1", (300.0, 210.0, 0, 0)),
    ("door_c1_r2", (300.0, 190.0, 0, 1)),
    ("door_c2_r1", (200.0, 400.0, 1, 0)),
    ("base_plate_c1_r2", (300.0, 190.0, 0, 1)),
    ("base_plate_c2_r1", (200.0, 400.0, 1, 0)),
])
def test_engine_returns_same_authoritative_cell_for_each_physical_key(key, expected):
    data = payload()
    before = deepcopy(data)
    result = resolve_fold_designer_payload_topology(key, data)
    source, returned_key, w, h, d, t, fw, model, unknown, corner, features, face, door, base = result
    assert manufacturing_api.resolve_fold_designer_payload_topology is resolve_fold_designer_payload_topology
    assert returned_key == key
    assert (w, h, d, t, fw) == (expected[0], expected[1], 200.0, 2.0, 25.0)
    assert model == "金庫型" and not unknown
    cell = door or base
    assert cell is not None and (cell.column_index, cell.row_index) == expected[2:]
    assert door_layout_part_key(cell) == key.replace("base_plate_", "door_", 1)
    assert cell in derive_door_layout_cells([(300, (210, 190)), (200, (400,))])
    assert features == ({"kind": "operator-feature"},)
    assert face == {"front": ["existing"]}
    assert data == before


def test_legacy_custom_model_save_reload_and_original_noncell_dimensions():
    data = json.loads(json.dumps(payload("未知類型"), ensure_ascii=False))
    result = resolve_fold_designer_payload_topology("head", data)
    assert result[1:7] == ("head", 500.0, 400.0, 200.0, 2.0, 25.0)
    assert result[7] == "自訂" and result[8] is True
    assert result[12] is None and result[13] is None
    assert gui._payload_topology_context("head", data) == result


@pytest.mark.parametrize("key", ("door_c1_r1", "base_plate_c1_r1"))
def test_missing_real_multidoor_topology_fails_closed(key):
    with pytest.raises(ValueError, match="authoritative multi-door topology"):
        resolve_fold_designer_payload_topology(key, {"w": 500, "h": 400})


@pytest.mark.parametrize("key", ("door_c9_r9", "base_plate_c9_r9"))
def test_missing_stable_id_never_uses_another_physical_cell(key):
    with pytest.raises(ValueError, match="stable_id"):
        resolve_fold_designer_payload_topology(key, payload())


def test_gui_adapter_delegates_without_cell_selection_or_physical_W_H(monkeypatch):
    sentinel = object()
    calls = []
    def engine(key, data):
        calls.append((key, data))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "resolve_fold_designer_payload_topology", engine)
    data = payload("受電箱")
    assert gui._payload_topology_context("door_c1_r1", data) is sentinel
    assert calls == [("door_c1_r1", data)]
    src = inspect.getsource(gui._payload_topology_context)
    assert "manufacturing_api.resolve_fold_designer_payload_topology(" in src
    for forbidden in ("derive_door_layout_cells(", "door_layout_export_filename(",
                      "start_width", "start_height", "base_plate_cell"):
        assert forbidden not in src
    owner_source = inspect.getsource(resolve_fold_designer_payload_topology)
    assert "tkinter" not in owner_source and "phase6_" not in owner_source
