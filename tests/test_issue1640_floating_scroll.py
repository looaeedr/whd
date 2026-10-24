"""#1640 end-to-end Tk UX contract: real floating view and scoped scrolling."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_hole_candidates import create_candidate, candidates_for
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application import receiving_settings_preview_2d as real_module
from gui_modules.application.receiving_scroll_view import make_scrollable_frame
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_overflow_scrollbars_scoped_to_hovered_pane():
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    try:
        holder, content, viewport = make_scrollable_frame(
            win, tk=tk, ttk=ttk, width=240, height=160,
        )
        holder.pack(fill="both", expand=True)
        for i in range(65):
            ttk.Label(content, text=f"第{i}項　長文字" * 3).pack(anchor="w")
        win.geometry("330x250")
        root.update()
        assert viewport.yview()[1] < 1
        assert viewport.xview()[1] < 1
        before = viewport.yview()
        viewport.event_generate("<MouseWheel>", delta=-120)
        root.update()
        assert viewport.yview()[0] > before[0]
        before_x = viewport.xview()
        viewport.event_generate("<MouseWheel>", delta=-120, state=1)
        root.update()
        assert viewport.xview()[0] > before_x[0]
        # Linux wheel events move the SAME hovered pane.
        before_y = viewport.yview()
        viewport.event_generate("<Button-5>")
        root.update()
        assert viewport.yview()[0] >= before_y[0]
    finally:
        win.destroy()
        root.destroy()


def test_real_popup_reuses_one_nonmodal_toplevel_without_applying_candidate(monkeypatch):
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    calls = []
    views = []
    # Real Hole Editor Feature, not the pre-contract arbitrary-dict fixture.
    saved, version = create_candidate(None, "head", [
        CircleFeature(
            diameter=10.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0.0, 0.0),
        )
    ])

    class FakeView:
        def __init__(self, parent, *, tk, ttk, requests):
            self.requests = tuple(requests)
            self.drawn = []
            self.failures = []
            views.append(self)

        def draw_geometry(self, requests):
            self.drawn.append(tuple(requests))

        def invalidate(self, message):
            self.failures.append(str(message))

        def zoom(self, factor):
            pass

        def reset_view(self):
            pass

    monkeypatch.setattr(real_module, "ReceivingSettingsPreview2D", FakeView)
    scene = object()

    def real_preview(role, version_id, si, bi):
        calls.append((role, version_id, si, bi))
        return scene

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
            get_candidate_ports=lambda: {
                "versions": lambda role: candidates_for(saved, role),
                "apply": lambda *_args: None,
                "edit": lambda *_args: None,
            },
            get_settings_ports=lambda _si: {
                "row": lambda: new_receiving_layout(width=800, height=1600, depth=350)["sets"][0],
                "select": lambda _bi: None,
            },
            get_real_cut_preview_request=real_preview,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        chooser = win._receiving_multi_candidate_combos["head"]
        chooser.set("版本一")
        chooser.event_generate("<<ComboboxSelected>>")
        root.update()
        popup = win._receiving_multi_real_preview["win"]
        assert popup is not None and popup.winfo_exists()
        assert popup.grab_current() is popup
        assert calls == [("head", version, 0, 0)]
        assert views[0].drawn == [(scene,)]
        assert popup._receiving_real_preview_request is scene

        chooser.set("即時")
        chooser.event_generate("<<ComboboxSelected>>")
        root.update()
        assert win._receiving_multi_real_preview["win"] is popup
        assert calls[-1] == ("head", None, 0, 0)
        assert len(views) == 1
        win._receiving_multi_close_real_preview()
        assert not popup.winfo_exists()
        win._receiving_multi_close()
    finally:
        root.destroy()
