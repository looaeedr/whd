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


@pytest.mark.parametrize("part_key", ("head", "door_c1_r1", "base_plate_c1_r1"))
@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
@pytest.mark.parametrize("bad", (True, False, 0, -1, None, "nan", "inf"))
def test_original_present_physical_source_cannot_be_float_coerced_before_part_request(
    part_key, field, bad,
):
    """Even a valid selected cell cannot conceal a corrupt global W/H/D/T/FW."""
    data = payload("受電箱")
    data[field] = bad
    before = deepcopy(data)
    with pytest.raises(ValueError, match="包外尺寸"):
        resolve_fold_designer_payload_topology(part_key, data)
    with pytest.raises(ValueError, match="包外尺寸"):
        gui._payload_topology_context(part_key, data)
    assert data == before


@pytest.mark.parametrize("part_key", ("door_c1_r1", "base_plate_c1_r1"))
@pytest.mark.parametrize("bad_columns", (
    [[True, [210, 190]], [200, [400]]],
    [[300, [False, 190]], [200, [400]]],
    [[300, [0, 190]], [200, [400]]],
    [[300, [float("nan"), 190]], [200, [400]]],
    [[300, [210, float("inf")]], [200, [400]]],
    [[300, []], [200, [400]]],
    "300x210",
))
def test_original_raw_door_grid_rejected_before_physical_cell_selection(
    part_key, bad_columns,
):
    """A serialized boolean width/height cannot create a one-mm Door/Plate."""
    data = payload()
    data["door_layout_columns"] = bad_columns
    before = deepcopy(data)
    with pytest.raises((ValueError, TypeError)):
        resolve_fold_designer_payload_topology(part_key, data)
    with pytest.raises((ValueError, TypeError)):
        gui._fold_designer_part_spec_from_payload(object(), part_key, data)
    assert data == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_fractional_physical_source_has_same_engine_cell_identity_in_gui(family):
    data = payload(family)
    data.update(w="500.25", h="400.125", d="200.5", t="2.125", fw="25.5")
    data["door_layout_columns"] = [
        ["300.125", ["210.25", "189.875"]],
        ["200.125", ["400.125"]],
    ]
    before = deepcopy(data)
    for key, width, height in (
        ("door_c1_r1", 300.125, 210.25),
        ("base_plate_c1_r2", 300.125, 189.875),
        ("door_c2_r1", 200.125, 400.125),
    ):
        engine = resolve_fold_designer_payload_topology(key, data)
        assert gui._payload_topology_context(key, data) == engine
        assert (engine[2], engine[3], engine[4], engine[5], engine[6]) == (
            width, height, 200.5, 2.125, 25.5,
        )
    assert data == before


def test_true_project_reload_physical_cell_routes_to_same_real_door_dxf(
    tmp_path,
):
    """Exact saved W/H/T and cell ID survive reopened .p6fold → Engine → DXF."""
    import ezdxf
    import phase6_project_file as project

    saved = {
        "model": "金庫型", "w": 500.25, "h": 400.125,
        "d": 200.5, "t": 2.125, "fw": 25.5,
        "door_layout_columns": [
            [300.125, [210.25, 189.875]],
            [200.125, [400.125]],
        ],
    }
    before = deepcopy(saved)
    path = project.write_project(
        tmp_path / "physical-topology.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    reopened = project.read_project(path)["snapshot"]
    result = resolve_fold_designer_payload_topology("door_c1_r1", reopened)
    assert (result[2], result[3], result[5], result[6]) == (
        300.125, 210.25, 2.125, 25.5,
    )
    cell = result[12]
    assert door_layout_part_key(cell) == "door_c1_r1"
    values = dict(
        w=result[2], h=result[3], t=result[5], fw=result[6],
        door_gap_w=2.0, door_gap_h=2.0,
        door_fold_l=10.0, door_fold_r=10.0,
        door_fold_t=10.0, door_fold_b=10.0,
    )
    spec = manufacturing_api.build_door_operator_part_spec(
        values, model_name="金庫型", frame_edges=cell.edges,
    )
    rendered = manufacturing_api.build_part_render_data(spec)
    assert rendered.material is not None and rendered.material.area > 0
    target = tmp_path / "door_c1_r1.dxf"
    manufacturing_api.save_part_render_data_dxf(
        rendered, target, verify_reopen=True,
    )
    assert manufacturing_api.verify_saved_part_render_data_dxf(rendered, target).ok
    assert any(e.dxf.layer == "CUTTING" for e in ezdxf.readfile(target).modelspace())
    assert saved == before


