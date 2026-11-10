"""#2517 Receiving physical Bay sketch cannot coerce raw W/H in GUI."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import receiving_operator_projection as owner
from gui_modules.application.receiving_multi_settings_window import paint_connected_bays


class _Canvas:
    def __init__(self):
        self.operations = []
    def winfo_width(self):
        return 600
    def cget(self, name):
        assert name == "width"
        return "600"
    def delete(self, tag):
        self.operations.append(("delete", tag))
    def create_rectangle(self, *args, **kwargs):
        self.operations.append(("rect", args))
        return len(self.operations)
    def create_line(self, *args, **kwargs):
        self.operations.append(("line", args))
        return len(self.operations)
    def create_text(self, *args, **kwargs):
        self.operations.append(("text", args))
        return len(self.operations)
    def bbox(self, item_id):
        return (20, 20, 100, 40)


def test_public_sketch_query_is_same_engine_owner_for_gui_and_headless():
    assert api.project_receiving_operator_bay_sketch_dimensions is (
        owner.project_receiving_operator_bay_sketch_dimensions
    )
    assert ae_engine.project_receiving_operator_bay_sketch_dimensions is (
        owner.project_receiving_operator_bay_sketch_dimensions
    )
    assert "project_receiving_operator_bay_sketch_dimensions" in ae_engine.__all__


def test_real_saved_bay_and_legacy_tuple_preserve_exact_fractional_mm():
    source = api.operator_new_receiving_layout(width=800, height=1600, depth=350)
    bay = source["sets"][0]["bays"][0]
    bay = {**bay, "width": 820.25, "height": 1600.5}
    original = deepcopy(bay)
    expect_seam = api.project_receiving_operator_bay_door_split_ratio(bay)
    assert api.project_receiving_operator_bay_sketch_dimensions(bay) == (
        820.25, 1600.5, expect_seam
    )
    default_seam = api.project_receiving_operator_bay_door_split_ratio(None)
    assert api.project_receiving_operator_bay_sketch_dimensions(
        (820.25, 1600.5, 350.75)
    ) == (820.25, 1600.5, default_seam)
    assert json.loads(json.dumps(bay)) == bay
    assert bay == original


@pytest.mark.parametrize(("bad","axis"), [
    (True, 0), (False, 1), (0, 0), (-3.5, 1),
    (float("nan"), 0), (float("inf"), 1),
    ("not-a-number", 0), (None, 1),
])
@pytest.mark.parametrize("source_type", ("tuple", "mapping"))
def test_invalid_raw_physical_dimensions_rejected_without_coercion(
    bad, axis, source_type,
):
    dims = [820.25, 1600.5]
    dims[axis] = bad
    source = (
        {"width": dims[0], "height": dims[1]}
        if source_type == "mapping" else tuple(dims)
    )
    with pytest.raises(ValueError):
        api.project_receiving_operator_bay_sketch_dimensions(source)


@pytest.mark.parametrize("bad", [(), (800,), {"width": 800}, False, 800, "invalid"])
def test_incomplete_physical_bay_source_fails_closed(bad):
    with pytest.raises(ValueError):
        api.project_receiving_operator_bay_sketch_dimensions(bad)


def test_family_only_schematic_still_available_without_saved_bay():
    expected = api.receiving_default_preview_dimensions({})
    projected = api.project_receiving_operator_bay_sketch_dimensions(None)
    assert projected == (
        expected[0], expected[1],
        api.project_receiving_operator_bay_door_split_ratio(None),
    )


def test_gui_rejects_malformed_second_bay_before_clearing_previous_canvas():
    canvas = _Canvas()
    good = {"width": 800, "height": 1600}
    bad = (True, 1600)
    with pytest.raises(ValueError):
        paint_connected_bays(canvas, 2, bay_dimensions=(good, bad))
    assert canvas.operations == []
    assert not hasattr(canvas, "_receiving_bay_hitboxes")


def test_valid_legacy_bay_values_draw_two_physical_bays_from_engine():
    canvas = _Canvas()
    count = paint_connected_bays(
        canvas, 2, selected=(0,), bay_dimensions=((800, 1600), (820.25, 1500.5)),
    )
    assert count == 2
    assert canvas.operations[0] == ("delete", "all")
    assert len(canvas._receiving_bay_hitboxes) == 2
    assert canvas._receiving_selected_bays == frozenset({0})


def test_gui_never_decodes_physical_dimensions_or_door_seam():
    text = inspect.getsource(paint_connected_bays)
    assert "manufacturing_api.project_receiving_operator_bay_sketch_dimensions(" in text
    assert "float(item[" not in text
    assert "manufacturing_api.project_receiving_operator_bay_door_split_ratio(" not in text
    assert text.index("project_receiving_operator_bay_sketch_dimensions(") < text.index('canvas.delete("all")')
