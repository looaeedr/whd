# -*- coding: utf-8 -*-
"""#1504 AC-03/15: actual NFB source-only Tk viewport and source isolation.

Preview is NOT a manufacturing placement, Hole Editor or approved DXF pivot.
"""
from copy import deepcopy
from tkinter import ttk

from ae_engine.receiving_inner_door_candidates import KEY
from ae_engine.receiving_nfb_model_identity import numeric_model_refs
from tests.test_issue1504_ac20_swt13_native_inner_brand_gui import (
    _open_original_editor, _walk, _button,
)


def test_ac03_original_inner_tk_preview_visible_with_zoom_pan_reset_and_no_write(monkeypatch):
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        row = modal._receiving_inner_switch_state["rows"][0]
        assert panel.frame.winfo_ismapped()
        assert panel.canvas.winfo_ismapped()
        assert "僅預覽" in panel.frame.cget("text")
        for title in ("＋ 放大", "－ 縮小", "重設"):
            assert len([
                w for w in _walk(panel.frame)
                if isinstance(w, ttk.Button) and w.cget("text") == title
            ]) == 1
        before = deepcopy(app._phase6_input_snapshot)
        assert row["available"].size() > 0
        row["available"].selection_set(0)
        row["available"].event_generate("<<ListboxSelect>>")
        root.update()
        assert panel.identity.get().startswith("士林｜")
        assert ("禁止製造" in panel.reason.get()
                or "不可製造" in panel.reason.get())
        assert panel._numeric_spec is not None
        assert panel.canvas.find_withtag("nfb-dxf")
        assert panel._numeric_zoom == 1.0
        _button(panel.frame, "＋ 放大").invoke()
        root.update()
        assert panel._numeric_zoom == 1.25
        _button(panel.frame, "－ 縮小").invoke()
        root.update()
        assert panel._numeric_zoom == 1.0
        panel.canvas.event_generate("<ButtonPress-1>", x=25, y=30)
        panel.canvas.event_generate("<B1-Motion>", x=45, y=65)
        root.update()
        assert panel._numeric_pan == (20.0, 35.0)
        _button(panel.frame, "重設").invoke()
        root.update()
        assert panel._numeric_pan == (0.0, 0.0)
        assert panel._numeric_zoom == 1.0
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac15_model_switch_resets_view_without_reusing_stale_source_or_writing(monkeypatch):
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        refs = numeric_model_refs("士林")
        assert len(refs) >= 2
        before = deepcopy(app._phase6_input_snapshot)
        panel.show("士林", refs[0])
        root.update()
        old_key = panel._source_key
        assert old_key is not None
        panel.zoom(1.25)
        panel._press(type("Point", (), {"x": 30, "y": 25})())
        panel._move(type("Point", (), {"x": 47, "y": 38})())
        panel._release()
        assert panel._numeric_zoom > 1.0
        assert panel._numeric_pan != (0.0, 0.0)
        panel.show("士林", refs[0])
        assert panel._source_key == old_key
        assert panel._numeric_zoom > 1.0
        panel.show("士林", refs[1])
        root.update()
        assert panel._source_key != old_key
        assert panel._numeric_zoom == 1.0
        assert panel._numeric_pan == (0.0, 0.0)
        panel.show("東元", refs[0])
        root.update()
        assert panel._numeric_spec is None
        assert panel._source_key is None
        assert panel.viewport.preview is None
        assert "禁止製造" in panel.reason.get()
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac03_original_inner_tk_indexed_legacy_dxf_canvas_preserves_arc_circle_and_is_readonly(monkeypatch, tmp_path):
    # The real production preview controller draws a synthetically generated
    # *valid indexed DXF*, not a stock screenshot or a manufacturing pivot.
    from tests.test_issue1492_nfb_real_dxf_preview import _index, _real

    index = _index(tmp_path)
    source = _real(index.parent / "士林" / "400_140X257_107.dxf")
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        panel._index_path = index
        before = deepcopy(app._phase6_input_snapshot)
        panel.show("士林", source.name)
        root.update()
        assert panel.frame.winfo_ismapped()
        assert panel.canvas.winfo_ismapped()
        assert panel._numeric_mode is False
        assert panel.viewport.preview is not None
        assert len(panel.viewport.preview.strokes) == 4
        assert panel.viewport.preview.entity_count == 4
        assert not panel.viewport.preview.manufacturing_ready
        assert panel.cache.parse_count == 1
        assert len(panel.canvas.find_withtag("nfb-dxf")) == 4
        original = panel.viewport.strokes_for_canvas(*panel._size())
        _button(panel.frame, "＋ 放大").invoke()
        root.update()
        assert panel.viewport.scale > 0
        panel.canvas.event_generate("<ButtonPress-1>", x=20, y=30)
        panel.canvas.event_generate("<B1-Motion>", x=42, y=50)
        root.update()
        assert panel.viewport.strokes_for_canvas(*panel._size()) != original
        _button(panel.frame, "重設").invoke()
        root.update()
        assert panel.viewport.strokes_for_canvas(*panel._size()) == original
        panel.show("士林", source.name)
        assert panel.cache.parse_count == 1
        panel.show("東元", source.name)
        root.update()
        assert panel.viewport.preview is None
        assert panel._source_key is None
        assert "來源無法查證" in panel.reason.get()
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac15_actual_tk_legacy_dxf_revision_reparse_is_targeted_and_does_not_rebuild_box(monkeypatch, tmp_path):
    import ezdxf
    from tests.test_issue1492_nfb_real_dxf_preview import _index, _real

    index = _index(tmp_path)
    source = _real(index.parent / "士林" / "400_140X257_107.dxf")
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        panel._index_path = index
        before = deepcopy(app._phase6_input_snapshot)
        panel.show("士林", source.name)
        first = panel.viewport.preview
        assert first is not None and first.source_sha256
        assert panel.cache.parse_count == 1
        for _ in range(4):
            _button(panel.frame, "＋ 放大").invoke()
            _button(panel.frame, "－ 縮小").invoke()
            _button(panel.frame, "重設").invoke()
        root.update()
        assert panel.cache.parse_count == 1
        d = ezdxf.readfile(source)
        d.modelspace().add_line((100, 0), (120, 20))
        d.saveas(source)
        panel.show("士林", source.name)
        root.update()
        second = panel.viewport.preview
        assert second is not None
        assert second.source_sha256 != first.source_sha256
        assert second.entity_count == 5
        assert panel.cache.parse_count == 2
        assert not second.manufacturing_ready
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
