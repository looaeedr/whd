"""#2517 Receiving GUI physical Set/Bay count cannot be repaired by Tk."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, resize_receiving_sets,
    normalize_receiving_operator_connection_counts as original,
)
from gui_modules.application import receiving_set_bay_controls as controls
from gui_modules.application import receiving_multi_settings_window as multi


def test_public_engine_facade_and_root_share_exact_callable():
    assert api.normalize_receiving_operator_connection_counts is original
    assert ae_engine.normalize_receiving_operator_connection_counts is original
    assert "normalize_receiving_operator_connection_counts" in ae_engine.__all__


def test_real_canonical_layout_set_and_bay_counts_project_without_repair():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    layout = resize_receiving_sets(layout, set_count=2)
    counts = tuple(len(group["bays"]) for group in layout["sets"])
    assert counts == (3, 1)
    assert original(counts) == counts
    assert original(iter(counts)) == counts


@pytest.mark.parametrize("bad", [
    (), [], None, 0, 3, "2", b"2", {},
    (0,), (-1,), (True,), (False,), (2.0,),
    ("2",), (2, 0), (3, False), (3, 2.5),
    (1, float("nan")), (1, float("inf")), (1, None),
])
def test_rejected_count_does_not_repair_or_mutate_source(bad):
    before = deepcopy(bad)
    with pytest.raises(ValueError, match="Receiving"):
        original(bad)
    assert bad == before


@pytest.mark.parametrize("invalid", [0, -1, 2.0, True, "2", None])
def test_preview_rejects_before_creating_any_tk_window(invalid):
    class NoWindow:
        @staticmethod
        def Toplevel(*args):
            raise AssertionError("invalid physical count created a Tk window")
    with pytest.raises(ValueError, match="Receiving"):
        controls.open_receiving_layer_preview(
            object(), tk=NoWindow, ttk=object(), layer_index=0,
            connection_count=invalid, brand="士林",
            render_request=object(),
        )


@pytest.mark.parametrize("invalid", [0, -1, 1.5, True, "2", None])
def test_sketch_invalid_count_cannot_clear_canvas_or_emit_fake_bay(invalid):
    class NoCanvas:
        def delete(self, *_):
            raise AssertionError("invalid count cleared source sketch")
    with pytest.raises(ValueError, match="Receiving"):
        multi.paint_connected_bays(NoCanvas(), invalid)


@pytest.mark.parametrize("invalid", [(0,), (1, True), (1, -2), (), (2.5,)])
def test_row_refresh_rejects_before_touching_existing_tk_controls(invalid):
    class NoRows:
        _phase6_receiving_layer_rows = ("existing row",)
    layer_host = NoRows()
    group = SimpleNamespace(
        layer_host=layer_host, remove_layer_button=None,
    )
    with pytest.raises(ValueError, match="Receiving"):
        controls.refresh_receiving_layer_rows(
            group, tk=object(), ttk=object(), connection_counts=invalid,
            on_resize_connections=lambda *_: None,
            on_preview=lambda *_: None,
        )
    assert layer_host._phase6_receiving_layer_rows == ("existing row",)


def test_all_gui_count_routes_use_public_engine_and_do_not_truncate_counts():
    for body in (
        inspect.getsource(controls.open_receiving_layer_preview),
        inspect.getsource(controls.refresh_receiving_layer_rows),
        inspect.getsource(multi.paint_connected_bays),
        inspect.getsource(multi.open_multi_settings),
    ):
        assert "manufacturing_api.normalize_receiving_operator_connection_counts(" in body
        assert "max(1, int(" not in body
