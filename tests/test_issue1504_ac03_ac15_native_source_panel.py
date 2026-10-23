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


def test_ac15_native_tk_assigned_highlight_reuses_unchanged_csv_catalog(monkeypatch):
    """Real selected-slot events must not reload the V5 catalog on every click.

    Brand/source signature changes may still reload via refresh_source().
    This tests the original inner-door editor event handler, not a mock panel.
    """
    from ae_engine import receiving_nfb_model_identity as model_catalog

    original = model_catalog.numeric_model_refs
    loads = []

    def counted_refs(brand, *args, **kwargs):
        loads.append(brand)
        return original(brand, *args, **kwargs)

    # inner_edit imports the catalog function when the real editor is opened.
    monkeypatch.setattr(model_catalog, "numeric_model_refs", counted_refs)
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        first = state["rows"][0]
        assert first["available"].size() > 0
        first["available"].selection_set(0)
        _button(first["section"], "＋加入").invoke()
        root.update()
        assert first["assigned"].size() == 1
        before = deepcopy(app._phase6_input_snapshot)
        before_draft = deepcopy(state["nfb_draft"]["draft"])
        baseline_loads = len(loads)
        assert baseline_loads > 0

        for _ in range(6):
            first["assigned"].selection_clear(0, "end")
            first["assigned"].selection_set(0)
            first["assigned"].event_generate("<<ListboxSelect>>")
            root.update()

        assert len(loads) == baseline_loads, (
            "Highlighting an unchanged V5 slot must not re-read the catalog"
        )
        assert app._phase6_input_snapshot == before
        assert state["nfb_draft"]["draft"] == before_draft
        assert KEY not in app._phase6_input_snapshot
        panel = modal._receiving_inner_nfb_dxf_panel
        assert panel._numeric_spec is not None
        assert panel.canvas.find_withtag("nfb-dxf")
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac15_v5_preview_cache_reuses_two_models_without_reparsing_csv(monkeypatch):
    """Read two actual numeric models once, not the entire CSV on every click."""
    from ae_engine import receiving_nfb_numeric_catalog as catalog

    root, app, modal = _open_original_editor(monkeypatch)
    try:
        refs = numeric_model_refs("士林")
        assert len(refs) >= 2
        panel = modal._receiving_inner_nfb_dxf_panel
        panel._numeric_sources.clear()
        panel._source_key = None

        original = catalog.read_numeric_specs
        reads = []

        def counted_read(brand, *args, **kwargs):
            reads.append(brand)
            return original(brand, *args, **kwargs)

        monkeypatch.setattr(catalog, "read_numeric_specs", counted_read)
        before = deepcopy(app._phase6_input_snapshot)
        for filename in (refs[0], refs[1], refs[0], refs[1], refs[0]):
            panel.show("士林", filename)
            root.update()
            assert panel._numeric_spec is not None
            assert panel.canvas.find_withtag("nfb-dxf")
        assert reads == ["士林", "士林"]
        assert len(panel._numeric_sources) == 2
        assert app._phase6_input_snapshot == before
        assert KEY not in before
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac15_v5_preview_cache_invalidates_changed_or_missing_csv_source(monkeypatch, tmp_path):
    """Only the viewport caches; changed/missing files force fresh or fail closed."""
    from gui_modules.application import receiving_nfb_source_preview as preview

    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        model = numeric_model_refs("士林")[0]
        fake_csv = tmp_path / "source-revision.csv"
        fake_csv.write_text("revision-one", encoding="utf-8")
        monkeypatch.setattr(preview, "brand_csv_path", lambda _brand: fake_csv)
        source = preview.selected_numeric_spec
        read_count = []

        def counted_spec(brand, filename):
            read_count.append((brand, filename))
            return source(brand, filename)

        monkeypatch.setattr(preview, "selected_numeric_spec", counted_spec)
        snapshot = deepcopy(app._phase6_input_snapshot)

        panel.show("士林", model)
        panel.zoom(1.25)
        panel.show("士林", model)
        assert len(read_count) == 1
        assert panel._numeric_zoom > 1
        fake_csv.write_text("revision-two-is-longer", encoding="utf-8")
        panel.show("士林", model)
        assert len(read_count) == 2
        assert panel._numeric_zoom == 1.0
        fake_csv.unlink()
        panel.show("士林", model)
        assert panel._numeric_spec is None
        assert panel._source_key is None
        assert panel.viewport.preview is None
        assert "禁止製造" in panel.reason.get()
        assert app._phase6_input_snapshot == snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
