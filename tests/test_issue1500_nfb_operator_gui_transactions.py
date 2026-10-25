"""#1500 real Tk operator controls -> one existing verified NFB transaction authority.

Buttons must use the highlighted Bay indices, recheck live source state at
click, warn with physical preview, permit cancel with zero change, and refresh
submit/copy/restore/Undo state without manufacturing a fresh NFB source.
"""
from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from gui_modules.application.fold_designer_composition_receiving import (
    _checked_nfb_copy_selection,
)
from gui_modules.application.receiving_multi_settings_window import (
    open_multi_settings,
)
from gui_modules.application import receiving_multi_settings_window as view


def _copy_layout():
    return {"sets": [{"stable_id": "set-actual", "bays": [
        {"stable_id": "bay-a", "nfb_config_submitted": True},
        {"stable_id": "bay-b", "nfb_config_submitted": False},
    ]}]}


@pytest.mark.parametrize("bad_set", (True, False, 0.0, "0", None, [], {}, -1, 1))
def test_ac07_gui_nfb_copy_requires_actual_set_identity_before_selection(bad_set):
    source = _copy_layout()
    frozen = deepcopy(source)
    with pytest.raises(ValueError, match="套位"):
        _checked_nfb_copy_selection(source, bad_set, (0, 1))
    assert source == frozen


@pytest.mark.parametrize("bad_selection", (
    None, 1, (), (0,), (0, 0),
    (0, True), (0, False), (0, 1.0), (0, "1"),
    (0, []), ([], 0), (0, {}), (0, 2), (0, -1),
))
def test_ac07_gui_nfb_copy_rejects_invalid_highlights_before_owner_alias(bad_selection):
    source = _copy_layout()
    frozen = deepcopy(source)
    with pytest.raises(ValueError, match="高亮"):
        _checked_nfb_copy_selection(source, 0, bad_selection)
    assert source == frozen


def test_ac07_gui_nfb_copy_preserves_two_valid_bay_owners_and_direction():
    source = _copy_layout()
    frozen = deepcopy(source)
    indices, selected = _checked_nfb_copy_selection(source, 0, (1, 0))
    assert indices == (1, 0)
    assert selected[1] is source["sets"][0]["bays"][1]
    assert selected[0] is source["sets"][0]["bays"][0]
    assert {v["stable_id"] for v in selected.values()} == {"bay-a", "bay-b"}
    assert selected[0]["nfb_config_submitted"] is True
    assert selected[1]["nfb_config_submitted"] is False
    assert source == frozen


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
            operator_x_changes=(
                "bay-0／nfb:0:slot1：X 未配置 → 0 mm；基準 未配置 → w800t2；條件 新增實體孔",
            ),
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
        assert all("受影響 NFB／X 基準差異" in p for p in seen_previews[:4])
        assert all("nfb:0:slot1" in p and "X 未配置 → 0 mm" in p
                   for p in seen_previews[:4])
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
        win._receiving_multi_setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert "解除本連連動" not in _buttons(win._receiving_multi_settings_host)
        win._receiving_multi_close()
    finally:
        root.destroy()



