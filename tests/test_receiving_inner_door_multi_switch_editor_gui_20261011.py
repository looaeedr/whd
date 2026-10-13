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
from ae_engine import receiving_switch_model_catalog as catalog


def _buttons(container):
    results = []
    for child in container.winfo_children():
        if isinstance(child, ttk.Button):
            results.append(child)
        results.extend(_buttons(child))
    return results


def test_version_editor_add_remove_repeated_switches_and_read_updated_csv(
        monkeypatch, tmp_path):
    csv_path = tmp_path / "開關索引.csv"
    header = "圖塊名稱,士林,深,東元,深,伍菱,深\n"
    csv_path.write_text(
        header + "1,A.dxf,,無對應檔案,,無對應檔案,\n"
        + "2,B.dxf,,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(catalog, "INDEX_PATH", csv_path)
    captured = {}
    monkeypatch.setattr(
        view, "open_multi_settings",
        lambda _root, **kwargs: captured.update(kwargs) or object(),
    )
    root = tk.Tk()
    root.withdraw()
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    app = SimpleNamespace(
        root=root,
        _phase6_input_snapshot={"active_mode": "set_bay"},
        designer_workspace=None,
    )
    assembly = SimpleNamespace(
        app=app,
        receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda _namespace: adapter,
        receiving_switch_adapter=lambda _namespace: SimpleNamespace(brand="士林"),
    )
    try:
        comp.open_receiving_multi_settings(assembly, "test")
        editor = captured["get_inner_candidate_ports"]()["edit"]
        saved_ids = []
        modal = editor(ROLE, None, saved_ids.append)
        root.update()
        state = modal._receiving_inner_switch_state
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
        assert first["count"].get() == "已配置 3 顆"
        assert state["chosen"][0] == ["A.dxf", "A.dxf", "B.dxf"]
        assert modal._receiving_inner_preview_status.get() == "尚未儲存的變更"
        first["assigned"].selection_set(1)
        buttons["－移除"].invoke()
        assert first["assigned"].get(0, tk.END) == ("A", "B")
        first["available"].selection_clear(0, tk.END)
        first["available"].selection_set(0)
        buttons["＋加入"].invoke()
        assert first["assigned"].get(0, tk.END) == ("A", "B", "A")

        confirm = next(b for b in _buttons(modal)
                       if b.cget("text") == "確認")
        confirm.invoke()
        root.update()
        assert saved_ids == ["inner-door-v1"]
        assert inner_config(app._phase6_input_snapshot[KEY], saved_ids[0]) == {
            "layers": 1, "models": [["A.dxf", "B.dxf", "A.dxf"], ""],
        }

        modal = editor(ROLE, saved_ids[0], lambda _vid: None)
        root.update()
        new_state = modal._receiving_inner_switch_state
        assert new_state["rows"][0]["assigned"].get(0, tk.END) == ("A", "B", "A")
        assert new_state["chosen"][0] == ["A.dxf", "B.dxf", "A.dxf"]
        assert modal._receiving_inner_preview_status.get() == "與已載入版本相同"
        # Add a second layer in-memory; the preview must change before saving.
        new_state["layers"].set(2)
        layer_two = new_state["rows"][1]
        layer_two["section"].pack(fill="x")
        layer_two["available"].selection_set(1)
        next(b for b in _buttons(layer_two["section"])
             if b.cget("text") == "＋加入").invoke()
        assert new_state["chosen"][1] == ["B.dxf"]
        assert modal._receiving_inner_preview_status.get() == "尚未儲存的變更"
        csv_path.write_text(
            header + "1,A.dxf,,無對應檔案,,無對應檔案,\n"
            + "3,C.dxf,,無對應檔案,,無對應檔案,\n",
            encoding="utf-8-sig",
        )
        modal._receiving_inner_refresh_switch_models(force=True)
        assert new_state["rows"][0]["available"].get(0, tk.END) == ("A", "C")
        assert new_state["rows"][0]["assigned"].get(0, tk.END) == ("A", "B", "A")
        next(b for b in _buttons(modal)
             if b.cget("text") == "確認").invoke()
        root.update()
        assert "失效" in new_state["warning"].get()
        assert inner_config(app._phase6_input_snapshot[KEY], saved_ids[0])["models"][0] == [
            "A.dxf", "B.dxf", "A.dxf",
        ]
        modal.destroy()
    finally:
        root.destroy()
