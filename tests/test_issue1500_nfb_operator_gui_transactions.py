"""#1500 real Tk operator controls -> one existing verified NFB transaction authority.

Buttons must use the highlighted Bay indices, recheck live source state at
click, warn with physical preview, permit cancel with zero change, and refresh
submit/copy/restore/Undo state without manufacturing a fresh NFB source.
"""
from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

from gui_modules.application.receiving_multi_settings_window import (
    open_multi_settings,
)
from gui_modules.application import receiving_multi_settings_window as view


def _buttons(host):
    stack = [host]
    found = {}
    while stack:
        widget = stack.pop()
        if isinstance(widget, ttk.Button):
            found[widget.cget("text")] = widget
        stack.extend(widget.winfo_children())
    return found


def _select_inner(win, root):
    listing = win._receiving_multi_setting_list
    listing.selection_set(1)
    listing.event_generate("<<ListboxSelect>>")
    root.update()


def _click_bay(win, root, index):
    canvas = win._receiving_multi_canvas
    x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[index]
    canvas.event_generate(
        "<Button-1>", x=int((x0 + x1) / 2),
        y=int((y0 + y1) / 2),
    )
    root.update()


def test_gui_submit_cancel_copy_restore_undo_reuses_physical_bay_authority(monkeypatch):
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    saved = set()
    ready = {0, 1}  # Real evidence would be staged separately, never guessed by UI.
    transactions = []
    warnings = []
    seen_previews = []
    undo_stack = []
    answers = iter((False, True, True, True, True))

    def askyesno(_title, message, *, parent):
        assert parent is win
        seen_previews.append(message)
        return next(answers)

    monkeypatch.setattr(view.messagebox, "askyesno", askyesno)
    monkeypatch.setattr(view.messagebox, "showwarning",
                        lambda _title, message, *, parent: warnings.append(message))

    def state(si, bi, selected=()):
        assert si == 0
        return {
            "submitted": bi in saved,
            "can_submit": bi in ready and bi not in saved,
            "can_copy": tuple(selected) == (0, 1)
                        and 0 in saved and 1 in ready and 1 not in saved,
            "can_restore": bi in saved,
            "can_undo": bool(undo_stack),
            "reason": "真來源待核對" if bi not in ready else "",
            "base_partial_ready": False,
        }

    def preview(action, ids):
        return SimpleNamespace(
            action=action, target_bay_ids=tuple(f"bay-{i}" for i in ids),
            impacted_parts=("inner_door:upper:panel",),
            held_parts=("base_plate:upper",),
            dependency_warnings=("PAD 尚未驗證",),
        )

    def transition(action, indices, confirm, mutator):
        before = set(saved)
        accepted = confirm(preview(action, indices))
        transactions.append((action, tuple(indices), accepted))
        if not accepted:
            assert saved == before
            return False
        undo_stack.append(before)
        mutator()
        return saved != before

    def submit(si, ids, confirm):
        assert si == 0 and tuple(ids) == (0,)
        assert state(si, 0, ids)["can_submit"]
        return transition("SUBMIT", ids, confirm, lambda: saved.add(0))

    def copy(si, ids, confirm):
        assert si == 0 and tuple(ids) == (0, 1)
        assert state(si, 0, ids)["can_copy"]
        return transition("COPY_SUBMIT", ids, confirm, lambda: saved.add(1))

    def restore(si, ids, confirm):
        assert si == 0 and all(i in saved for i in ids)
        return transition("RESTORE_UNCONFIGURED", ids, confirm,
                          lambda: saved.difference_update(ids))

    def undo():
        before = undo_stack.pop()
        saved.clear()
        saved.update(before)
        transactions.append(("UNDO", (), True))
        return True

    ports = {
        "state": state, "submit": submit, "copy": copy,
        "restore": restore, "undo": undo,
        "manifest": lambda _si, bi: (
            {"status": "BLOCKED", "reason": "測試未放行製造"}
            if bi in saved else {"status": "LEGACY"}
        ),
    }
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: True,
            get_settings_ports=lambda _si: {
                "row": lambda: {"bays": [
                    {"stable_id": "bay-0"}, {"stable_id": "bay-1"},
                ]},
                "select": lambda _bi: None,
            },
            get_nfb_transaction_ports=lambda: ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        _select_inner(win, root)
        host = win._receiving_multi_settings_host
        buttons = _buttons(host)
        assert buttons["確認套用 NFB"].instate(("!disabled",))
        assert buttons["複製至其他連"].instate(("disabled",))
        assert buttons["還原為未配置"].instate(("disabled",))
        # The operator explicitly retired the per-Bay unlink action.
        # Removing it must not remove the existing highlighter/link/transaction controls.
        assert "解除本連連動" not in buttons
        assert "連動選取的連" in buttons
        assert "確認套用 NFB" in buttons

        # Cancel must never submit, nor consume the capability.
        buttons["確認套用 NFB"].invoke()
        assert saved == set()
        assert _buttons(host)["確認套用 NFB"].instate(("!disabled",))
        _buttons(host)["確認套用 NFB"].invoke()
        assert saved == {0}
        assert _buttons(host)["確認套用 NFB"].instate(("disabled",))
        assert _buttons(host)["還原為未配置"].instate(("!disabled",))

        _click_bay(win, root, 1)
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)
        buttons = _buttons(host)
        assert buttons["複製至其他連"].instate(("!disabled",))
        assert buttons["還原為未配置"].instate(("disabled",))
        buttons["複製至其他連"].invoke()
        assert saved == {0, 1}
        assert _buttons(host)["複製至其他連"].instate(("disabled",))
        assert _buttons(host)["還原為未配置"].instate(("!disabled",))
        _buttons(host)["還原為未配置"].invoke()
        assert saved == set()
        assert _buttons(host)["復原上次 NFB 操作"].instate(("!disabled",))
        _buttons(host)["復原上次 NFB 操作"].invoke()
        assert saved == {0, 1}

        assert transactions == [
            ("SUBMIT", (0,), False), ("SUBMIT", (0,), True),
            ("COPY_SUBMIT", (0, 1), True),
            ("RESTORE_UNCONFIGURED", (0, 1), True),
            ("UNDO", (), True),
        ]
        assert not warnings
        assert all("影響板件" in p and "尚未製造放行" in p
                   for p in seen_previews[:4])
        assert all("PAD" in p for p in seen_previews[:4])
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_live_source_revocation_blocks_stale_enabled_submit_button(monkeypatch):
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    ready = {0}
    submitted = []
    messages = []
    monkeypatch.setattr(view.messagebox, "showwarning",
                        lambda title, message, *, parent: messages.append(message))
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _: True,
            resize_connections=lambda *_: False,
            get_settings_ports=lambda _: {
                "row": lambda: {"bays": [{"stable_id": "bay-0"}]},
                "select": lambda _: None,
            },
            get_nfb_transaction_ports=lambda: {
                "state": lambda si, bi, selection=(): {
                    "can_submit": bi in ready, "can_copy": False,
                    "can_restore": False, "can_undo": False,
                    "reason": "原始來源已變更，請重新驗證",
                    "base_partial_ready": False,
                },
                "submit": lambda *args: submitted.append(args),
                "manifest": lambda *_: {"status": "LEGACY"},
            },
        )
        root.update()
        assert win._receiving_multi_apply(0)
        _select_inner(win, root)
        enabled = _buttons(win._receiving_multi_settings_host)["確認套用 NFB"]
        assert enabled.instate(("!disabled",))
        ready.clear()  # DXF or geometry changed after this button was painted.
        enabled.invoke()
        assert not submitted
        assert messages and "原始來源已變更" in messages[0]
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_source_revoked_warning_is_live_and_unlink_never_resurfaces(monkeypatch):
    root = tk.Tk()
    root.update()
    messages = []
    ready = {0}
    calls = []
    monkeypatch.setattr(view.messagebox, "showwarning",
                        lambda _title, message, *, parent:
                        messages.append(message))
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _: True,
            resize_connections=lambda *_: True,
            get_settings_ports=lambda _: {
                "row": lambda: {"bays": [{"stable_id": "bay-0"}]},
                "select": lambda _: None,
                "share": lambda *_: calls.append("share"),
                "unlink": lambda *_: calls.append("retired-unlink"),
            },
            get_nfb_transaction_ports=lambda: {
                "state": lambda si, bi, selected=(): {
                    "submitted": False, "can_submit": bi in ready,
                    "can_copy": False, "can_restore": False,
                    "can_undo": False,
                    "reason": "現行 CSV 請經原開孔編輯器確認全部",
                    "base_partial_ready": False,
                },
                "submit": lambda *_: calls.append("submit"),
                "manifest": lambda *_: {"status": "LEGACY"},
            },
        )
        root.update()
        assert win._receiving_multi_apply(0)
        _select_inner(win, root)
        buttons = _buttons(win._receiving_multi_settings_host)
        assert "解除本連連動" not in buttons
        assert buttons["連動選取的連"].instate(("!disabled",))
        # Genuine source revocation between paint and click must not submit,
        # even though the first painted button was enabled.
        stale_button = buttons["確認套用 NFB"]
        assert stale_button.instate(("!disabled",))
        ready.clear()
        stale_button.invoke()
        assert calls == []
        assert messages and "CSV" in messages[-1]
        # After repaint the rendered button must be disabled and show the
        # source-owned reason rather than an invented obsolete DXF mandate.
        win._receiving_multi_applied["selected_bays"] = (0,)
        win._receiving_multi_show_settings()
        assert "解除本連連動" not in _buttons(win._receiving_multi_settings_host)
        win._receiving_multi_close()
    finally:
        root.destroy()
