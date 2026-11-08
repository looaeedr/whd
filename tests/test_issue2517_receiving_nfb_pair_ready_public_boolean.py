"""#2517: Receiving NFB paired partial export UI may not trust bool('false')."""
import inspect
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import receiving_multi_settings_window as gui


def _buttons(widget, text):
    items = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button) and child.cget("text") == text:
            items.append(child)
        items.extend(_buttons(child, text))
    return tuple(items)


PAIR_LABEL = "輸出內門＋底板 DXF（成對部分）"


def _open_window(status):
    root = tk.Tk()
    root.geometry("900x650+0+0")
    root.update()
    actions = []
    ports = {
        "state": lambda *args: {
            "base_partial_ready": status["value"],
            "can_submit": False, "can_copy": False,
            "can_undo": False, "can_restore": False,
        },
        "pair_partial_export": lambda *args: (
            actions.append(("export", args))
            or SimpleNamespace(
                inner_door_path="inner.dxf",
                base_plate_path="base.dxf",
                base_plate_paths=("base.dxf",),
                verified_v5_scope=None,
            )
        ),
    }
    win = gui.open_multi_settings(
        root, get_snapshot=lambda: {"active_mode": "set_bay"},
        get_switch=lambda: SimpleNamespace(
            connection_counts=lambda: (1,),
        ),
        switch_mode=lambda _mode: True,
        resize_connections=lambda *_: True,
        get_settings_ports=lambda _idx: {
            "select": lambda _bay: None,
        },
        get_nfb_transaction_ports=lambda: ports,
        get_brand=lambda: "士林",
    )
    root.update()
    assert win._receiving_multi_apply(0)
    selector = win._receiving_multi_setting_list
    selector.selection_set(1)
    selector.event_generate("<<ListboxSelect>>")
    root.update()
    assert win._receiving_multi_selected_setting["kind"] == "inner_door_layers"
    return root, win, actions


@pytest.mark.parametrize("raw", (
    "false", "off", "0", False, 0,
    "maybe", None, 2, float("nan"),
))
def test_real_tk_hides_nfb_paired_partial_export_for_unready_or_malformed_status(raw):
    state = {"value": raw}
    root = None
    try:
        root, win, actions = _open_window(state)
        assert _buttons(win._receiving_multi_settings_host, PAIR_LABEL) == ()
        assert actions == []
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.parametrize("initial", ("true", "on", 1, True))
def test_real_tk_revalidates_stale_partial_pair_before_folder_or_output(
    initial, monkeypatch,
):
    state = {"value": initial}
    file_dialog = []
    warnings = []
    monkeypatch.setattr(filedialog, "askdirectory",
                        lambda **kwargs: file_dialog.append(kwargs) or "/tmp/unused")
    monkeypatch.setattr(messagebox, "showwarning",
                        lambda *args, **kwargs: warnings.append((args, kwargs)))
    root = None
    try:
        root, win, actions = _open_window(state)
        buttons = _buttons(win._receiving_multi_settings_host, PAIR_LABEL)
        assert len(buttons) == 1
        state["value"] = "false"
        buttons[0].invoke()
        assert not file_dialog and not actions
        assert warnings
        assert "實體選型／提交驗證已失效" in warnings[-1][0][1]
    finally:
        if root is not None:
            root.destroy()


def test_real_tk_pair_action_still_delegates_authorized_true_to_existing_writer(
    monkeypatch,
):
    state = {"value": "true"}
    folders = []
    feedback = []
    monkeypatch.setattr(
        filedialog, "askdirectory",
        lambda **kw: folders.append(kw) or "/tmp/dxf-output",
    )
    monkeypatch.setattr(
        messagebox, "showinfo",
        lambda *args, **kw: feedback.append((args, kw)),
    )
    root = None
    try:
        root, win, actions = _open_window(state)
        buttons = _buttons(win._receiving_multi_settings_host, PAIR_LABEL)
        assert len(buttons) == 1
        buttons[0].invoke()
        assert len(folders) == len(actions) == len(feedback) == 1
        assert actions[0][0] == "export"
        assert actions[0][1] == (0, 0, "/tmp/dxf-output")
        assert "內門＋底板部分 DXF" in feedback[0][0][0]
    finally:
        if root is not None:
            root.destroy()


def test_gui_pair_visibility_and_click_reuse_one_public_engine_status_contract():
    source = inspect.getsource(gui.open_multi_settings)
    assert source.count(
        'manufacturing_api.normalize_operator_settings_boolean(\n'
    ) >= 2
    assert 'base_ready = bool(' not in source
    assert 'if not live_ports["state"](' not in source
    for raw in ("false", "off", "0", False, 0):
        assert api.normalize_operator_settings_boolean(raw) is False
    for raw in ("true", "on", "1", True, 1):
        assert api.normalize_operator_settings_boolean(raw) is True
