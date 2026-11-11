"""#2517: production side MARKING GUI shares Engine source preflight with CHECK."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_fixed_plate_side_check_dxf as original
from gui_modules.project import export_actions
from tests.test_issue1503_side_only_mfg_gui import _host, _messages


def _snapshot():
    return {
        "model": "受電箱",
        "active_mode": "set_bay", "nfb_config_submitted": True,
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
    }


def test_check_and_manufacturing_read_same_public_engine_source_with_fractional_precision():
    snapshot = {
        **_snapshot(), "w": "800.125", "h": "1600.375",
        "d": 350.625, "t": "2.125",
    }
    before = deepcopy(snapshot)
    expected = ((800.125, 1600.375, 350.625), 2.125)
    assert api.receiving_ear_side_check_operator_inputs(snapshot) == expected
    assert original.receiving_ear_side_check_operator_inputs(snapshot) == expected
    assert snapshot == before
    assert json.loads(json.dumps(snapshot)) == snapshot


@pytest.mark.parametrize("field", ("w", "h", "d", "t"))
@pytest.mark.parametrize("bad", (
    True, None, 0, -1.25, "nan", "inf", "-inf", float("nan"),
    "not-a-number",
))
def test_engine_rejects_all_bad_side_dimensions_before_gui_picker_or_geometry(
    field, bad, monkeypatch, tmp_path,
):
    snapshot = _snapshot()
    snapshot[field] = bad
    before = deepcopy(snapshot)
    with pytest.raises((ValueError, TypeError), match="包外尺寸"):
        api.receiving_ear_side_check_operator_inputs(snapshot)
    host, events = _host(snapshot, object())
    _messages(monkeypatch, tmp_path, events)
    assert export_actions.export_receiving_ear_side_manufacturing_dxf(host) is None
    assert events[0] == "flush"
    assert "resolved" not in events and "folder" not in events
    assert any(isinstance(row, tuple) and row[0] == "error" for row in events)
    assert snapshot == before
    assert not list(tmp_path.iterdir())


def test_mfg_gui_forwards_validated_source_to_existing_final_exporter(
    monkeypatch, tmp_path,
):
    snapshot = _snapshot()
    snapshot.update({"w": "800.125", "h": "1600.25", "d": "350.375", "t": "2.5"})
    geometry = object()
    host, events = _host(snapshot, geometry)
    _messages(monkeypatch, tmp_path, events)
    emitted = []

    def candidate(snapshot_arg, geometry_arg, folder, **kwargs):
        emitted.append((snapshot_arg, geometry_arg, folder, kwargs))
        return SimpleNamespace(
            physical_ear_ids=("ear-L", "ear-R"), marking_lines_verified=6,
            output_paths=(("box_body:left_side", "left.dxf"),
                          ("box_body:right_side", "right.dxf")),
        )

    monkeypatch.setattr(
        export_actions.manufacturing_api,
        "export_receiving_ear_side_manufacturing_marking_dxf", candidate,
    )
    result = export_actions.export_receiving_ear_side_manufacturing_dxf(host)
    assert result is not None
    assert events[:3] == ["flush", "resolved", "folder"]
    assert len(emitted) == 1
    assert emitted[0][0] == snapshot
    assert emitted[0][1] is geometry
    assert emitted[0][2] == str(tmp_path)
    forwarded = dict(emitted[0][3])
    source_guard = forwarded.pop("pre_commit_guard")
    assert callable(source_guard)
    source_guard()
    assert forwarded == {
        "dimensions": (800.125, 1600.25, 350.375),
        "sheet_thickness": 2.5,
        "overwrite": False,
    }
    assert [row[0] for row in events if isinstance(row, tuple)] == ["success"]


def test_gui_mfg_has_no_separate_family_or_physical_numeric_rule():
    source = inspect.getsource(
        export_actions.export_receiving_ear_side_manufacturing_dxf
    )
    assert "manufacturing_api.receiving_ear_side_check_operator_inputs(" in source
    assert "float(snapshot[" not in source
    assert "resolve_live_cabinet_family" not in source
    owner = inspect.getsource(original.receiving_ear_side_check_operator_inputs)
    assert "normalize_operator_source_dimension(" in owner