def test_ac28_native_tk_uses_actual_two_bay_transaction_preview_and_atomic_source_gate(
    monkeypatch,
):
    """Original Tk dialog consumes actual #1500 transaction previews, not mocks.

    The typed CUTTING witnesses below are the pre-existing test fixtures, NOT
    original manufacturer DXF certificates or either old Windows .p6fold.
    """
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
    from tests.test_issue1500_nfb_transactions import (
        layout as transaction_layout, config, evidence,
    )

    adapter = ReceivingSetBayAdapter(transaction_layout())
    original = adapter.layout
    staged = {
        0: config(x=0, owner="nfb:0:slot1"),
        1: config(x=125, owner="nfb:1:slot1"),
    }
    # Real operator confirmation is per physical Bay, and must display
    # ALL selected units, not only the first selected NFB in that Bay.
    second_unit = deepcopy(staged[0]["holes"][0])
    second_unit["physical_hole_id"] = "nfb:0:slot2"
    second_unit["manual_x_mm"] = 180
    staged[0]["holes"].append(second_unit)
    recorded = []
    warnings = []
    decisions = iter((False, True))  # cancel then approve first real Bay

    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    try:
        def askyesno(_title, message, *, parent):
            assert parent is win
            recorded.append(message)
            return next(decisions)

        monkeypatch.setattr(view.messagebox, "askyesno", askyesno)
        monkeypatch.setattr(
            view.messagebox, "showwarning",
            lambda _title, message, *, parent: warnings.append(message),
        )

        def state(si, bi, selection=()):
            row = adapter.layout["sets"][si]["bays"][bi]
            return {
                "submitted": row.get("nfb_config_submitted") is True,
                "can_submit": bi in staged,
                "can_copy": False,
                "can_restore": False,
                "can_undo": adapter.nfb_can_undo,
                "reason": "尚未取得本次有效的真來源" if bi not in staged else "",
                "base_partial_ready": False,
            }

        def submit(si, ids, confirm):
            assert si == 0 and len(ids) == 1
            bi = ids[0]
            candidate = staged[bi]
            # The typed fixture deliberately disagrees with Bay 2 X=125.
            # Genuine per-hole transaction verification must reject it BEFORE
            # GUI operator confirmation, without mutating the first Bay.
            manufactured_x = 0 if bi == 0 else 100
            proof = evidence(adapter.layout, bi, x=manufactured_x)
            if bi == 0:
                from dataclasses import replace
                scope, inventory, door = proof
                proof = (scope, inventory, replace(
                    door,
                    physical_hole_ids=("nfb:0:slot1", "nfb:0:slot2"),
                    verified_hole_locations=(
                        ("nfb:0:slot1", 0.0, 1, 0, 90),
                        ("nfb:0:slot2", 180.0, 1, 0, 90),
                    ),
                ))
            outcome = adapter.submit_nfb_to_bays(
                set_index=si, bay_indices=tuple(ids), version_id="v1",
                configs={bi: candidate}, evidence={bi: proof},
                confirm=confirm,
            )
            if outcome.changed:
                staged.pop(bi)
            return outcome.changed

        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_: False,
            get_settings_ports=lambda _si: {
                "row": lambda: {"bays": [
                    {"stable_id": original["sets"][0]["bays"][0]["stable_id"]},
                    {"stable_id": original["sets"][0]["bays"][1]["stable_id"]},
                ]},
                "select": lambda _bi: None,
            },
            get_nfb_transaction_ports=lambda: {
                "state": state, "submit": submit,
                "manifest": lambda *_: {"status": "LEGACY"},
            },
        )
        root.update()
        assert win._receiving_multi_apply(0)
        _select_inner(win, root)
        host = win._receiving_multi_settings_host

        # Actual physical Bay 1: cancel must leave submission + Undo empty.
        assert _buttons(host)["確認套用 NFB"].instate(("!disabled",))
        _buttons(host)["確認套用 NFB"].invoke()
        assert adapter.layout == original and not adapter.nfb_can_undo
        assert len(recorded) == 1
        assert original["sets"][0]["bays"][0]["stable_id"] in recorded[0]
        assert "nfb:0:slot1" in recorded[0]
        assert "nfb:0:slot2" in recorded[0]
        assert "X 未配置 → 0 mm" in recorded[0]
        assert "X 未配置 → 180 mm" in recorded[0]
        assert "基準 未配置 → w800t2" in recorded[0]
        assert "受影響 NFB／X 基準差異" in recorded[0]
        assert "尚未製造放行" in recorded[0]

        # Accept the SAME verified physical candidate. Other Bay untouched.
        _buttons(host)["確認套用 NFB"].invoke()
        committed = adapter.layout
        assert committed["sets"][0]["bays"][0]["nfb_config_submitted"] is True
        assert [h["manual_x_mm"] for h in
                committed["sets"][0]["bays"][0]["nfb_config"]["holes"]] == [0, 180]
        assert "nfb_config" not in committed["sets"][0]["bays"][1]
        assert adapter.nfb_can_undo
        assert len(recorded) == 2

        # Switch actual canvas selection to Bay 2. Its typed CUTTING witness
        # reports X=100 whereas operator requested 125. The backend must
        # fail before the native dialog and leave committed Bay 1 intact.
        _click_bay(win, root, 1)
        _click_bay(win, root, 0)
        assert win._receiving_multi_applied["selected_bays"] == (1,)
        assert _buttons(host)["確認套用 NFB"].instate(("!disabled",))
        _buttons(host)["確認套用 NFB"].invoke()
        assert len(recorded) == 2
        assert warnings and "configured X/Y slot/rotation differs" in warnings[-1]
        assert adapter.layout == committed
        assert 1 in staged
        assert adapter.nfb_can_undo

        win._receiving_multi_close()
    finally:
        root.destroy()
