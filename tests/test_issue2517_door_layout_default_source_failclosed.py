"""#2517: Door-layout physical W/H must not be replaced with AE defaults."""
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from gui_modules.application import door_layout_host_adapter as adapter


def _value(value):
    return SimpleNamespace(get=lambda: value)


def _host(width, height, *, old=None):
    calls = []
    host = SimpleNamespace(
        w_var=_value(width),
        h_var=_value(height),
        door_layout_columns=list(old if old is not None else ()),
        _new_door_layout_column=lambda w, hs, **kw: (
            calls.append(("new", w, list(hs), kw))
            or {"width": w, "heights": list(hs), "width_auto": kw.get("width_auto", False)}
        ),
        _recompute_door_layout_remainders=lambda **kw: calls.append(("recompute", kw)),
        _remap_door_layout_owned_data=lambda **kw: calls.append(("remap", kw)),
        _on_door_layout_value_changed=lambda **kw: calls.append(("changed", kw)),
        door_layout_selected_var=SimpleNamespace(set=lambda value: calls.append(("selected", value))),
    )
    return host, calls


@pytest.mark.parametrize("field", ("w", "h"))
@pytest.mark.parametrize("invalid", (None, True, False, "", "broken", 0, -1,
                                     "nan", "inf", float("inf"), float("nan")))
def test_empty_layout_rejects_invalid_physical_source_without_state_mutation(field, invalid):
    host, calls = _host(
        invalid if field == "w" else 920,
        invalid if field == "h" else 440,
    )
    with pytest.raises(ValueError, match=field.upper() + " 包外尺寸"):
        adapter._ensure_door_layout_default(host)
    assert host.door_layout_columns == []
    assert calls == []


def test_empty_layout_uses_exact_fractional_operator_dimensions_not_ae_constants():
    host, calls = _host("920.25", "440.5")
    adapter._ensure_door_layout_default(host)
    assert host.door_layout_columns == [{
        "width": 920.25, "heights": [440.5], "width_auto": False,
    }]
    assert calls[0] == ("new", 920.25, [440.5], {})
    assert calls[1] == ("recompute", {"rebuild": False})


@pytest.mark.parametrize("invalid", (None, True, "", "nan", "-1", "invalid"))
def test_delete_final_manual_column_rejects_bad_height_before_identity_remap(invalid):
    original = {"width_var": "saved-cell", "width_auto": False}
    host, calls = _host(920, invalid, old=[original])
    with pytest.raises(ValueError, match="H 包外尺寸"):
        adapter.remove_door_layout_column(host, 0)
    assert host.door_layout_columns == [original]
    assert calls == []


def test_delete_last_column_regenerates_only_exact_valid_operator_height():
    host, calls = _host(
        920, "440.5", old=[{"width_auto": False, "saved_id": "door_c1_r1"}],
    )
    adapter.remove_door_layout_column(host, 0)
    assert host.door_layout_columns == [{
        "width": 0.0, "heights": [440.5], "width_auto": True,
    }]
    assert calls[0] == ("remap", {"operation": "delete_column", "column_index": 0})
    assert calls[1] == ("selected", "0:0")
    assert calls[2] == (
        "new", 0.0, [440.5], {"width_auto": True, "height_auto": [True]},
    )
    assert calls[3:] == [
        ("recompute", {"rebuild": True}),
        ("changed", {"recompute": False}),
    ]


def test_host_has_no_ae_manufacturing_defaults_or_private_import():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/door_layout_host_adapter.py").read_text(
                  encoding="utf-8"
              )
    assert "import ae_engine.ae" not in source
    assert "ae.W" not in source and "ae.H" not in source
    assert source.count("manufacturing_api.normalize_operator_source_dimension(") == 9


@pytest.mark.parametrize("column", (
    (True, [440]), (0, [440]), (float("nan"), [440]),
    (920, [True]), (920, [0]), (920, ["nan"]), (920, [400, "inf"]),
))
def test_explicit_multi_column_input_is_atomic_and_never_casts_invalid_physical_mm(column):
    previous = {"width_auto": False, "saved_id": "door_c1_r1"}
    host, calls = _host(920, 440, old=[previous])
    with pytest.raises(ValueError, match="包外尺寸"):
        adapter.set_door_layout_columns(host, [(920, [440]), column])
    assert host.door_layout_columns == [previous]
    assert calls == []


def test_explicit_multi_column_input_preserves_valid_fractional_physical_mm():
    host, calls = _host(1000, 500)
    adapter.set_door_layout_columns(host, [("920.25", ["440.5"]), ("79.75", [59.5])])
    assert host.door_layout_columns == [
        {"width": 920.25, "heights": [440.5], "width_auto": False},
        {"width": 79.75, "heights": [59.5], "width_auto": False},
    ]
    assert calls[0] == ("new", 920.25, [440.5], {})
    assert calls[1] == ("new", 79.75, [59.5], {})
    assert calls[2:] == [
        ("selected", "0:0"),
        ("recompute", {"rebuild": False}),
    ]


@pytest.mark.parametrize("column", (
    (True, [440]), (920, [True]), (920, ["nan"]),
))
def test_loaded_legacy_tuple_is_revalidated_before_material_preview(column):
    host, calls = _host(920, 440, old=[column])
    with pytest.raises(ValueError, match="包外尺寸"):
        adapter.get_door_layout_columns(host)
    assert host.door_layout_columns == [column]
    assert calls == []


@pytest.mark.parametrize("bad", (True, float("nan"), "inf", 0, "-1", None))
def test_door_layout_recompute_rejects_bad_wh_before_controller_or_ui_mutation(bad):
    host, calls = _host(bad, 440, old=[{"width_auto": False}])
    host._door_layout_controller_columns = lambda: calls.append(("controller",))
    with pytest.raises(ValueError, match="W / H 必須先填入有效數字"):
        adapter._recompute_door_layout_remainders(host, rebuild=False)
    assert calls == []
