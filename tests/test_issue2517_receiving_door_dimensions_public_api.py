"""#2517 Receiving Set/Bay Door Layout dimension commit uses public Engine."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.fold_designer_composition_receiving import (
    receiving_settings_ports,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _settings_ports():
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    events = []

    class Composition:
        app = SimpleNamespace(
            _phase6_input_snapshot={},
            submit_update_intent=lambda *args, **kwargs: events.append("commit"),
        )

        def receiving_adapter(self, namespace):
            return adapter

        def sync_receiving_current_bay(self, namespace):
            events.append("sync")

    return receiving_settings_ports(Composition(), None, 0), adapter, events


def test_receiving_dimensions_commit_calls_public_engine_door_cell_validation(monkeypatch):
    ports, adapter, events = _settings_ports()
    old = deepcopy(adapter.layout)
    seen = []
    original = manufacturing_api.door_layout_cells

    def check(columns, *, total_width, total_height):
        seen.append((columns, total_width, total_height))
        return original(columns, total_width=total_width, total_height=total_height)

    monkeypatch.setattr(manufacturing_api, "door_layout_cells", check)
    columns = ((400, (600, 1000)), (400, (1600,)))
    ports["dimensions"](800, 1600, 350, columns)

    assert seen == [(columns, 800, 1600)]
    saved = adapter.current_bay()
    assert saved["door_state"]["door_layout_columns"] == [
        [400, [600, 1000]], [400, [1600]],
    ]
    assert saved["door_state"]["multi_door_enabled"] is True
    assert old != adapter.layout
    assert events == ["sync", "commit"]


@pytest.mark.parametrize("columns", [
    ((True, (1600,)),),
    ((800, (True,)),),
    ((800, (600,)),),
    ((800, (float("nan"),)),),
])
def test_invalid_receiving_door_dimensions_cannot_partially_commit(columns):
    ports, adapter, events = _settings_ports()
    old = deepcopy(adapter.layout)
    old_selection = adapter.selection
    old_dirty = set(adapter._session_dirty_ids)

    with pytest.raises(ValueError):
        ports["dimensions"](800, 1600, 350, columns)

    assert adapter.layout == old
    assert adapter.selection == old_selection
    assert adapter._session_dirty_ids == old_dirty
    assert events == []


def test_receiving_dimensions_respects_public_engine_rejection_before_mutation(monkeypatch):
    ports, adapter, events = _settings_ports()
    old = deepcopy(adapter.layout)

    def refuse(*args, **kwargs):
        raise ValueError("ENGINE_DOOR_LAYOUT_REJECTED")

    monkeypatch.setattr(manufacturing_api, "door_layout_cells", refuse)
    with pytest.raises(ValueError, match="ENGINE_DOOR_LAYOUT_REJECTED"):
        ports["dimensions"](800, 1600, 350, ((800, (1600,)),))

    assert adapter.layout == old
    assert adapter._session_dirty_ids == set()
    assert events == []
