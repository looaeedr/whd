# -*- coding: utf-8 -*-
"""#2517 physical Receiving Bay dimension grouping is an Engine source decision."""
from copy import deepcopy
from inspect import getsource

import pytest
import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    project_receiving_bay_dimension_groups as owner,
)
from gui_modules.application import receiving_multi_settings_window as gui


def _three_bays():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )


def test_canonical_source_and_nonadjacent_equal_bay_sizes_remain_distinct():
    layout = update_receiving_bay(_three_bays(), set_index=0, bay_index=1, width=900)
    before = deepcopy(layout)
    bays = layout["sets"][0]["bays"]
    expected = (
        ((800.0, 1600.0, 350.0), (0, 2)),
        ((900.0, 1600.0, 350.0), (1,)),
    )
    assert api.project_receiving_bay_dimension_groups is owner
    assert ae_engine.project_receiving_bay_dimension_groups is owner
    assert "project_receiving_bay_dimension_groups" in ae_engine.__all__
    assert api.project_receiving_bay_dimension_groups(bays) == expected
    assert gui.dimension_group_summary(bays) == expected
    assert layout == before


def test_other_dimensions_and_legacy_numeric_texts_keep_physical_group_identity():
    bays = deepcopy(_three_bays()["sets"][0]["bays"])
    bays[1]["height"] = "1800"
    bays[2]["depth"] = 425.5
    before = deepcopy(bays)
    assert api.project_receiving_bay_dimension_groups(bays) == (
        ((800.0, 1600.0, 350.0), (0,)),
        ((800.0, 1800.0, 350.0), (1,)),
        ((800.0, 1600.0, 425.5), (2,)),
    )
    assert bays == before


@pytest.mark.parametrize("source", [None, 42, {}, "not bays", [None], [False], [{}]])
def test_invalid_physical_bay_sources_fail_closed(source):
    with pytest.raises(ValueError):
        api.project_receiving_bay_dimension_groups(source)


@pytest.mark.parametrize("axis", ["width", "height", "depth"])
@pytest.mark.parametrize("bad", [True, False, 0, -2, float("nan"), float("inf"), "bad"])
def test_invalid_physical_size_fails_without_modifying_unrelated_bays(axis, bad):
    bays = deepcopy(_three_bays()["sets"][0]["bays"])
    original_siblings = deepcopy((bays[0], bays[2]))
    bays[1][axis] = bad
    with pytest.raises(ValueError):
        api.project_receiving_bay_dimension_groups(bays)
    assert (bays[0], bays[2]) == original_siblings


def test_gui_is_a_thin_public_api_adapter(monkeypatch):
    code = getsource(gui.dimension_group_summary)
    assert "manufacturing_api.project_receiving_bay_dimension_groups(" in code
    assert "tuple(float(bay[field])" not in code
    source_bays = _three_bays()["sets"][0]["bays"]
    passed = []
    def fake(bays):
        passed.append(bays)
        return (((2.0, 3.0, 4.0), (1,)),)
    monkeypatch.setattr(api, "project_receiving_bay_dimension_groups", fake)
    assert gui.dimension_group_summary(source_bays) == (((2.0, 3.0, 4.0), (1,)),)
    assert passed == [source_bays]
