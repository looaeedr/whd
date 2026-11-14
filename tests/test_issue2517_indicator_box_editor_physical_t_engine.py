"""#2517 standalone IndicatorBox geometry requires canonical physical T source."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import indicator_editor_geometry as owner
from gui_modules.editors import hole_editor as gui


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def _host():
    return SimpleNamespace(
        indicator_l_var=Var("1"),
        indicator_layer_g_vars=[Var("2")],
    )


@pytest.mark.parametrize("raw", [
    True, False, 0, "0", -1, "-1", None, "",
    float("nan"), float("inf"), float("-inf"),
    "nan", "inf", "-inf", "not-a-thickness", [], {},
])
def test_invalid_headless_thickness_never_reaches_box_geometry(monkeypatch, raw):
    monkeypatch.setattr(owner.ae, "get_stretched_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "bad physical T must be rejected before any AE solve"
                        ))
    before = repr(raw)
    with pytest.raises((ValueError, TypeError)):
        api.resolve_indicator_box_editor_geometry((2,), thickness=raw)
    assert repr(raw) == before


@pytest.mark.parametrize("raw", [True, False, None, "bad", "nan", "0", -1])
def test_gui_hole_editor_rejects_same_bad_t_without_feature_geometry(
    monkeypatch, raw,
):
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *args: errors.append(args))
    monkeypatch.setattr(owner.ae, "get_stretched_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail("invalid T cannot resolve"))
    values = {"t": raw}
    before = repr(values)
    assert gui._indicator_box_context(_host(), values) is None
    assert errors and errors[-1][0] == "開孔失敗"
    assert repr(values) == before


@pytest.mark.parametrize("raw,expected", [
    (2, 2.0), (2.0, 2.0), ("2", 2.0),
    ("2.125", 2.125), (2.125, 2.125),
])
def test_valid_serialized_and_fractional_t_match_real_engine_geometry(raw, expected):
    original = json.loads(json.dumps({"t": raw}))
    accepted = api.normalize_operator_source_dimension(original["t"], field="t")
    assert accepted == expected
    direct = api.resolve_indicator_box_editor_geometry(
        (2,), thickness=original["t"]
    )
    gui_result = gui._indicator_box_context(_host(), original)
    assert gui_result is not None
    assert gui_result["width"] == pytest.approx(direct.width)
    assert gui_result["height"] == pytest.approx(direct.height)
    assert direct.width > 0 and direct.height > 0
    assert gui_result["baseline_status_text"] == direct.baseline_status
    assert original == {"t": raw}


def test_indicator_geometry_reuses_canonical_engine_t_source():
    source = inspect.getsource(owner.resolve_indicator_box_editor_geometry)
    assert "normalize_operator_source_dimension(thickness, field=\"t\")" in source
    assert "t = float(thickness)" not in source
