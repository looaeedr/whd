# -*- coding: utf-8 -*-
"""#2517 Engine-only Door grid numeric source transitions and GUI parity."""
import ast
from pathlib import Path

import pytest

from ae_engine import (
    DoorLayoutColumnState, DoorLayoutCommitValidation, DoorLayoutRecomputeResult,
    manufacturing_api,
)
from gui_modules.application import door_layout_controller as gui_adapter


def _columns():
    return (
        DoorLayoutColumnState(400.0, False, (500.0, 700.0), (False, True)),
        DoorLayoutColumnState(600.0, True, (1200.0,), (True,)),
    )


def test_headless_engine_recompute_keeps_authoritative_partition_and_auto_remainder():
    result = manufacturing_api.recompute_door_layout(
        (DoorLayoutColumnState(400, False, (500,), (False,)),),
        total_width=1000, total_height=1200, selected_key="9:9",
    )
    assert isinstance(result, DoorLayoutRecomputeResult)
    assert tuple((c.width, c.width_auto) for c in result.columns) == (
        (400.0, False), (600.0, True),
    )
    assert result.columns[0].heights == (500.0, 700.0)
    assert result.columns[0].height_auto == (False, True)
    assert result.selected_key == "1:0"


def test_headless_engine_width_and_height_guards_preserve_auto_owner():
    columns = _columns()
    yes = manufacturing_api.validate_door_layout_width_commit(
        columns, 1, 1000.0, 600.0,
    )
    changed = manufacturing_api.validate_door_layout_width_commit(
        columns, 1, 1000.0, 550.0,
    )
    assert isinstance(yes, DoorLayoutCommitValidation)
    assert yes.valid and yes.keep_auto
    assert changed.valid and not changed.keep_auto
    good_h = manufacturing_api.validate_door_layout_height_commit(
        columns, 0, 1, 1200.0, 700.0,
    )
    edited_h = manufacturing_api.validate_door_layout_height_commit(
        columns, 0, 1, 1200.0, 650.0,
    )
    assert good_h.valid and good_h.keep_auto
    assert edited_h.valid and not edited_h.keep_auto


@pytest.mark.parametrize("bad", [True, False, -1, float("nan"), float("inf"), 10**400])
def test_invalid_physical_dimension_fails_closed_before_partition(bad):
    with pytest.raises(ValueError):
        manufacturing_api.recompute_door_layout(
            _columns(), total_width=bad, total_height=1200, selected_key="0:0",
        )


@pytest.mark.parametrize("bad", [True, -1, 4, 1.0])
def test_invalid_operator_column_index_is_not_physical_bay_alias(bad):
    with pytest.raises(ValueError):
        manufacturing_api.validate_door_layout_width_commit(
            _columns(), bad, 1000, 600,
        )


def test_gui_adapter_calls_one_public_engine_numeric_port(monkeypatch):
    real = manufacturing_api.recompute_door_layout
    calls = []
    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(manufacturing_api, "recompute_door_layout", wrapped)
    output = gui_adapter.recompute_door_layout(
        _columns(), total_width=1000, total_height=1200,
        selected_key="0:1",
    )
    assert len(calls) == 1
    assert output == real(
        _columns(), total_width=1000, total_height=1200, selected_key="0:1",
    )


def test_gui_keeps_only_cell_presentation_mapping_no_partition_formula():
    module = Path(gui_adapter.__file__).read_text(encoding="utf-8")
    ast.parse(module)
    assert "complete_partition(" not in module
    assert "validate_door_layout_dimensions(" not in module
    assert "from .sheetmetal_part_adapters" not in module
    assert "manufacturing_api.recompute_door_layout(" in module
