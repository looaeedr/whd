"""#2517 Receiving Set/Bay live W/H/D uses public Engine source validation."""
from inspect import getsource
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.fold_designer_composition_receiving import (
    commit_receiving_current_bay_controls,
)


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def host(values, *, old=None):
    events = []
    requested = []
    current = {"width": 800.0, "height": 1600.0, "depth": 350.0}
    if old:
        current.update(old)

    def update_current_bay(**kwargs):
        requested.append(dict(kwargs))
        current.update(kwargs)
    adapter = SimpleNamespace(
        layout={"sets": [{"bays": [current]}]},
        current_bay=lambda: dict(current),
        update_current_bay=update_current_bay,
    )
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"},
        _phase6_sync_ready=True,
        _phase6_receiving_set_bay_guard=False,
        _phase6_initializing=False,
        v_w=Var(values["w"]), v_h=Var(values["h"]), v_d=Var(values["d"]),
        designer_workspace=SimpleNamespace(mark_dirty=lambda: events.append("dirty")),
    )
    owner = SimpleNamespace(
        app=app,
        receiving_adapter=lambda namespace: adapter,
        sync_receiving_current_bay=lambda namespace, **kwargs: events.append("sync"),
        sync_authoritative_derived_parts=lambda namespace: events.append("derived"),
    )
    return owner, adapter, requested, events


def test_real_live_bay_preserves_fractional_finished_dimensions():
    owner, adapter, calls, events = host(
        {"w": "820.25", "h": "1600.5", "d": "360.75"},
    )
    assert commit_receiving_current_bay_controls(owner, {}) is True
    assert calls == [{"width": 820.25, "height": 1600.5, "depth": 360.75}]
    assert adapter.current_bay() == calls[0]
    assert events == ["sync", "dirty", "derived"]
    assert owner.app._phase6_input_snapshot["receiving_layout"] == adapter.layout


@pytest.mark.parametrize("axis,bad", [
    ("w", False), ("w", 0), ("w", "nan"),
    ("h", -3), ("h", "inf"), ("h", "bad"),
    ("d", None), ("d", float("inf")),
])
def test_invalid_live_bay_source_fails_before_any_mutation(axis, bad):
    values = {"w": "820", "h": "1600", "d": "360"}
    values[axis] = bad
    owner, adapter, calls, events = host(values)
    original = adapter.current_bay()
    with pytest.raises(ValueError, match="包外尺寸"):
        commit_receiving_current_bay_controls(owner, {})
    assert calls == [] and events == []
    assert adapter.current_bay() == original
    assert "receiving_layout" not in owner.app._phase6_input_snapshot


def test_no_change_does_not_rederive_physical_parts():
    owner, _adapter, calls, events = host(
        {"w": "800", "h": "1600", "d": "350"},
    )
    assert commit_receiving_current_bay_controls(owner, {}) is True
    assert calls == [{"width": 800.0, "height": 1600.0, "depth": 350.0}]
    assert events == ["sync", "dirty"]


def test_gui_only_reads_controls_and_delegates_dimensions_to_engine():
    source = getsource(commit_receiving_current_bay_controls)
    assert source.count("manufacturing_api.normalize_operator_source_dimension(") == 3
    assert "original.get_int(" not in source
    assert "manufacturing_api.update_receiving_bay(" not in source
    assert "adapter.update_current_bay(**requested)" in source
