"""#2517: all three public Door Grid transactions reject corrupt fixed mm.

Auto remainder controls are not manufactured fixed dimensions. The original
Engine complete_partition remains the sole W/H remainder/topology solver.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.door_layout_numeric_transitions import (
    DoorLayoutColumnState,
    _normalized_auto_columns,
)


def _columns(*, width=400.125, heights=(450.25, 549.75),
             width_auto="false", height_auto=("false", "false")):
    return (
        DoorLayoutColumnState(
            width=width, width_auto=width_auto,
            heights=heights, height_auto=height_auto,
        ),
    )


def _all_transactions(columns):
    return (
        lambda: api.recompute_door_layout(
            columns, total_width=1000, total_height=1000,
            selected_key="0:0",
        ),
        lambda: api.validate_door_layout_width_commit(
            columns, 0, 1000, 400.125,
        ),
        lambda: api.validate_door_layout_height_commit(
            columns, 0, 0, 1000, 450.25,
        ),
    )


@pytest.mark.parametrize("bad", [
    True, False, None, 0, -1, "bad", "nan", "inf",
    float("nan"), float("inf"), float("-inf"), [],
])
@pytest.mark.parametrize("field", ["width", "height"])
def test_raw_fixed_dimension_rejected_by_all_three_public_api_entrypoints(
    bad, field,
):
    if field == "width":
        columns = _columns(width=bad)
    else:
        columns = _columns(heights=(450.25, bad))
    prior = repr(columns)
    for call in _all_transactions(columns):
        with pytest.raises((ValueError, TypeError)):
            call()
        assert repr(columns) == prior


def test_invalid_second_column_does_not_publish_partial_valid_topology():
    first = _columns()[0]
    second = DoorLayoutColumnState(
        width=True, width_auto=False, heights=(1000,), height_auto=(False,),
    )
    columns = (first, second)
    before = deepcopy(columns)
    for call in _all_transactions(columns):
        with pytest.raises(ValueError):
            call()
    assert columns == before


def test_inactive_auto_height_placeholder_does_not_fabricate_fixed_one_mm():
    columns = _columns(
        heights=(450.25, True), height_auto=("false", "true"),
    )
    before = deepcopy(columns)
    resolved = api.recompute_door_layout(
        columns, total_width=1000, total_height=1000, selected_key="0:0",
    )
    first, auto_column = resolved.columns
    assert first.heights == (450.25, 549.75)
    assert first.height_auto == (False, True)
    assert auto_column.width == 599.875
    assert auto_column.width_auto is True
    assert columns == before
    assert api.validate_door_layout_width_commit(
        columns, 0, 1000, 400.125,
    ).valid is True
    assert api.validate_door_layout_height_commit(
        columns, 0, 0, 1000, 450.25,
    ).valid is True


def test_auto_width_placeholder_is_replaced_by_original_engine_remainder():
    columns = _columns(
        width=True, heights=(False,), width_auto="true",
        height_auto=("true",),
    )
    before = deepcopy(columns)
    resolved = api.recompute_door_layout(
        columns, total_width=1000.125, total_height=800.75,
        selected_key="0:0",
    )
    assert len(resolved.columns) == 1
    column = resolved.columns[0]
    assert (column.width, column.heights) == (1000.125, (800.75,))
    assert column.width_auto and column.height_auto == (True,)
    assert columns == before


def test_valid_fractional_source_preserves_physical_ids_after_json_roundtrip():
    columns = _columns(heights=(450.125, 549.875))
    original = deepcopy(columns)
    result = api.recompute_door_layout(
        columns, total_width=1000, total_height=1000, selected_key="0:0",
    )
    assert result.width_completion.valid is True
    saved = json.loads(json.dumps([
        [c.width, list(c.heights)] for c in result.columns
    ]))
    cells = api.door_layout_cells(
        saved, total_width=1000, total_height=1000,
    )
    assert [api.door_layout_part_key(cell) for cell in cells] == [
        "door_c1_r1", "door_c1_r2", "door_c2_r1",
    ]
    assert [cell.start_height for cell in cells] == [
        450.125, 549.875, 1000,
    ]
    assert columns == original


def test_one_engine_source_validator_precedes_all_fixed_dimension_float_casts():
    normalizer = inspect.getsource(_normalized_auto_columns)
    assert '_positive_total("欄寬",' in normalizer
    assert '_positive_total("高度",' in normalizer
    engine = inspect.getsource(api.recompute_door_layout)
    assert "columns = _normalized_auto_columns(columns)" in engine
