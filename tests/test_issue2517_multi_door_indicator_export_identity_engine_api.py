"""#2517: one Engine physical Door ID for GUI, headless, project and DXF."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges, DoorLayoutCell, door_layout_indicator_export_filename,
)
from ae_engine.contracts import ManufacturingContext
from gui_modules.project import export_actions as gui


def _cells():
    return (
        DoorLayoutCell(0, 0, 400.0, 500.0, DoorFrameEdges()),
        DoorLayoutCell(0, 1, 400.0, 300.0, DoorFrameEdges()),
        DoorLayoutCell(1, 0, 200.0, 800.0, DoorFrameEdges()),
    )


def test_indicator_filename_is_original_engine_physical_cell_identity():
    assert api.door_layout_indicator_export_filename is door_layout_indicator_export_filename
    assert ae_engine.door_layout_indicator_export_filename is door_layout_indicator_export_filename
    for cell, stem in zip(_cells(), ("c1_r1", "c1_r2", "c2_r1")):
        assert api.door_layout_export_filename(cell) == f"door_{stem}.dxf"
        assert api.door_layout_indicator_export_filename(
            cell, part_kind="indicator_box",
        ) == f"indicator_box_{stem}.dxf"
        assert api.door_layout_indicator_export_filename(
            cell, part_kind="indicator_door",
        ) == f"indicator_door_{stem}.dxf"


@pytest.mark.parametrize("invalid", (True, False, 0.5, "0", -1, None))
def test_invalid_physical_door_cell_index_cannot_be_cast_into_dxf_filename(invalid):
    cell = DoorLayoutCell(invalid, 0, 400.0, 500.0, DoorFrameEdges())
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PHYSICAL_CELL_INDEX_INVALID"):
        api.door_layout_indicator_export_filename(cell, part_kind="indicator_box")
    row = DoorLayoutCell(0, invalid, 400.0, 500.0, DoorFrameEdges())
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PHYSICAL_CELL_INDEX_INVALID"):
        api.door_layout_indicator_export_filename(row, part_kind="indicator_door")


@pytest.mark.parametrize("kind", ("door", "base_plate", "indicator", "", None, 0))
def test_unregistered_export_kind_never_claims_a_manufacturing_sheet(kind):
    with pytest.raises(ValueError, match="DOOR_LAYOUT_INDICATOR_EXPORT_KIND_INVALID"):
        api.door_layout_indicator_export_filename(_cells()[0], part_kind=kind)


def test_actual_project_save_reload_preserves_2d_cell_and_all_three_dxf_names(tmp_path):
    import phase6_project_file as project

    raw = {
        "model": "金庫型", "w": 600.0, "h": 800.0, "d": 350.0,
        "t": 2.0, "fw": 25.0,
        "multi_door_enabled": True,
        "door_layout_columns": [[400.0, [500.0, 300.0]], [200.0, [800.0]]],
        "door_layout_indicator_states": {
            "0:0": {"mode": "indicator_box", "layers": 1, "groups": [2],
                     "offset_x": 0, "offset_y": 0, "is_box_dist": False},
        },
    }
    before = deepcopy(raw)
    target = project.write_project(
        tmp_path / "indicator-layout.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": raw},
    )
    reloaded = project.read_project(target)["snapshot"]
    restored_cells = api.door_layout_cells(
        reloaded["door_layout_columns"],
        total_width=reloaded["w"], total_height=reloaded["h"],
    )
    assert [(c.column_index, c.row_index) for c in restored_cells] == [
        (0, 0), (0, 1), (1, 0),
    ]
    for cell, original in zip(restored_cells, _cells()):
        assert api.door_layout_export_filename(cell) == api.door_layout_export_filename(original)
        for kind in ("indicator_box", "indicator_door"):
            assert api.door_layout_indicator_export_filename(
                cell, part_kind=kind,
            ) == api.door_layout_indicator_export_filename(original, part_kind=kind)
    assert raw == before


def test_real_gui_indicator_dxf_uses_engine_identity_and_reopens_actual_cutting(
    tmp_path, monkeypatch,
):
    physical_cells = (_cells()[0], _cells()[2])
    raw = {
        "mode": "indicator_box", "layers": 1, "groups": [2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    recorded = []
    contexts = []
    original_filename = api.door_layout_indicator_export_filename

    def record_filename(cell, *, part_kind):
        recorded.append((cell, part_kind))
        return original_filename(cell, part_kind=part_kind)

    def export_engine_render(spec, filename, context):
        rendered = api.build_part_render_data(spec, context)
        assert rendered.scene is not None
        assert rendered.material is not None and not rendered.material.is_empty
        saved = api.save_part_render_data_dxf(
            rendered, filename, overwrite=True, verify_reopen=True,
        )
        assert api.verify_saved_part_render_data_dxf(rendered, saved).ok
        contexts.append((spec, Path(saved)))

    monkeypatch.setattr(api, "door_layout_indicator_export_filename", record_filename)
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    host = SimpleNamespace(
        get_door_layout_cells=lambda: physical_cells,
        _door_layout_cell_key=lambda cell: f"{cell.column_index}:{cell.row_index}",
        door_layout_indicator_states={"0:0": deepcopy(raw), "1:0": deepcopy(raw)},
        _validate_door_layout_indicator_fit=lambda *_: None,
        door_layout_indicator_box_features={"0:0": [], "1:0": []},
        door_layout_indicator_door_features={"0:0": [], "1:0": []},
        _manufacturing_context=lambda *, draw_stock: context,
        _indicator_box_part_spec=lambda values, groups, *, features:
            api.build_indicator_box_operator_part_spec(
                values, groups, features=features,
            ),
        _export_authoritative_part=export_engine_render,
    )
    directory = tmp_path / "physical-dxf"
    directory.mkdir()
    outputs = gui.export_multi_door_indicator_box_parts(
        host, str(directory), {"model": "金庫型", "t": 2.0},
        export_box=True, export_door=False,
    )
    assert outputs == ["indicator_box_c1_r1.dxf", "indicator_box_c2_r1.dxf"]
    assert recorded == [
        (physical_cells[0], "indicator_box"),
        (physical_cells[1], "indicator_box"),
    ]
    assert len(contexts) == 2
    for spec, path in contexts:
        assert path.name in outputs and path.is_file()
        assert any(entity.dxf.layer == "CUTTING" for entity in ezdxf.readfile(path).modelspace())


def test_real_gui_indicator_door_filename_comes_from_engine_before_export(
    monkeypatch,
):
    cell = _cells()[1]
    physical = {"mode": "indicator_box", "layers": 1, "groups": [2],
                "offset_x": 0, "offset_y": 0, "is_box_dist": False}
    seen = []
    host = SimpleNamespace(
        get_door_layout_cells=lambda: (cell,),
        _door_layout_cell_key=lambda _: "0:1",
        door_layout_indicator_states={"0:1": physical},
        _validate_door_layout_indicator_fit=lambda *_: None,
        door_layout_indicator_box_features={"0:1": []},
        door_layout_indicator_door_features={"0:1": []},
        _manufacturing_context=lambda *, draw_stock: None,
        _indicator_door_part_spec=lambda values, groups, *, features: ("small-door", groups),
        _export_authoritative_part=lambda spec, filepath, context:
            seen.append((spec, Path(filepath).name)),
    )
    assert gui.export_multi_door_indicator_box_parts(
        host, "/unused", {"t": 2}, export_box=False, export_door=True,
    ) == ["indicator_door_c1_r2.dxf"]
    assert seen == [(("small-door", (2,)), "indicator_door_c1_r2.dxf")]


def test_later_corrupt_saved_indicator_cell_never_writes_earlier_dxf(tmp_path):
    """Direct GUI route must preflight every raw cell before first Engine write."""
    cells = _cells()[:2]
    valid = {"mode": "indicator_box", "layers": 1, "groups": [2],
             "offset_x": 0, "offset_y": 0, "is_box_dist": False}
    invalid = {**valid, "groups": ["bad"]}
    written = []
    source = {"0:0": deepcopy(valid), "0:1": deepcopy(invalid)}
    before = deepcopy(source)
    host = SimpleNamespace(
        get_door_layout_cells=lambda: cells,
        _door_layout_cell_key=lambda c: f"{c.column_index}:{c.row_index}",
        door_layout_indicator_states=source,
        _validate_door_layout_indicator_fit=lambda *_: None,
        door_layout_indicator_box_features={"0:0": [], "0:1": []},
        door_layout_indicator_door_features={"0:0": [], "0:1": []},
        _manufacturing_context=lambda *, draw_stock: None,
        _indicator_box_part_spec=lambda *_args, **_kwargs: object(),
        _export_authoritative_part=lambda *args: written.append(args),
    )
    with pytest.raises((ValueError, TypeError)):
        gui.export_multi_door_indicator_box_parts(
            host, str(tmp_path), {"model": "金庫型", "t": 2.0},
            export_box=True, export_door=False,
        )
    assert written == []
    assert list(tmp_path.iterdir()) == []
    assert source == before


def test_later_indicator_partspec_failure_is_rejected_before_earlier_dxf(tmp_path):
    cells = _cells()[:2]
    valid = {"mode": "indicator_box", "layers": 1, "groups": [2],
             "offset_x": 0, "offset_y": 0, "is_box_dist": False}
    writes = []
    def spec(_val, _groups, *, features):
        if features == ["invalid"]:
            raise ValueError("LATER_PHYSICAL_PARTSPEC_INVALID")
        return ("valid-spec",)
    host = SimpleNamespace(
        get_door_layout_cells=lambda: cells,
        _door_layout_cell_key=lambda c: f"{c.column_index}:{c.row_index}",
        door_layout_indicator_states={"0:0": valid, "0:1": deepcopy(valid)},
        _validate_door_layout_indicator_fit=lambda *_: None,
        door_layout_indicator_box_features={"0:0": [], "0:1": ["invalid"]},
        door_layout_indicator_door_features={"0:0": [], "0:1": []},
        _manufacturing_context=lambda *, draw_stock: None,
        _indicator_box_part_spec=spec,
        _export_authoritative_part=lambda *args: writes.append(args),
    )
    with pytest.raises(ValueError, match="LATER_PHYSICAL_PARTSPEC_INVALID"):
        gui.export_multi_door_indicator_box_parts(
            host, str(tmp_path), {"t": 2.0},
            export_box=True, export_door=False,
        )
    assert writes == [] and list(tmp_path.iterdir()) == []


def test_later_invalid_door_cell_identity_preflights_all_before_dxf(tmp_path):
    cells = (_cells()[0], DoorLayoutCell(True, 1, 200.0, 500.0, DoorFrameEdges()))
    writes = []
    host = SimpleNamespace(
        get_door_layout_cells=lambda: cells,
        _manufacturing_context=lambda *, draw_stock: None,
        _door_layout_part_spec=lambda c, values: (c, values),
        _export_authoritative_part=lambda *args: writes.append(args),
    )
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PHYSICAL_CELL_INDEX_INVALID"):
        gui.export_multi_door_layout_dxfs(host, str(tmp_path), {"t": 2.0})
    assert writes == [] and list(tmp_path.iterdir()) == []


def test_later_door_partspec_failure_precedes_first_dxf(tmp_path):
    writes = []
    def spec(cell, _val):
        if cell.row_index:
            raise ValueError("LATER_DOOR_PARTSPEC_INVALID")
        return ("valid",)
    host = SimpleNamespace(
        get_door_layout_cells=lambda: _cells()[:2],
        _manufacturing_context=lambda *, draw_stock: None,
        _door_layout_part_spec=spec,
        _export_authoritative_part=lambda *args: writes.append(args),
    )
    with pytest.raises(ValueError, match="LATER_DOOR_PARTSPEC_INVALID"):
        gui.export_multi_door_layout_dxfs(host, str(tmp_path), {"t": 2.0})
    assert writes == [] and list(tmp_path.iterdir()) == []
