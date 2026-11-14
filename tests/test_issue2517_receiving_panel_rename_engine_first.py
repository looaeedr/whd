"""#2517: Receiving panel-name GUI delegates physical identity before indexing."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _adapter():
    source = resize_receiving_bays(
        new_receiving_layout(width=820.25, height=1600.5, depth=350.75),
        set_index=0, bay_count=2,
    )
    return ReceivingSetBayAdapter(source)


@pytest.mark.parametrize("set_index,bay_index", [
    (True, 0), (False, 0), (0, True), (0, False),
    ("0", 0), (0, "0"), (0.0, 0), (0, 1.0),
    (-1, 0), (0, -1), (1, 0), (0, 2),
])
def test_invalid_rename_target_is_rejected_by_engine_before_gui_state_changes(
    monkeypatch, set_index, bay_index,
):
    adapter = _adapter()
    before = deepcopy((adapter.layout, adapter.selection, adapter._session_dirty_ids))
    original = api.rename_receiving_panel
    seen = []

    def tracked(layout, *, set_index, bay_index, panel_name):
        seen.append((set_index, bay_index, panel_name))
        return original(
            layout, set_index=set_index, bay_index=bay_index,
            panel_name=panel_name,
        )

    monkeypatch.setattr(api, "rename_receiving_panel", tracked)
    with pytest.raises(IndexError, match="Receiving .*_index"):
        adapter.rename_bay(set_index, bay_index, "新盤名")
    assert seen == [(set_index, bay_index, "新盤名")]
    assert (adapter.layout, adapter.selection, adapter._session_dirty_ids) == before


def test_engine_preempts_any_python_indexing_for_invalid_caller(monkeypatch):
    adapter = _adapter()
    before = deepcopy(adapter.layout)
    seen = []

    def rejected(*args, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("ENGINE VALIDATION FIRST")

    monkeypatch.setattr(api, "rename_receiving_panel", rejected)
    with pytest.raises(RuntimeError, match="ENGINE VALIDATION FIRST"):
        adapter.rename_bay(True, object(), "盤名")
    assert seen[0]["set_index"] is True
    assert adapter.layout == before
    assert adapter._session_dirty_ids == set()


def test_legitimate_rename_commits_only_named_bay_and_preserves_physical_identity():
    adapter = _adapter()
    original = adapter.layout
    selection = adapter.selection
    original_ids = [
        bay["stable_id"] for bay in original["sets"][0]["bays"]
    ]
    assert adapter.rename_bay(0, 1, "分電盤") is True
    updated = adapter.layout
    assert adapter.selection == selection
    assert updated["sets"][0]["bays"][0] == original["sets"][0]["bays"][0]
    assert [b["stable_id"] for b in updated["sets"][0]["bays"]] == original_ids
    assert updated["sets"][0]["bays"][1]["panel_name"] == "分電盤"
    assert adapter._session_dirty_ids == {original_ids[1]}
    assert adapter.rename_bay(0, 1, "分電盤") is False
    assert api.normalize_receiving_layout(
        json.loads(json.dumps(updated))
    ) == updated
    for field in ("width", "height", "depth"):
        assert updated["sets"][0]["bays"][1][field] == original["sets"][0]["bays"][1][field]


def test_gui_rename_calls_public_transaction_before_any_physical_bay_indexing():
    source = inspect.getsource(ReceivingSetBayAdapter.rename_bay)
    assert source.index("manufacturing_api.rename_receiving_panel(") < source.index(
        'self._layout["sets"][set_index]["bays"][bay_index]'
    )
