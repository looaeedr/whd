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
        # Preview status belongs to the heading, never the selectable text:
        # existing operator selection and legacy UI automation both rely
        # on the exact model display name rather than a decorated value.
        from ae_engine.receiving_nfb_model_identity import (
            numeric_model_refs, display_model_ref,
        )
        first_ref = numeric_model_refs("士林")[0]
        assert row["available"].get(0) == display_model_ref(first_ref)
        assert first_ref.startswith("nfbv5:")
        assert any(
            isinstance(widget, ttk.Label)
            and widget.cget("text") == "CSV 型號｜僅預覽"
            for widget in _walk(row["section"])
        )
        row["available"].selection_set(0)
        row["available"].event_generate("<<ListboxSelect>>")
        root.update()
        assert panel.identity.get().startswith("士林｜")
        assert ("禁止製造" in panel.reason.get()
                or "此處僅預覽" in panel.reason.get())
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


def test_ac15_original_tk_two_model_highlight_has_bounded_latency_no_full_3d(monkeypatch):
    """Measure source-view highlight, not an unrelated whole-cabinet benchmark."""
    from math import ceil
    from statistics import median
    from time import perf_counter
    from ae_engine import receiving_nfb_numeric_catalog as catalog
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter

    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        first = state["rows"][0]
        assert first["available"].size() >= 2
        for model_index in (0, 1):
            first["available"].selection_clear(0, "end")
            first["available"].selection_set(model_index)
            _button(first["section"], "＋加入").invoke()
            root.update()
        assert first["assigned"].size() == 2
        project_before = deepcopy(app._phase6_input_snapshot)
        draft_before = deepcopy(state["nfb_draft"]["draft"])
        panel = modal._receiving_inner_nfb_dxf_panel
        panel._numeric_sources.clear()
        panel._source_key = None

        reads = []
        actual_read = catalog.read_numeric_specs

        def count_csv_reads(brand, *args, **kwargs):
            reads.append(brand)
            return actual_read(brand, *args, **kwargs)

        monkeypatch.setattr(catalog, "read_numeric_specs", count_csv_reads)

        def forbidden_scene_render(*_args, **_kwargs):
            raise AssertionError("Highlight may not rebuild full FinalScene 3D")

        monkeypatch.setattr(Phase6FinalSceneRenderer, "render", forbidden_scene_render)
        monkeypatch.setattr(Phase6FinalSceneViewAdapter, "render_cutting_mesh",
                            forbidden_scene_render)
        elapsed_ms = []
        for slot in (0, 1) * 12:
            started = perf_counter()
            first["assigned"].selection_clear(0, "end")
            first["assigned"].selection_set(slot)
            first["assigned"].event_generate("<<ListboxSelect>>")
            root.update()
            elapsed_ms.append((perf_counter() - started) * 1000.0)
            assert panel._numeric_spec is not None
            assert panel.canvas.find_withtag("nfb-dxf")
        p95_ms = sorted(elapsed_ms)[ceil(.95 * len(elapsed_ms)) - 1]
        median_ms = median(elapsed_ms)
        # A full 2D/3D solve would be orders of magnitude slower. Bounds apply
        # only to this original Tk source-selection path on the CI runner.
        assert median_ms < 150.0, median_ms
        assert p95_ms < 300.0, p95_ms
        assert reads == ["士林", "士林"], reads
        assert len(panel._numeric_sources) == 2
        assert app._phase6_input_snapshot == project_before
        assert state["nfb_draft"]["draft"] == draft_before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_swt05_original_inner_tk_per_unit_preview_cancel_discards_draft(monkeypatch):
    """Real original UI: selecting a V5 unit source is not a manufacturing edit."""
    from tkinter import messagebox

    notices = []
    monkeypatch.setattr(
        messagebox, "askyesno",
        lambda title, body, **_kw: notices.append((title, body)) or True,
    )
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        original = deepcopy(app._phase6_input_snapshot)
        first = modal._receiving_inner_switch_state["rows"][0]
        assert first["available"].size() >= 1
        first["available"].selection_set(0)
        _button(first["section"], "＋加入").invoke()
        first["assigned"].selection_set(0)
        first["assigned"].event_generate("<<ListboxSelect>>")
        root.update()
        panel = modal._receiving_inner_nfb_dxf_panel
        assert panel.frame.winfo_ismapped()
        assert panel._numeric_spec is not None
        assert panel.canvas.find_withtag("nfb-dxf")
        assert "禁止製造" in panel.reason.get() or "不可製造" in panel.reason.get()
        assert app._phase6_input_snapshot == original
        _button(modal, "取消").invoke()
        root.update()
        assert not modal.winfo_exists()
        assert app._phase6_input_snapshot == original
        assert KEY not in app._phase6_input_snapshot
        assert len(notices) == 1
        assert "捨棄" in notices[0][0]
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_swt05_original_inner_tk_confirm_saves_candidate_not_manufacturing(monkeypatch):
    """Confirming standalone version stores its source choice, not CUTTING."""
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        before = deepcopy(app._phase6_input_snapshot)
        first = modal._receiving_inner_switch_state["rows"][0]
        first["available"].selection_set(0)
        _button(first["section"], "＋加入").invoke()
        first["assigned"].selection_set(0)
        first["assigned"].event_generate("<<ListboxSelect>>")
        root.update()
        panel = modal._receiving_inner_nfb_dxf_panel
        source = modal._receiving_inner_switch_state["nfb_draft"]["draft"]["layers"][0]["slots"][0]["filename"]
        assert source in numeric_model_refs("士林")
        assert panel._numeric_spec is not None
        assert KEY not in before
        _button(modal, "確定").invoke()
        root.update()
        assert not modal.winfo_exists()
        assert KEY in app._phase6_input_snapshot
        from ae_engine.receiving_inner_door_candidates import normalize_inner_candidates, inner_versions, inner_config, ROLE
        library = normalize_inner_candidates(app._phase6_input_snapshot[KEY])
        versions = inner_versions(library)
        assert len(versions) == 1
        version = versions[0]
        candidate = inner_config(library, version["id"])
        assert source in str(candidate["models"][0])
        assert before["model"] == app._phase6_input_snapshot["model"]
        # A candidate is not a live manufacturing transaction nor 3D rebuild.
        assert not any("CUTTING" in str(k) for k in app._phase6_input_snapshot)
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_swt05_embedded_original_hole_editor_cancel_then_confirm_stages_only(monkeypatch):
    """Original embedded tab routes to parent stage; never commits on tab confirm."""
    from types import SimpleNamespace
    import tkinter as tk
    from tkinter import ttk
    from ae_engine.receiving_layout import new_receiving_layout
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
    from gui_modules.application import fold_designer_composition_receiving as comp
    from gui_modules.application import receiving_multi_settings_window as view

    captured = {}
    monkeypatch.setattr(
        view, "open_multi_settings",
        lambda _root, **kwargs: captured.update(kwargs) or object(),
    )
    root = tk.Tk()
    root.withdraw()
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350),
    )
    app = SimpleNamespace(
        root=root,
        _phase6_input_snapshot={
            "active_mode": "set_bay", "model": "受電箱",
            # The original physical Hole Editor requires a real receiving
            # inner-door cell. A headless adapter without it must fail closed.
            "multi_door_enabled": True,
            "door_layout_scope": "receiving-main",
            "door_layout_columns": [[800.0, [1100.0, 500.0]]],
            "inner_doors": [{
                "stable_id": "upper", "cell_key": "0:0",
                "included_frame_sides": ["top", "left", "right"],
            }],
        },
        _settings_values={},
        _phase6_box_whd={"w": 800, "h": 1600, "d": 350, "t": 2},
        _phase6_endcap_bottom_wrap_state={},
        designer_workspace=SimpleNamespace(active_mode="set_bay"),
    )
    assembly = SimpleNamespace(
        app=app, receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda _ns: adapter,
        receiving_switch_adapter=lambda _ns: SimpleNamespace(brand="士林"),
        corner_transaction_payload=lambda _ns: {},
        collect_workspace_state=lambda _ns: {},
    )
    comp.open_receiving_multi_settings(assembly, "test")
    editor = captured["get_inner_candidate_ports"]()["edit"]
    parent = tk.Toplevel(root)
    parent._receiving_settings_mode = "single"
    staged, saved, closed = [], [], []
    parent._receiving_stage_config = lambda config, holes: staged.append(
        (deepcopy(config), holes)
    )
    parent._receiving_pending_features = lambda: ()
    container = ttk.Frame(parent)
    container.pack(fill="both", expand=True)
    original = deepcopy(app._phase6_input_snapshot)
    try:
        first = editor("inner-door", None, lambda version: saved.append(version),
                       embed_parent=container,
                       after_closed=lambda: closed.append(True))
        root.update()
        assert first.winfo_exists()
        assert first._receiving_inner_switch_state["direct_to_drawing"] is True
        assert first._receiving_inner_switch_state["rows"][0]["assigned"].size() >= 1
        assert "X 基準未定" in first._receiving_inner_switch_state["nfb_draft_status"].get()
        assert "僅預覽" in first._receiving_inner_switch_state["nfb_draft_status"].get()
        _button(first, "取消").invoke()
        root.update()
        assert not first.winfo_exists()
        assert closed == [True]
        assert not staged and not saved
        assert app._phase6_input_snapshot == original
        assert KEY not in app._phase6_input_snapshot

        second = editor("inner-door", None, lambda version: saved.append(version),
                        embed_parent=container)
        root.update()
        assert second._receiving_inner_switch_state["rows"][0]["assigned"].size() >= 1
        _button(second, "確定").invoke()
        root.update()
        assert not second.winfo_exists(), second._receiving_inner_switch_state["warning"].get()
        assert len(staged) == 1
        config, features = staged[0]
        assert config["layers"] == 1
        assert features and all(feature.source_type == "NFB_CSV_SOURCE"
                                for feature in features)
        assert saved == [None]
        # Confirm on the tab is staging only; the parent Hole Editor owns final
        # application. The project state and factory release remain untouched.
        assert app._phase6_input_snapshot == original
        assert KEY not in app._phase6_input_snapshot
    finally:
        if parent.winfo_exists():
            parent.destroy()
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


