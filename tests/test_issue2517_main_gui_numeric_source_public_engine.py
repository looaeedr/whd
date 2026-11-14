"""#2517 Main GUI source numeric parser uses public Engine and preserves signs."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as gui


FIELDS = {"w":"w_var","h":"h_var","d":"d_var","fw":"fw_z_var","t":"t_var","zl1":"zl1_var","zl2":"zl2_var","zr1":"zr1_var","zr2":"zr2_var","z_comp":"z_comp_var","yl1":"yl1_var","yr1":"yr1_var","ytop1":"ytop1_var","ybottom1":"ybottom1_var","door_gap_w":"door_gap_w_var","door_gap_h":"door_gap_h_var","door_fold_l":"door_fold_l_var","door_fold_r":"door_fold_r_var","door_fold_t":"door_fold_t_var","door_fold_b":"door_fold_b_var","base_plate_shrink_top":"base_plate_shrink_top_var","base_plate_shrink_bottom":"base_plate_shrink_bottom_var","base_plate_shrink_left":"base_plate_shrink_left_var","base_plate_shrink_right":"base_plate_shrink_right_var","base_plate_bend":"base_plate_bend_var"}
PHYSICAL = frozenset(("w", "h", "d", "t", "fw"))


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _source():
    data = {"w": "800.125", "h": "1600.5", "d": "350.75",
            "t": "2", "fw": "25.5"}
    data.update({
        key: "-3.125" if key in {
            "zl1", "z_comp", "door_fold_l", "base_plate_shrink_left"
        } else "19.25"
        for key in FIELDS if key not in PHYSICAL
    })
    return data


def _host(data):
    return SimpleNamespace(**{
        attr: Var(data[key]) for key, attr in FIELDS.items()
    })


def _engine(data):
    physical = api.normalize_operator_source_dimensions(data)
    rest = {key: value for key, value in data.items() if key not in physical}
    clean = api.normalize_operator_settings_updates(
        {key: 0.0 for key in rest}, rest,
    )
    return {**physical, **clean}


def test_gui_read_matches_all_25_headless_engine_numeric_results_and_is_detached():
    source = _source()
    before = deepcopy(source)
    result = gui.get_float_values(_host(source))
    assert result == _engine(source)
    assert len(result) == len(FIELDS) == 25
    assert all(type(value) is float for value in result.values())
    assert result["w"] == 800.125
    assert result["h"] == 1600.5
    assert result["d"] == 350.75
    assert result["zl1"] == -3.125
    assert result["base_plate_shrink_left"] == -3.125
    assert source == before


@pytest.mark.parametrize(("key", "bad"), [
    ("w", True), ("h", False), ("d", 0), ("w", "-1"),
    ("t", True), ("fw", 0), ("fw", "nan"), ("w", "inf"),
    ("door_gap_w", True), ("door_fold_l", False),
    ("base_plate_shrink_left", True), ("base_plate_bend", "nan"),
    ("zl1", "garbage"), ("z_comp", float("inf")),
])
def test_bad_numeric_source_fails_atomically_before_any_physical_part(key, bad):
    data = _source()
    data[key] = bad
    saved = deepcopy(data)
    with pytest.raises(ValueError):
        gui.get_float_values(_host(data))
    assert data == saved


def test_numeric_source_json_save_reload_retains_engine_parity():
    saved = json.loads(json.dumps(_source()))
    assert gui.get_float_values(_host(saved)) == _engine(saved)
    assert saved["door_fold_l"] == "-3.125"


def test_gui_does_not_coerce_raw_physical_or_fold_sources():
    source = inspect.getsource(gui.get_float_values)
    assert "manufacturing_api.normalize_operator_source_dimensions(raw)" in source
    assert "manufacturing_api.normalize_operator_settings_updates(" in source
    assert "float(self.w_var.get())" not in source
    assert "float(self.base_plate_shrink_left_var.get())" not in source
