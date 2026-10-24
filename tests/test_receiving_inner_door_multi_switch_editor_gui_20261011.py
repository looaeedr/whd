# -*- coding: utf-8 -*-
"""Real Tk inner-door editor: CSV switch choices belong in the editor, not first page."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_inner_door_candidates import (
    KEY, ROLE, inner_config,
)
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application import fold_designer_composition_receiving as comp
from gui_modules.application import receiving_multi_settings_window as view
from ae_engine import receiving_nfb_numeric_catalog as numeric_catalog
from ae_engine.receiving_nfb_model_identity import numeric_model_ref


def _radios(container):
    for child in container.winfo_children():
        if isinstance(child, ttk.Radiobutton):
            yield child
        yield from _radios(child)


def _buttons(container):
    results = []
    for child in container.winfo_children():
        if isinstance(child, ttk.Button):
            results.append(child)
        results.extend(_buttons(child))
    return results


def test_version_editor_add_remove_repeated_switches_and_read_updated_csv(
        monkeypatch, tmp_path):
    # The current editor reads the selected brand from numeric V5 CSV,
    # not the retired DXF-index file. Keep the physical CSV schema valid.
    csv_path = tmp_path / "NFB數值規格.csv"
    header = ",".join(numeric_catalog.HEADER) + "\n"
    csv_path.write_text(
        header + "A,60,100,40,50X90,25X80,5,0,0\n"
        + "B,70,110,45,55X95,30X85,5,0,0\n",
        encoding="utf-8-sig",
    )
    original_path = numeric_catalog.brand_csv_path
    monkeypatch.setattr(
        numeric_catalog, "brand_csv_path",
        lambda brand: csv_path if brand == "士林" else original_path(brand),
    )
    ref_a = numeric_model_ref("士林", "A")
    ref_b = numeric_model_ref("士林", "B")
    captured = {}
    monkeypatch.setattr(
        view, "open_multi_settings",
        lambda _root, **kwargs: captured.update(kwargs) or object(),
    )
    root = tk.Tk()
    root.geometry("500x360+10+10")
    root.update_idletasks()
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    app = SimpleNamespace(
        root=root,
        _phase6_input_snapshot={"active_mode": "set_bay", "model": "受電箱"},
        _settings_values={},
        _phase6_box_whd={"w": 800, "h": 1600, "d": 350, "t": 2},
        _phase6_endcap_bottom_wrap_state={},
        designer_workspace=None,
    )
    assembly = SimpleNamespace(
        app=app,
        receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda _namespace: adapter,
        receiving_switch_adapter=lambda _namespace: SimpleNamespace(brand="士林"),
        corner_transaction_payload=lambda _namespace: {},
        collect_workspace_state=lambda _namespace: {},
    )
    try:
        comp.open_receiving_multi_settings(assembly, "test")
        editor = captured["get_inner_candidate_ports"]()["edit"]
        saved_ids = []
        modal = editor(ROLE, None, saved_ids.append)
        root.update()
        state = modal._receiving_inner_switch_state
        assert [value.get() for value in state["layer_heights_mm"]] == ["330", "830"]
        assert len(state["rows"]) == 2
        assert not hasattr(modal, "_receiving_inner_preview_canvas")
        assert modal._receiving_inner_preview_status.get() == "與已載入版本相同"
        first = state["rows"][0]
        assert first["available"].get(0, tk.END) == ("A", "B")
        buttons = {b.cget("text"): b for b in
                   _buttons(first["section"])}
        first["available"].selection_set(0)
        buttons["＋加入"].invoke()
        buttons["＋加入"].invoke()
        first["available"].selection_clear(0, tk.END)
        first["available"].selection_set(1)
        buttons["＋加入"].invoke()
        assert first["assigned"].get(0, tk.END) == ("A", "A", "B")
        assert first["count"].get() == "實體 3 槽／開關 3 顆"
        assert state["chosen"][0] == [ref_a, ref_a, ref_b]
        assert modal._receiving_inner_preview_status.get() == "尚未儲存的變更"
        first["assigned"].selection_set(1)
        buttons["－移除"].invoke()
        assert first["assigned"].get(0, tk.END) == ("A", "B")
        first["available"].selection_clear(0, tk.END)
        first["available"].selection_set(0)
        buttons["＋加入"].invoke()
        assert first["assigned"].get(0, tk.END) == ("A", "B", "A")

        confirm = next(b for b in _buttons(modal)
                       if b.cget("text") == "確定")
        confirm.invoke()
        root.update()
        assert saved_ids == ["inner-door-v1"]
        saved = inner_config(app._phase6_input_snapshot[KEY], saved_ids[0])
        assert saved["layers"] == 1
        assert saved["models"] == [[ref_a, ref_b, ref_a], ""]
        assert saved["layer_heights_mm"] == [330.0, 830.0]
        assert saved["features"] == {}

        modal = editor(ROLE, saved_ids[0], lambda _vid: None)
        root.update()
        new_state = modal._receiving_inner_switch_state
        assert new_state["rows"][0]["assigned"].get(0, tk.END) == ("A", "B", "A")
        assert new_state["chosen"][0] == [ref_a, ref_b, ref_a]
        assert modal._receiving_inner_preview_status.get() == "與已載入版本相同"
        # Add a second layer in-memory; the preview must change before saving.
        next(
            radio for radio in _radios(modal)
            if radio.cget("text") == "2" and str(radio.cget("value")) == "2"
        ).invoke()
        root.update()
        assert new_state["layers"].get() == 2
        assert new_state["nfb_draft"]["draft"]["layer_count"] == 2
        layer_two = new_state["rows"][1]
        assert layer_two["section"].winfo_manager()
        layer_two["available"].selection_set(1)
        next(b for b in _buttons(layer_two["section"])
             if b.cget("text") == "＋加入").invoke()
        assert new_state["chosen"][1] == [ref_b]
        assert new_state["layer_heights_mm"][0].get() == "330"
        assert modal._receiving_inner_preview_status.get() == "尚未儲存的變更"
        csv_path.write_text(
            header + "A,60,100,40,50X90,25X80,5,0,0\n"
            + "C,70,110,45,55X95,30X85,5,0,0\n",
            encoding="utf-8-sig",
        )
        modal._receiving_inner_refresh_switch_models(force=True)
        assert new_state["rows"][0]["available"].get(0, tk.END) == ("A", "C")
        assert new_state["rows"][0]["assigned"].get(0, tk.END) == ("A", "B", "A")
        next(b for b in _buttons(modal)
             if b.cget("text") == "確定").invoke()
        root.update()
        assert "已不在廠牌 CSV" in new_state["warning"].get()
        assert inner_config(app._phase6_input_snapshot[KEY], saved_ids[0])["models"][0] == [
            ref_a, ref_b, ref_a,
        ]
        modal.destroy()
    finally:
        root.destroy()
