"""#2517 original Door grid physical Indicator owner persists through Save→Reload."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, DoorLayoutCell
from gui_modules.application import fold_designer_snapshot_projection as gui_snapshot
from gui_modules.project import export_actions as gui_export
from tests.test_issue2517_receiving_base_plate_snapshot_alias_save_reload import SnapshotHost
import phase6_project_file as project


def _indicator():
    return {"mode": "indicator_box", "layers": 1, "groups": [2],
            "offset_x": 1.25, "offset_y": -2.5, "is_box_dist": False}


def test_original_engine_maps_legacy_indicator_cell_coordinate_to_real_door_id():
    original = {(0, 0): _indicator(), (1, 2): _indicator()}
    before = deepcopy(original)
    canonical = api.project_operator_door_layout_indicator_snapshot_states(original)
    assert set(canonical) == {"0:0", "1:2"}
    assert canonical["0:0"]["groups"] == [2]
    assert canonical["0:0"]["offset_x"] == pytest.approx(1.25)
    assert canonical["1:2"]["mode"] == "indicator_box"
    assert original == before


@pytest.mark.parametrize("bad", (
    "broken", "(0, 0)", "0.5:0", "-1:0", True, 0, None,
    (True, 0), (0.5, 0), (0, -1), (0, 0, 0),
))
def test_invalid_persisted_indicator_owner_cannot_become_invisible_holes(bad):
    saved = {bad: _indicator()}
    old = deepcopy(saved)
    with pytest.raises(ValueError, match="門格指示燈來源身分無效"):
        api.project_operator_door_layout_indicator_snapshot_states(saved)
    assert saved == old


@pytest.mark.parametrize("duplicate", ("0:0", "00:0", "0:00"))
def test_tuple_and_text_alias_cannot_silently_override_saved_lamp(duplicate):
    first = _indicator()
    second = {**_indicator(), "groups": [3]}
    saved = {(0, 0): first, duplicate: second}
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="門格指示燈來源身分衝突：0:0"):
        api.project_operator_door_layout_indicator_snapshot_states(saved)
    assert saved == before


def test_real_gui_snapshot_project_reload_and_same_owner_engine_dxf_reopen(tmp_path):
    original = {(0, 0): _indicator()}
    before = deepcopy(original)
    host = SnapshotHost("金庫型", {"model": "金庫型"})
    host.door_layout_indicator_states = original
    created = gui_snapshot._snapshot_base_state(host)
    assert set(created["door_layout_indicator_states"]) == {"0:0"}
    target = project.write_project(
        tmp_path / "indicator-physical-identity.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": created},
    )
    loaded = project.read_project(target)["snapshot"]
    restored = loaded["door_layout_indicator_states"]
    assert set(restored) == {"0:0"}
    state = api.project_operator_door_cell_indicator_manufacturing_source(restored["0:0"])
    assert state["mode"] == "indicator_box"
    assert tuple(state["groups"][:state["layers"]]) == (2,)
    assert state["offset_x"] == pytest.approx(1.25)
    assert state["offset_y"] == pytest.approx(-2.5)

    cell = DoorLayoutCell(0, 0, 400.0, 500.0, DoorFrameEdges())
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    published = []

    def export_real_verified(spec, filepath, _context):
        render = api.build_part_render_data(spec, _context)
        assert render.scene is not None and render.material is not None
        saved = api.save_part_render_data_dxf(
            render, filepath, overwrite=True, verify_reopen=True,
        )
        assert api.verify_saved_part_render_data_dxf(render, saved).ok
        published.append(Path(saved))

    adapter = SimpleNamespace(
        get_door_layout_cells=lambda: (cell,),
        _door_layout_cell_key=lambda _: "0:0",
        door_layout_indicator_states=restored,
        _validate_door_layout_indicator_fit=lambda *_: None,
        door_layout_indicator_box_features={"0:0": []},
        door_layout_indicator_door_features={"0:0": []},
        _manufacturing_context=lambda *, draw_stock: context,
        _indicator_box_part_spec=lambda val, groups, *, features:
            api.build_indicator_box_operator_part_spec(val, groups, features=features),
        _export_authoritative_part=export_real_verified,
    )
    out_dir = tmp_path / "real-verified-dxf"
    out_dir.mkdir()
    exported = gui_export.export_multi_door_indicator_box_parts(
        adapter, str(out_dir), {"model": "金庫型", "t": 2.0},
        export_box=True, export_door=False,
    )
    assert exported == ["indicator_box_c1_r1.dxf"]
    assert published == [out_dir / exported[0]]
    assert published[0].is_file()
    assert any(obj.dxf.layer == "CUTTING"
               for obj in ezdxf.readfile(published[0]).modelspace())
    assert original == before


def test_bad_saved_indicator_owner_fails_before_gui_can_publish_snapshot():
    invalid = {"not-a-door-cell": _indicator()}
    before = deepcopy(invalid)
    host = SnapshotHost("受電箱", {"model": "受電箱"})
    host.door_layout_indicator_states = invalid
    with pytest.raises(ValueError, match="門格指示燈來源身分無效"):
        gui_snapshot._snapshot_base_state(host)
    assert invalid == before
