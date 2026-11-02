"""#2517 2D Door previews consume same physical source validator as Engine."""
import inspect
from types import SimpleNamespace

import pytest

from gui_modules.application.render_snapshots import (
    door_layout_overview_snapshot, single_door_render_snapshot,
)


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def host(**overrides):
    data = dict(
        w_var=Var("500.25"), h_var=Var("800.5"), t_var=Var("2.25"),
        fw_z_var=Var("25.75"), door_gap_w_var=Var("0"),
        door_gap_h_var=Var("3.5"), door_fold_l_var=Var("0"),
        door_fold_r_var=Var("15"), door_fold_t_var=Var("15"),
        door_fold_b_var=Var("15"), is_indicator_box_var=Var(False),
        is_door_indicator_var=Var(False),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("field,raw", [
    ("w_var", "nan"), ("w_var", True), ("w_var", 0),
    ("h_var", "inf"), ("h_var", -5), ("h_var", None),
    ("t_var", "nan"), ("t_var", False), ("t_var", "bad"),
    ("fw_z_var", "inf"), ("fw_z_var", -2),
])
def test_bad_single_door_physical_source_rejected_before_partspec(field, raw):
    calls = []
    app = host(**{field: Var(raw)})
    app._single_door_part_spec = lambda *a, **k: calls.append((a, k))
    with pytest.raises(ValueError, match="包外尺寸"):
        single_door_render_snapshot(app)
    assert calls == []


def test_single_door_passes_fractional_physical_w_h_t_fw_to_existing_part_spec():
    seen = []
    app = host()
    def witness(values, **kwargs):
        seen.append((dict(values), kwargs))
        raise RuntimeError("PART_SPEC_WITNESS")
    app._single_door_part_spec = witness
    with pytest.raises(RuntimeError, match="PART_SPEC_WITNESS"):
        single_door_render_snapshot(app)
    assert len(seen) == 1
    dimensions = seen[0][0]
    assert {key: dimensions[key] for key in ("w", "h", "t", "fw")} == {
        "w": 500.25, "h": 800.5, "t": 2.25, "fw": 25.75,
    }
    assert dimensions["door_gap_w"] == 0.0
    assert dimensions["door_fold_l"] == 0.0


@pytest.mark.parametrize("field,raw", [
    ("w_var", "nan"), ("w_var", True), ("w_var", 0),
    ("h_var", "inf"), ("h_var", -3), ("h_var", "bad"),
])
def test_multidoor_overview_returns_error_not_fabricated_physical_span(field, raw):
    app = host(**{field: Var(raw)})
    app.get_door_layout_columns = lambda: pytest.fail("must not read layout")
    payload = door_layout_overview_snapshot(app, {})
    assert isinstance(payload["error"], ValueError)
    assert "包外尺寸" in str(payload["error"])


def test_multidoor_overview_keeps_fractional_operator_span():
    app = host()
    app.get_door_layout_columns = lambda: ()
    app.get_door_layout_cells = lambda: ()
    app.get_float_values = lambda: {}
    app.door_layout_selected_var = Var("none")
    app._baseline_source_model = lambda: "金庫型"
    payload = door_layout_overview_snapshot(app, {})
    assert payload["error"] is None
    assert (payload["total_w"], payload["total_h"]) == (500.25, 800.5)


def test_gui_calls_existing_engine_physical_validator_without_local_formulas():
    source = inspect.getsource(single_door_render_snapshot)
    overview = inspect.getsource(door_layout_overview_snapshot)
    assert source.count("manufacturing_api.normalize_operator_source_dimension(") == 4
    assert overview.count("manufacturing_api.normalize_operator_source_dimension(") == 2
    for old in ('"w": float(host.w_var.get())', '"t": float(host.t_var.get())'):
        assert old not in source