def test_ac51_original_tk_v5_selector_shows_source_scope_without_fake_release(monkeypatch):
    """Current CSV has no old per-model DXF gate; the live selector still
    requires a per-Set/Bay committed physical proof before manufacturing.
    Preview must keep the original selectable model names and never mutate
    the authoritative saved project.
    """
    from ae_engine.receiving_nfb_2d_preview import NfbDxfPreviewCache
    from ae_engine.receiving_nfb_model_identity import (
        numeric_model_ref, display_model_ref,
    )

    root, app, modal = _open_original_editor(monkeypatch)
    try:
        panel = modal._receiving_inner_nfb_dxf_panel
        row = modal._receiving_inner_switch_state["rows"][0]
        model = numeric_model_ref("士林", "2P400")
        before = deepcopy(app._phase6_input_snapshot)
        # Never query legacy original DXF just to display the current V5.
        def forbid_legacy(*args, **kwargs):
            raise AssertionError("CURRENT NFB V5 selector called old-model DXF reader")
        monkeypatch.setattr(NfbDxfPreviewCache, "load", forbid_legacy)
        panel.show("士林", model)
        root.update()
        assert panel._numeric_spec is not None
        assert panel._numeric_spec.dimensionally_complete is True
        assert "CSV 數值完整" in panel.reason.get()
        assert "此處僅預覽" in panel.reason.get()
        assert "正式出圖需提交目前 Set/Bay" in panel.reason.get()
        assert "實體內門／底板" in panel.reason.get()
        assert "可製造（內門）" not in panel.reason.get()
        assert "僅預覽" in panel.frame.cget("text")
        assert any(
            isinstance(widget, ttk.Label)
            and widget.cget("text") ==
                "型號僅預覽｜製造資格以本連已提交配置及真實板件驗證為準"
            for widget in _walk(row["section"])
        )
        assert any(
            row["available"].get(i) == display_model_ref(model)
            for i in range(row["available"].size())
        )
        assert panel.canvas.find_withtag("nfb-dxf")
        panel.show("東元", model)
        root.update()
        assert "禁止製造" in panel.reason.get()
        assert panel._numeric_spec is None
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
