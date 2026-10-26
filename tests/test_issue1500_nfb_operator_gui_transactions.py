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

def test_ac23_reopened_stale_world_x_native_tk_reconfirm_restores_only_source_verified_dxf(
    tmp_path, monkeypatch,
):
    """One Bay: manufacture -> commit -> datum drift -> disk -> native GUI re-approve.

    Never fabricate a CONFIRMED state on reload: an original Tk operator
    approval is essential and only that same approved per-hole geometry may
    become exportable again. The source is a generated DXF used by the actual
    production parser, NOT an original customer project or blanket MFG-2.
    """
    from ae_engine.receiving_layout import update_receiving_bay
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from ae_engine.receiving_nfb_export_manifest import (
        INNER_DOOR, OTHER, NfbActualPart, derive_nfb_partial_export_manifest,
    )
    from ae_engine.receiving_nfb_manufacturing_release import (
        configured_nfb_inner_door_render_data, save_configured_nfb_inner_door_dxf,
    )
    from ae_engine.receiving_nfb_transactions import submit_nfb_bays
    from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from ae_engine.receiving_nfb_manufacturing_release import NfbValidatedInnerDoorRender
    from phase6_project_file import write_project, read_project
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
    from tests.test_issue1497_configured_nfb_manufacturing_release import (
        _source, _hole, _state,
    )
    from tests.test_issue1499_nfb_persistence import _payload
    from tests.test_issue1500_nfb_transactions import (
        layout as transaction_layout, config, evidence,
    )

    index, source, profile = _source(tmp_path)
    physical_id = "nfb:0:slot1"
    manufacturer = configured_nfb_inner_door_render_data(
        _state(), "upper", holes=(_hole(id=physical_id, x=0, angle=90),),
        index_path=index, source_path=source, profile=profile,
    )
    assert isinstance(manufacturer, NfbValidatedInnerDoorRender)
    assert manufacturer.manufacturing_ready
    assert manufacturer.verified_hole_locations == (
        (physical_id, 0.0, 1, 0, 90),
    )
    source_evidence = inspect_nfb_dxf_source(source)
    original = transaction_layout()
    original_bay = original["sets"][0]["bays"][0]
    source_scope, _, _ = evidence(original, 0)
    initial = submit_nfb_bays(
        original, set_index=0, bay_indices=(0,), version_id="v1",
        configs={0: config(x=0, owner=physical_id)},
        evidence={0: (source_scope, source_evidence, manufacturer)},
        confirm=lambda _: True,
    ).layout
    assert initial["sets"][0]["bays"][0]["nfb_config_submitted"] is True

    changed = update_receiving_bay(initial, set_index=0, bay_index=0, width=750)
    changed = update_receiving_bay(changed, set_index=0, bay_index=0, width=800)
    stale_hole = changed["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert stale_hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert stale_hole["manual_x_mm"] == 0
    assert changed["sets"][0]["bays"][1] == original["sets"][0]["bays"][1]

    before_file = write_project(tmp_path / "ac23_pending_reconfirm.p6fold", _payload(changed))
    reopened = read_project(before_file)["snapshot"]["receiving_layout"]
    assert reopened["sets"][0]["bays"][0]["nfb_config"]["holes"][0][
        "manual_x_state"
    ] == "RECONFIRM_REQUIRED"

    def physical_manifest(layout):
        bays = layout["sets"][0]["bays"]
        scope = NfbPhysicalScope(
            layout["sets"][0]["stable_id"], bays[0]["stable_id"], "v1",
            True, manufacturer.part_id, (), (),
        )
        return derive_nfb_partial_export_manifest(
            scope=scope,
            actual_parts=(
                NfbActualPart(manufacturer.part_id, INNER_DOOR, 1),
                NfbActualPart("independent-side", OTHER, 1),
            ),
            saved_bay=bays[0], set_brand="士林",
            source_inventory=source_evidence,
            verified_inner_door=manufacturer,
            source_path=source,
            proven_unaffected_part_ids=("independent-side",),
        )

    held = physical_manifest(reopened)
    assert held.authorized_part_ids == ("independent-side",)
    assert not held.whole_ready
    with pytest.raises(ValueError, match="BLOCKED"):
        held.require_export((manufacturer.part_id,), partial=True)

    adapter = ReceivingSetBayAdapter(reopened)
    staged = deepcopy(reopened["sets"][0]["bays"][0]["nfb_config"])
    staged["holes"][0]["manual_x_state"] = "CONFIRMED"
    staged["holes"][0]["datum_revision"] = "w800t2-native-reconfirmed"
    assert staged["holes"][0]["manual_x_mm"] == 0
    previews = []
    warnings = []
    approvals = iter((False, True))
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    try:
        def askyesno(_title, message, *, parent):
            assert parent is win
            previews.append(message)
            return next(approvals)

        monkeypatch.setattr(view.messagebox, "askyesno", askyesno)
        monkeypatch.setattr(
            view.messagebox, "showwarning",
            lambda _title, msg, *, parent: warnings.append(msg),
        )

        def state(si, bi, selection=()):
            row = adapter.layout["sets"][si]["bays"][bi]
            return {
                "submitted": row.get("nfb_config_submitted") is True,
                "can_submit": bi == 0,
                "can_copy": False, "can_restore": True,
                "can_undo": adapter.nfb_can_undo,
                "reason": "", "base_partial_ready": False,
            }

        def submit(si, selected, confirm):
            assert si == 0 and tuple(selected) == (0,)
            scope, _, _ = evidence(adapter.layout, 0)
            outcome = adapter.submit_nfb_to_bays(
                set_index=0, bay_indices=(0,), version_id="v1",
                configs={0: staged},
                evidence={0: (scope, source_evidence, manufacturer)},
                confirm=confirm,
            )
            return outcome.changed

        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _: True, resize_connections=lambda *_: False,
            get_settings_ports=lambda _: {
                "row": lambda: {"bays": [
                    {"stable_id": b["stable_id"]}
                    for b in adapter.layout["sets"][0]["bays"]
                ]},
                "select": lambda _: None,
            },
            get_nfb_transaction_ports=lambda: {
                "state": state, "submit": submit,
                "manifest": lambda *_: {"status": "BLOCKED",
                                         "reason": "舊 X 待重新確認"},
            },
        )
        root.update()
        assert win._receiving_multi_apply(0)
        _select_inner(win, root)
        button = _buttons(win._receiving_multi_settings_host)["確認套用 NFB"]
        assert button.instate(("!disabled",))
        before_cancel = deepcopy(adapter.layout)
        button.invoke()
        assert adapter.layout == before_cancel
        assert not adapter.nfb_can_undo
        assert len(previews) == 1
        assert physical_id in previews[0]
        assert "確認狀態變更" in previews[0]
        assert "X 基準版次變更" in previews[0]
        assert "尚未製造放行" in previews[0]

        button = _buttons(win._receiving_multi_settings_host)["確認套用 NFB"]
        button.invoke()
        assert not warnings
        assert len(previews) == 2
        approved_hole = adapter.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
        assert approved_hole["manual_x_state"] == "CONFIRMED"
        assert approved_hole["manual_x_mm"] == 0
        assert approved_hole["datum_revision"] == "w800t2-native-reconfirmed"
        assert adapter.nfb_can_undo
        assert adapter.layout["sets"][0]["bays"][1] == original["sets"][0]["bays"][1]
        win._receiving_multi_close()
    finally:
        root.destroy()

    saved = write_project(
        tmp_path / "ac23_native_reconfirmed.p6fold", _payload(adapter.layout),
    )
    reopened_approved = read_project(saved)["snapshot"]["receiving_layout"]
    final_hole = reopened_approved["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert final_hole["manual_x_state"] == "CONFIRMED"
    assert final_hole["manual_x_mm"] == 0

    accepted = physical_manifest(reopened_approved)
    assert manufacturer.part_id in accepted.authorized_part_ids
    assert accepted.require_export((manufacturer.part_id,), partial=True) == (
        manufacturer.part_id,
    )
    output = tmp_path / "ac23_native_reconfirmed_actual_cutting.dxf"
    save_configured_nfb_inner_door_dxf(
        _state(), "upper", output,
        holes=(_hole(id=physical_id, x=final_hole["manual_x_mm"], angle=90),),
        index_path=index, source_path=source, profile=profile,
    )
    assert output.is_file()
    import ezdxf
    output_cutting = [
        part for part in ezdxf.readfile(output).modelspace()
        if part.dxftype() == "LWPOLYLINE"
        and part.dxf.layer == "CUTTING" and part.closed
    ]
    assert len(output_cutting) == 2

    # The same revived X permission is still byte-bound to the original.
    source.write_bytes(source.read_bytes() + b"\nSOURCE_REPLACED")
    revoked = physical_manifest(reopened_approved)
    assert revoked.authorized_part_ids == ("independent-side",)
    with pytest.raises(ValueError, match="BLOCKED"):
        revoked.require_export((manufacturer.part_id,), partial=True)


def test_ac07_ac43_native_two_bay_copy_cancel_overwrite_independence_and_reopen(
    tmp_path, monkeypatch,
):
    """Actual Tk canvas/button -> source-verified physical Bay copy transaction.

    The source evidence is the existing typed MFG-1 test fixture; it is not
    original manufacturer DXF, arbitrary X authorization or Windows human UAT.
    """
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
    from tests.test_issue1500_nfb_transactions import (
        layout as transaction_layout, config, evidence,
    )
    from tests.test_issue1499_nfb_persistence import _payload
    from phase6_project_file import write_project, read_project

    adapter = ReceivingSetBayAdapter(transaction_layout())
    source = config(x=0, owner="nfb:0:slot1")
    source["holes"][0]["unit_id"] = "verified-original-source-unit"
    created = adapter.submit_nfb_to_bays(
        set_index=0, bay_indices=(0,), version_id="v1",
        configs={0: source},
        evidence={0: evidence(adapter.layout, 0, x=0)},
        confirm=lambda _: True,
    )
    assert created.changed
    initial = adapter.layout
    assert initial["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert "nfb_config" not in initial["sets"][0]["bays"][1]

    approvals = iter((False, True, False, True))
    previews = []
    warnings = []
    target_ready = {"value": True}
    new_world_x = {"value": 100}
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    try:
        def askyesno(_title, message, *, parent):
            assert parent is window
            previews.append(message)
            return next(approvals)

        monkeypatch.setattr(view.messagebox, "askyesno", askyesno)
        monkeypatch.setattr(
            view.messagebox, "showwarning",
            lambda _title, message, *, parent: warnings.append(message),
        )

        def state(si, bi, selected=()):
            assert si == 0
            row = adapter.layout["sets"][si]["bays"][bi]
            return {
                "submitted": row.get("nfb_config_submitted") is True,
                "can_submit": False,
                "can_copy": (
                    tuple(selected) == (0, 1)
                    and adapter.layout["sets"][0]["bays"][0].get(
                        "nfb_config_submitted"
                    ) is True
                    and target_ready["value"]
                ),
                "can_restore": row.get("nfb_config_submitted") is True,
                "can_undo": adapter.nfb_can_undo,
                "reason": "目標連尚未驗證 X 來源" if not target_ready["value"] else "",
                "base_partial_ready": False,
            }

        def copy(si, ids, confirm):
            assert si == 0 and tuple(ids) == (0, 1)
            if not target_ready["value"]:
                raise ValueError("目標連尚未驗證 X 來源")
            x = new_world_x["value"]
            target = config(x=x, owner="nfb:1:slot1")
            target["holes"][0]["unit_id"] = "independent-target-unit"
            result = adapter.copy_submitted_nfb_to_bay(
                set_index=si, source_bay_index=0, target_bay_index=1,
                version_id="v1", target_config=target,
                evidence=evidence(adapter.layout, 1, x=x),
                confirm=confirm,
            )
            return result.changed

        window = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _: True,
            resize_connections=lambda *_: False,
            get_settings_ports=lambda _: {
                "row": lambda: {"bays": [
                    {"stable_id": row["stable_id"]}
                    for row in adapter.layout["sets"][0]["bays"]
                ]},
                "select": lambda _: None,
            },
            get_nfb_transaction_ports=lambda: {
                "state": state,
                "copy": copy,
                "undo": adapter.undo_last_nfb_transaction,
                "manifest": lambda *_: {"status": "BLOCKED",
                                         "reason": "其餘板件尚未製造放行"},
            },
        )
        root.update()
        assert window._receiving_multi_apply(0)
        _select_inner(window, root)
        _click_bay(window, root, 1)
        assert window._receiving_multi_applied["selected_bays"] == (0, 1)
        host = window._receiving_multi_settings_host

        # A visible but stale copy button MUST re-read live authorization.
        assert _buttons(host)["複製至其他連"].instate(("!disabled",))
        target_ready["value"] = False
        _buttons(host)["複製至其他連"].invoke()
        assert warnings and "恰好兩連" in warnings[-1]
        assert adapter.layout == initial
        assert not previews
        target_ready["value"] = True

        # First submission into UNCONFIGURED: cancel does not create dormant
        # target config, source config or transient Undo receipt.
        _buttons(host)["複製至其他連"].invoke()
        assert adapter.layout == initial
        assert len(previews) == 1 and "COPY_SUBMIT" in previews[-1]
        assert "影響板件" in previews[-1]
        assert "尚未製造放行" in previews[-1]
        assert not any("nfb_config" in r for r in
                       adapter.layout["sets"][0]["bays"][1:])

        # Confirm the *same* source-specific physical target.
        _buttons(host)["複製至其他連"].invoke()
        first_copy = adapter.layout
        source_hole = first_copy["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
        target_hole = first_copy["sets"][0]["bays"][1]["nfb_config"]["holes"][0]
        assert first_copy["sets"][0]["bays"][1]["nfb_config_submitted"] is True
        assert source_hole["physical_hole_id"] != target_hole["physical_hole_id"]
        assert source_hole["unit_id"] == "verified-original-source-unit"
        assert target_hole["unit_id"] == "independent-target-unit"
        assert (source_hole["manual_x_mm"], target_hole["manual_x_mm"]) == (0, 100)
        assert source_hole["rotation_deg"] == target_hole["rotation_deg"] == 90
        assert adapter.nfb_can_undo

        # Overwriting a submitted target also needs an actual operator prompt,
        # and a cancelled overwrite may not change either Bay.
        new_world_x["value"] = 200
        assert _buttons(host)["複製至其他連"].instate(("!disabled",))
        _buttons(host)["複製至其他連"].invoke()
        assert adapter.layout == first_copy
        assert "COPY_OVERWRITE" in previews[-1]
        _buttons(host)["複製至其他連"].invoke()
        overwritten = adapter.layout
        assert overwritten["sets"][0]["bays"][0] == first_copy["sets"][0]["bays"][0]
        assert overwritten["sets"][0]["bays"][1]["nfb_config"]["holes"][0][
            "manual_x_mm"
        ] == 200
        assert overwritten["sets"][0]["bays"][1]["nfb_config"]["holes"][0][
            "unit_id"
        ] == "independent-target-unit"
        assert len(previews) == 4
        # Undo only the overwrite. The first independent copy survives.
        assert _buttons(host)["復原上次 NFB 操作"].instate(("!disabled",))
        monkeypatch.setattr(
            view.messagebox, "askyesno",
            lambda _title, msg, *, parent: (
                True if "Undo" in _title and parent is window else
                (_ for _ in ()).throw(AssertionError("unexpected operator prompt"))
            ),
        )
        _buttons(host)["復原上次 NFB 操作"].invoke()
        assert adapter.layout == first_copy

        window._receiving_multi_close()
    finally:
        root.destroy()

    saved = write_project(
        tmp_path / "ac07_ac43_native_bay_copy.p6fold",
        _payload(adapter.layout),
    )
    reopened = read_project(saved)["snapshot"]["receiving_layout"]
    bays = reopened["sets"][0]["bays"]
    assert all(b["nfb_config_submitted"] is True for b in bays)
    assert bays[0]["nfb_config"]["holes"][0]["unit_id"] == (
        "verified-original-source-unit"
    )
    assert bays[1]["nfb_config"]["holes"][0]["unit_id"] == (
        "independent-target-unit"
    )
    assert bays[0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert bays[1]["nfb_config"]["holes"][0]["manual_x_mm"] == 100
    assert bays[0]["nfb_config"]["holes"][0]["physical_hole_id"] != (
        bays[1]["nfb_config"]["holes"][0]["physical_hole_id"]
    )
