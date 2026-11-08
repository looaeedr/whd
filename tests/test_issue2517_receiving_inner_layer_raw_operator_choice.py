"""#2517 Receiving operator inner-door layers: one Engine UI-to-physical gate."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import receiving_shared_settings as owner
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.application import receiving_set_bay_controls as gui


@pytest.mark.parametrize(("raw", "expected"), [
    ("1", 1), ("2", 2), (1, 1), (2, 2),
])
def test_public_operator_layer_choice_preserves_original_engine_integer_rule(raw, expected):
    assert (
        api.normalize_receiving_operator_inner_door_layer_choice
        is owner.normalize_receiving_operator_inner_door_layer_choice
        is ae_engine.normalize_receiving_operator_inner_door_layer_choice
    )
    assert api.normalize_receiving_operator_inner_door_layer_choice(raw) == expected
    assert type(api.normalize_receiving_operator_inner_door_layer_choice(raw)) is int


@pytest.mark.parametrize("bad", [
    True, False, 0, 3, 1.0, 2.0, -1, "01", "02", "1.0", "2.0",
    "", "true", None, float("nan"), [], {},
])
def test_invalid_raw_operator_layer_choice_fails_closed(bad):
    with pytest.raises(ValueError, match="內門層數"):
        api.normalize_receiving_operator_inner_door_layer_choice(bad)


def _layout():
    row = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    return api.edit_receiving_shared_setting_for_bays(
        row, set_index=0, bay_indices=(0,),
        kind="inner_door_layers", value=2,
    )


def test_engine_preview_and_committed_physical_bays_use_the_same_decoded_value():
    layout = _layout()
    before = deepcopy(layout)
    row = layout["sets"][0]
    for raw in ("1", "2"):
        target = api.normalize_receiving_operator_inner_door_layer_choice(raw)
        preview = api.project_receiving_shared_setting_group(
            row, 1, "inner_door_layers", preview_value=target,
        )
        expected = api.edit_receiving_shared_setting_for_bays(
            layout, set_index=0, bay_indices=(1,),
            kind="inner_door_layers", value=target,
        )
        assert preview[0] == target
        assert api.project_receiving_shared_setting_group(
            expected["sets"][0], 1, "inner_door_layers",
        )[0] == target
    assert layout == before


def test_real_tk_receiving_preview_and_apply_pass_only_engine_validated_layers(monkeypatch):
    import tkinter as tk
    from tkinter import ttk, messagebox

    layout = _layout()
    row = layout["sets"][0]
    source = deepcopy(row)
    changed = []
    warnings = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: warnings.append(args))
    root = tk.Tk()
    root.withdraw()
    try:
        panel = gui._build_receiving_settings_editor(
            root, tk=tk, ttk=ttk, ports={
                "row": lambda: row,
                "select": lambda _index: None,
                "change": lambda *args: changed.append(args),
            },
        )
        panel._receiving_kind_var.set("內門層數")
        panel._receiving_refresh()

        def descendants(w):
            for child in w.winfo_children():
                yield child
                yield from descendants(child)

        layer_picker = next(
            x for x in descendants(panel)
            if isinstance(x, ttk.Combobox)
            and tuple(x.cget("values")) == ("1", "2")
        )
        apply_button = next(
            x for x in descendants(panel)
            if isinstance(x, ttk.Button) and x.cget("text") == "編輯／套用"
        )
        panel._receiving_select_bay(1)
        layer_picker.set("2")
        panel._receiving_refresh(load_value=False)
        assert panel._receiving_matches == (0,)
        apply_button.invoke()
        assert changed == [("inner_door_layers", 2, [1])]
        assert not warnings
        assert row == source

        layer_picker.set("02")
        apply_button.invoke()
        assert changed == [("inner_door_layers", 2, [1])]
        assert warnings
        assert row == source
    finally:
        root.destroy()


def test_gui_has_no_local_int_conversion_of_physical_layer_choice():
    source = inspect.getsource(gui._build_receiving_settings_editor)
    assert "preview_value=int(value_var.get())" not in source
    assert "else int(value_var.get())" not in source
    assert source.count("manufacturing_api.normalize_receiving_operator_inner_door_layer_choice(") == 2
