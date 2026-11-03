"""#2517: Receiving Door Hole Editor uses canonical Family/Bay/physical ID."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_part_adapters import door_layout_part_key as engine_door_layout_part_key
from gui_modules.application import door_layout_host_adapter as host_adapter
import gui


def _host(*, family="receiving", whd=None, columns=None, cabinet_type=False):
    snapshot = {
        "door_layout_columns": [(400.125, [600.25])],
        "door_fold_l": 19.0,
    }
    if cabinet_type:
        snapshot["cabinet_type"] = family
    else:
        snapshot["model"] = family
    if columns is not None:
        snapshot["door_layout_columns"] = columns
    dimensions = (
        {"w": 400.125, "h": 600.25, "d": "240.125"}
        if whd is None else whd
    )
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_box_whd=dimensions,
        designer_workspace=None,
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        get_door_layout_columns=lambda: pytest.fail(
            "Receiving must never use the unrelated legacy Door grid"
        ),
        w_var=SimpleNamespace(get=lambda: "999"),
        h_var=SimpleNamespace(get=lambda: "999"),
    )
    return host


@pytest.mark.parametrize("alias", (
    "受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ",
))
def test_active_receiving_door_layout_uses_registered_alias_and_live_bay(alias):
    host = _host(family=alias)
    source_before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    whd_before = deepcopy(host.fold_designer_app._phase6_box_whd)
    snapshot, projected = host_adapter._receiving_live_door_layout_source(host)
    assert snapshot is host.fold_designer_app._phase6_input_snapshot
    assert projected == whd_before and projected is not whd_before
    cells = host_adapter.get_door_layout_cells(host)
    assert len(cells) == 1
    assert (cells[0].start_width, cells[0].start_height) == (400.125, 600.25)
    assert manufacturing_api.door_layout_part_key(cells[0]) == (
        engine_door_layout_part_key(cells[0])
    ) == "door_c1_r1"
    assert host.fold_designer_app._phase6_input_snapshot == source_before
    assert host.fold_designer_app._phase6_box_whd == whd_before


def test_receiving_legacy_cabinet_type_alias_is_not_ignored():
    host = _host(family="ReCeIvInG", cabinet_type=True)
    assert host_adapter.get_door_layout_cells(host)[0].start_width == 400.125


def test_non_receiving_does_not_read_foreign_live_door_source():
    host = _host(family="金庫型")
    assert host_adapter._receiving_live_door_layout_source(host) is None


@pytest.mark.parametrize("broken", (
    {"w": True}, {"h": False}, {"d": True},
    {"w": float("nan")}, {"h": float("inf")}, {"d": float("-inf")},
    {"w": 0}, {"h": -0.5}, {"d": "not-a-length"},
))
def test_receiving_invalid_confirmed_whd_never_falls_back_to_old_gui(broken):
    dims = {"w": 400.125, "h": 600.25, "d": 240.125}
    dims.update(broken)
    host = _host(whd=dims)
    with pytest.raises(ValueError):
        host_adapter.get_door_layout_cells(host)
    assert host.fold_designer_app._phase6_box_whd is dims


@pytest.mark.parametrize("missing", ("w", "h", "d"))
def test_receiving_missing_one_bay_axis_must_not_use_legacy_header(missing):
    dims = {"w": 400.125, "h": 600.25, "d": 240.125}
    dims.pop(missing)
    with pytest.raises(ValueError, match="Bay W/H/D"):
        host_adapter.get_door_layout_cells(_host(whd=dims))


def test_receiving_missing_whole_bay_or_columns_must_not_use_old_gui():
    host = _host()
    host.fold_designer_app._phase6_box_whd = None
    with pytest.raises(ValueError, match="Bay W/H/D"):
        host_adapter.get_door_layout_cells(host)
    host = _host(columns=[])
    with pytest.raises(ValueError, match="門分割"):
        host_adapter.get_door_layout_cells(host)


def test_operator_editor_uses_actual_receiving_bay_raw_dimensions_and_engine_identity(
    monkeypatch,
):
    host = _host(family="receiving")
    source_before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    dimensions_before = deepcopy(host.fold_designer_app._phase6_box_whd)
    calls, payload, committed = [], {}, []
    host.fold_designer_app.submit_update_intent = (
        lambda *args, **kwargs: committed.append((args, kwargs))
    )
    host.last_unified_hole_editor = None
    host.door_layout_selected_var = SimpleNamespace(set=lambda value: calls.append(("select", value)))
    host.get_selected_door_layout_cell = lambda: host_adapter.get_door_layout_cells(host)[0]
    host._door_layout_cell_key = host_adapter._door_layout_cell_key
    host.get_float_values = lambda: {
        "w": 999.0, "h": 999.0, "d": 999.0,
        "fw": 29.0, "t": 2.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_b": 15.0,
    }
    def structural(cell, values):
        calls.append(("structural", dict(values)))
        return SimpleNamespace(width=700.0, height=720.0)
    host._door_layout_cell_result = structural
    def part(cell, values):
        calls.append(("spec", dict(values)))
        return object()
    host._door_layout_part_spec = part
    host._door_layout_baseline_scene = lambda cell, values: (None, "baseline source")
    host.door_layout_features = {}
    host.door_layout_indicator_states = {}
    host.door_layout_indicator_box_features = {}
    host.door_layout_indicator_door_features = {}
    host._door_layout_indicator_state_for_key = lambda key: {"mode": "none"}
    host._open_unified_hole_editor = lambda *args, **kwargs: payload.update(
        {"args": args, "kwargs": kwargs}
    )
    host._indicator_component_editor_contexts = lambda *args, **kwargs: None
    host.draw_door_layout_overview = lambda: None
    host.surface_features = {}
    host.workspace_controller = SimpleNamespace(
        part_features_snapshot=lambda: {},
        replace_part_features=lambda data: committed.append(("features", deepcopy(data))),
    )

    def editor_project(result, spec, **kwargs):
        calls.append(("Engine editor", kwargs["baseline_status"]))
        return SimpleNamespace(
            surface="engine-face", width=result.width, height=result.height,
            reference_guide="finished guide", door_indicator_context=object(),
            door_frame_edges=object(), baseline_scene=None,
            baseline_status=kwargs["baseline_status"],
        )
    monkeypatch.setattr(
        manufacturing_api, "project_operator_hole_editor_door_cell", editor_project,
    )
    original_key = manufacturing_api.door_layout_part_key
    def physical_key(cell):
        calls.append(("Engine physical key", (cell.column_index, cell.row_index)))
        return original_key(cell)
    monkeypatch.setattr(manufacturing_api, "door_layout_part_key", physical_key)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        pytest.fail("valid Receiving editor must open"))

    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, 0, 0)
    assert payload["args"][2:5] == ("engine-face", 700.0, 720.0)
    passed = dict(calls)["structural"]
    assert passed["w"] == 400.125 and passed["h"] == 600.25
    # A legal numeric string is validated by Engine, never GUI-floated.
    assert passed["d"] == "240.125"
    assert dict(calls)["spec"] == passed
    assert ("Engine physical key", (0, 0)) in calls
    assert host.door_layout_features == {}
    payload["kwargs"]["feature_list_override"].append("operator hole")
    assert host.door_layout_features == {}
    payload["kwargs"]["sync_callback"]()
    assert host.door_layout_features["0:0"] == ["operator hole"]
    assert host.surface_features["door_c1_r1"] == ["operator hole"]
    assert ("features", {"door_c1_r1": ["operator hole"]}) in committed
    assert host.fold_designer_app._phase6_input_snapshot["door_layout_features"] == {
        "0:0": ["operator hole"],
    }
    assert dimensions_before == host.fold_designer_app._phase6_box_whd
    assert source_before["model"] == host.fold_designer_app._phase6_input_snapshot["model"]


def test_editor_displays_invalid_live_bay_error_before_any_part_is_built(monkeypatch):
    host = _host(family="receiving", whd={
        "w": 400.125, "h": 600.25, "d": True,
    })
    selection = []
    errors = []
    host.last_unified_hole_editor = None
    host.door_layout_selected_var = SimpleNamespace(set=selection.append)
    host.get_selected_door_layout_cell = lambda: host_adapter.get_door_layout_cells(host)[0]
    host._door_layout_cell_key = host_adapter._door_layout_cell_key
    host.get_float_values = lambda: pytest.fail("invalid Bay must stop before settings")
    host._open_unified_hole_editor = lambda *args, **kwargs: pytest.fail(
        "invalid source must never open editor"
    )
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args: errors.append(args))
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, 0, 0)
    assert len(errors) == 1
    assert "開孔失敗" in errors[0][0]
    assert selection == ["0:0"]


def test_door_editor_does_not_duplicate_family_or_part_identity_policy():
    selector = inspect.getsource(host_adapter._receiving_live_door_layout_source)
    editor = inspect.getsource(gui.Phase6ApplicationHost.open_door_layout_cell_editor)
    assert "manufacturing_api.receiving_family_supports_back_panel_mode(" in selector
    assert "manufacturing_api.project_operator_receiving_settings_live_dimensions(" in selector
    assert "manufacturing_api.door_layout_part_key(cell)" in editor
    assert "float(whd[axis])" not in editor
    assert "door_c{cell.column_index" not in editor
