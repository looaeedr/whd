"""#2517 Door cell and independent Indicator-Box DXF use raw Engine physical source."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import manufacturing_adapter as adapter
from gui_modules.project import export_actions as export


CELL = SimpleNamespace(column_index=0, row_index=0,
                       start_width=800.0, start_height=1600.0, edges=None)
VAL = {"w": 800.0, "h": 1600.0, "t": 2.0, "fw": 25.0}


def _state(mode="indicator_box", **kwargs):
    state = {"mode": mode, "layers": 2, "groups": [3, 2, 2, 2, 2, 2],
             "offset_x": 1.25, "offset_y": -2.5, "is_box_dist": False}
    state.update(kwargs)
    return state


def _host(raw, *, display=None):
    visited = []
    # Display may have already substituted incorrect physical groups.
    normalized = display if display is not None else _state()
    host = SimpleNamespace(
        door_layout_indicator_states={"0:0": raw},
        _door_layout_cell_key=lambda cell: "0:0",
        _door_layout_indicator_state_for_key=lambda key: normalized,
        door_layout_features={"0:0": ["operator-feature"]},
        _baseline_source_model=lambda: "金庫型",
        _manual_corner_policy=lambda *a: None,
        _door_material_frame_width=lambda fw, t: fw,
        _door_part_spec_from_values=lambda vals, **kw: visited.append(("door", vals, kw)) or kw,
        get_door_layout_cells=lambda: (CELL,),
        _manufacturing_context=lambda *, draw_stock: "engine-context",
        _validate_door_layout_indicator_fit=lambda cell, state, vals:
            visited.append(("fit", state, vals)),
        _indicator_box_part_spec=lambda vals, groups, *, features:
            visited.append(("box", groups, features)) or "box-spec",
        _indicator_door_part_spec=lambda vals, groups, *, features:
            visited.append(("small-door", groups, features)) or "small-door-spec",
        _export_authoritative_part=lambda spec, path, ctx:
            visited.append(("export", spec, ctx)),
        door_layout_indicator_box_features={"0:0": ["box-hole"]},
        door_layout_indicator_door_features={"0:0": ["small-door-hole"]},
    )
    return host, visited


@pytest.mark.parametrize("mode", ("indicator_box", "indicator", "none"))
def test_selected_cell_door_part_spec_uses_exact_engine_groups_offsets(mode):
    state = _state(mode)
    before = deepcopy(state)
    host, visited = _host(state, display=_state(groups=[8, 8, 2, 2, 2, 2]))
    result = adapter._door_layout_part_spec(host, CELL, VAL)
    assert state == before
    assert result["indicator_hole"] is not None if mode == "indicator_box" else result["indicator_hole"] is None
    assert result["door_indicator"] == ((3, 2) if mode == "indicator" else None)
    assert result["door_indicator_offset"] == (1.25, -2.5) if mode != "none" else result["door_indicator_offset"] == (0.0, 0.0)
    assert len(visited) == 1 and visited[0][0] == "door"
    assert result["features"] == ["operator-feature"]


@pytest.mark.parametrize("invalid", (
    {"layers": True}, {"layers": 1.5}, {"layers": 7},
    {"groups": [False, 2]}, {"groups": [3.5, 2]},
    {"groups": [0, 2]}, {"groups": [9, 2]},
    {"layers": 3, "groups": [2]},
    {"offset_x": float("nan")}, {"offset_y": "not-a-number"},
    {"mode": "unsupported"},
))
def test_corrupt_real_cell_cannot_generate_door_or_indicator_dxfs(tmp_path, invalid):
    raw = _state(**invalid)
    host, visited = _host(raw)
    with pytest.raises(ValueError):
        adapter._door_layout_part_spec(host, CELL, VAL)
    assert visited == []
    with pytest.raises(ValueError):
        export.export_multi_door_indicator_box_parts(host, str(tmp_path), VAL)
    assert visited == []
    assert list(tmp_path.iterdir()) == []


def test_independent_valid_box_and_door_export_share_engine_groups(tmp_path):
    host, visited = _host(_state(groups=[2, 3, 2, 2, 2, 2]),
                          display=_state(groups=[8, 8, 2, 2, 2, 2]))
    exported = export.export_multi_door_indicator_box_parts(host, str(tmp_path), VAL)
    assert exported == ["indicator_box_c1_r1.dxf", "indicator_door_c1_r1.dxf"]
    assert [call[1] for call in visited if call[0] in ("box", "small-door")] == [(2, 3), (2, 3)]
    assert [call[1] for call in visited if call[0] == "export"] == ["box-spec", "small-door-spec"]
    assert host.door_layout_indicator_states["0:0"]["groups"][:2] == [2, 3]


def test_missing_real_cell_does_not_export_repaired_display(tmp_path):
    host, visited = _host(_state())
    host.door_layout_indicator_states = {}
    assert adapter._door_layout_part_spec(host, CELL, VAL)["indicator_hole"] is None
    assert export.export_multi_door_indicator_box_parts(host, str(tmp_path), VAL) == []
    assert len([call for call in visited if call[0] == "export"]) == 0


def test_gui_export_and_door_part_spec_have_no_manufacturing_group_cast():
    a = inspect.getsource(adapter._door_layout_part_spec)
    b = inspect.getsource(export.export_multi_door_indicator_box_parts)
    for source in (a, b):
        assert "project_operator_door_cell_indicator_manufacturing_source(" in source
        assert "max(1, min(6, int(" not in source
        assert "tuple(int(v)" not in source
