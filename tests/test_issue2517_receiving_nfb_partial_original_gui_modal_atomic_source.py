"""#2517 original Receiving NFB partial manufacturing: no old Bay after a modal.

The actual two original GUI buttons must not publish from a Bay that was
modified in-place while the native directory picker re-entered Tk. Engine
must recheck all physical source manifests AFTER staging and atomically
withdraw even the first published part if the source changes during commit.
No GUI owns NFB CSV, folded geometry, world X or DXF calculations.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, filedialog

import pytest

from ae_engine import receiving_nfb_partial_batch_dispatcher as engine
from gui_modules.application import receiving_multi_settings_window as ui
from tests.test_issue1501_highlighted_partial_dxf_dispatcher import _ports
from tests.test_issue1502_current_csv_multi_bay_once import _multi


@pytest.mark.parametrize("allow_held", [False, True])
def test_all_ready_bays_source_drift_after_actual_staged_parts_blocks_publication(
    tmp_path, allow_held,
):
    ports, staged = _ports()
    old_report = ports["manifest"]
    modified = {"value": False}
    original_export = ports["partial_export"]

    def live_report(si, bi):
        report = old_report(si, bi)
        if modified["value"] and bi == 0:
            report["version_id"] = "UNSUBMITTED_REPLACEMENT_VERSION"
        return report

    def writer(si, bi, dest):
        result = original_export(si, bi, dest)
        if bi == 1:  # Both real selected DXFs staged, neither published yet
            modified["value"] = True
        return result

    ports.update(manifest=live_report, partial_export=writer)
    with pytest.raises(ValueError, match="NFB_PARTIAL_SOURCE_CHANGED_BEFORE_COMMIT"):
        engine.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0, 1),
            output_directory=tmp_path, allow_held=allow_held,
        )
    assert len(staged) == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("allow_held", [False, True])
def test_change_during_first_actual_atomic_link_removes_all_nfb_dxfs_and_report(
    tmp_path, monkeypatch, allow_held,
):
    ports, staged = _ports()
    old_report = ports["manifest"]
    modified = {"value": False}
    original_link = engine.os.link
    links = []

    def live_report(si, bi):
        report = old_report(si, bi)
        if modified["value"] and bi == 1:
            # A previously verified Bay/source revision has changed.
            report["version_id"] = "CHANGED_DURING_PUBLICATION"
        return report

    def race_link(source, destination, *args, **kwargs):
        result = original_link(source, destination, *args, **kwargs)
        links.append(Path(destination))
        if len(links) == 1:
            modified["value"] = True
        return result

    ports["manifest"] = live_report
    monkeypatch.setattr(engine.os, "link", race_link)
    with pytest.raises(ValueError, match="NFB_PARTIAL_SOURCE_CHANGED_BEFORE_COMMIT"):
        engine.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0, 1),
            output_directory=tmp_path, allow_held=allow_held,
        )
    assert len(staged) == 2 and len(links) >= 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("drift", [
    "selection", "set", "mode", "nested_holes", "snapshot", "topology",
])
def test_original_gui_modal_source_witness_rejects_detached_nested_drift(drift):
    source = _multi()
    layout = source["receiving_layout"]
    applied = {"mode": "set_bay", "set_index": 0, "selected_bays": (0,)}
    guard = ui._receiving_nfb_partial_modal_source_witness(
        lambda: source,
        lambda: SimpleNamespace(layout=layout),
        applied, set_index=0, bay_indices=(0,),
    )
    guard()
    if drift == "selection":
        applied["selected_bays"] = (1,)
    elif drift == "set":
        applied["set_index"] = 1
    elif drift == "mode":
        applied["mode"] = "quantity"
    elif drift == "nested_holes":
        layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_mm"] += 1
    elif drift == "snapshot":
        source["panel_name"] = "changed-during-picker"
    else:
        layout["sets"][0]["bays"][0]["panel_name"] = "changed-in-place"
    with pytest.raises(ValueError, match="已變更"):
        guard()


def _native_buttons(root):
    def walk(parent):
        for child in parent.winfo_children():
            yield child
            yield from walk(child)
    return {w.cget("text"): w for w in walk(root)
            if isinstance(w, ttk.Button)}


@pytest.mark.parametrize("action", ["inner", "paired"])
def test_actual_original_multi_settings_nfb_button_refuses_modal_changed_bay(
    tmp_path, monkeypatch, action,
):
    source = _multi()
    original = deepcopy(source)
    layout = source["receiving_layout"]
    ports, writes = _ports()
    pair_calls, dialogs = [], []
    ports["state"] = lambda si, bi, *_args: {
        "base_partial_ready": True, "can_restore": True,
    }
    ports["pair_partial_export"] = lambda si, bi, output: pair_calls.append(
        (si, bi, output)
    )
    root = tk.Tk()
    root.geometry("850x650+0+0")
    root.update()
    try:
        switch = SimpleNamespace(
            layout=layout,
            connection_counts=lambda: tuple(len(s["bays"]) for s in layout["sets"]),
        )
        win = ui.open_multi_settings(
            root, get_snapshot=lambda: source,
            get_switch=lambda: switch, switch_mode=lambda _: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=lambda _si: {"select": lambda _bi: None},
            get_nfb_transaction_ports=lambda: ports,
        )
        root.update()
        assert win._receiving_multi_apply(0) is True
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        label = ("輸出已驗證內門 DXF（僅部分）"
                 if action == "inner" else
                 "輸出內門＋底板 DXF（成對部分）")
        buttons = _native_buttons(win._receiving_multi_settings_host)
        assert label in buttons

        def change_in_modal(**_kwargs):
            dialogs.append(1)
            # Simulate a nested GUI callback changing the SAME mutable
            # committed numeric CSV NFB source without replacing its dict.
            layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0][
                "manual_x_mm"
            ] += 20.0
            return str(tmp_path)

        monkeypatch.setattr(filedialog, "askdirectory", change_in_modal)
        warns = []
        monkeypatch.setattr(ui.messagebox, "showwarning",
                            lambda *args, **kwargs: warns.append(args))
        monkeypatch.setattr(ui.messagebox, "showerror",
                            lambda *args, **kwargs: warns.append(args))
        buttons[label].invoke()
        assert dialogs == [1]
        assert warns
        assert writes == [] and pair_calls == []
        assert list(tmp_path.iterdir()) == []
        assert source != original
    finally:
        root.destroy()
