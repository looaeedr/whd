"""#2517: physical filenames in the historical GUI PartSpec route are Engine-owned."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.sheetmetal_part_adapters import legacy_single_part_dxf_filename
from gui_modules.project import export_actions as gui


_NAMES = {
    "box_body": "box_body_z.dxf",
    "head": "end_cap_head.dxf",
    "tail": "end_cap_tail.dxf",
    "door": "door_unfold.dxf",
    "base_plate": "base_plate.dxf",
    "indicator_box": "indicator_box.dxf",
    "indicator_door": "indicator_door.dxf",
}


def _flags(**selected):
    return {part: selected.get(part, False) for part in _NAMES}


def _operator(value):
    return SimpleNamespace(get=lambda: value)


def test_engine_is_only_owner_of_all_seven_legacy_part_dxf_names():
    assert api.legacy_single_part_dxf_filename is legacy_single_part_dxf_filename
    assert ae_engine.legacy_single_part_dxf_filename is legacy_single_part_dxf_filename
    for kind, name in _NAMES.items():
        assert api.legacy_single_part_dxf_filename(kind) == name


@pytest.mark.parametrize("invalid", [
    True, False, 0, 1, None, "", "Door", "indicator", "door_c1_r1",
    "../door", "box_body_z.dxf", [], {},
])
def test_invalid_legacy_sheet_kind_is_not_a_manufacturing_filename(invalid):
    with pytest.raises(ValueError, match="LEGACY_SINGLE_PART_EXPORT_KIND_INVALID"):
        api.legacy_single_part_dxf_filename(invalid)


def test_all_seven_historical_gui_export_names_delegate_to_same_public_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(gui, "_export_selected_resolved_parts", lambda *_: None)
    monkeypatch.setattr(gui, "_collect_live_indicator_groups", lambda *a, **kw: (2,))
    name_calls = []
    actual_name = api.legacy_single_part_dxf_filename

    def record_name(part_kind):
        name_calls.append(part_kind)
        return actual_name(part_kind)

    monkeypatch.setattr(api, "legacy_single_part_dxf_filename", record_name)
    recorded = []
    host = SimpleNamespace(
        _manufacturing_context=lambda **kw: object(),
        _export_authoritative_part=lambda spec, filename, context:
            recorded.append((spec, Path(filename).name)),
        _box_body_part_spec=lambda val: "box-spec",
        _end_cap_part_spec=lambda val, *, is_tail: ("endcap-spec", is_tail),
        _single_door_part_spec=lambda val, **kw: "door-spec",
        _base_plate_part_spec=lambda val: "base-spec",
        _indicator_box_part_spec=lambda val, groups, *, features: "indicator-box-spec",
        _indicator_door_part_spec=lambda val, groups, *, features: "indicator-door-spec",
        multi_door_enabled_var=_operator(False),
        is_indicator_box_var=_operator(False),
        is_door_indicator_var=_operator(False),
        indicator_l_var=_operator("1"),
        indicator_layer_g_vars=[],
        surface_features={"indicator_box": [], "indicator_door": []},
    )
    output, errors = gui._export_selected_parts(
        host, tmp_path, {"t": 2.0}, _flags(**{name: True for name in _NAMES}), False,
    )
    assert errors == []
    assert output == list(_NAMES.values())
    assert [name for _, name in recorded] == output
    assert name_calls == list(_NAMES)
    gui_source = inspect.getsource(gui._export_selected_parts)
    assert "legacy_single_part_dxf_filename" in gui_source
    assert not any(filename in gui_source for filename in _NAMES.values())


def test_legacy_gui_door_real_engine_dxf_and_project_save_reload(tmp_path, monkeypatch):
    import phase6_project_file as project

    snapshot = {"model": "金庫型", "w": 500.0, "h": 600.0, "d": 350.0,
                "t": 2.0, "fw": 25.0}
    saved = project.write_project(
        tmp_path / "legacy-part-naming.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = project.read_project(saved)["snapshot"]
    assert restored["model"] == snapshot["model"]
    monkeypatch.setattr(gui, "_export_selected_resolved_parts", lambda *_: None)

    def engine_export(spec, filename, context):
        render = api.build_part_render_data(spec, context)
        path = api.save_part_render_data_dxf(
            render, filename, overwrite=True, verify_reopen=True,
        )
        assert api.verify_saved_part_render_data_dxf(render, path).ok

    host = SimpleNamespace(
        _manufacturing_context=lambda **kw: ManufacturingContext(
            resource_root=Path(__file__).resolve().parents[1],
        ),
        _export_authoritative_part=engine_export,
        _single_door_part_spec=lambda val, **kw: DoorPartSpec(
            width=val["w"], height=val["h"], thickness=val["t"],
            frame_width=val["fw"], model_name=val["model"], features=(),
        ),
        multi_door_enabled_var=_operator(False),
        is_indicator_box_var=_operator(False),
        is_door_indicator_var=_operator(False),
    )
    folder = tmp_path / "out"
    folder.mkdir()
    exported, errors = gui._export_selected_parts(
        host, folder, restored, _flags(door=True), False,
    )
    assert exported == ["door_unfold.dxf"]
    assert not errors
    dxfs = list(folder.glob("*.dxf"))
    assert len(dxfs) == 1 and dxfs[0].name == api.legacy_single_part_dxf_filename("door")
    reopened = ezdxf.readfile(dxfs[0])
    assert any(ent.dxf.layer == "CUTTING" for ent in reopened.modelspace())
