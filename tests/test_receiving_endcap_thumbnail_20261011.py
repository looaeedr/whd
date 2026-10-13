# -*- coding: utf-8 -*-
"""Endcap thumbnails reflect actual Hole Editor features and per-Bay Apply."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

from ae_engine.sheetmetal_feature_core import (
    FeatureAnchor, CircleFeature, RectFeature, ProfileFeature,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.receiving_hole_candidates import (
    create_candidate, candidates_for, candidate_features,
)
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_shared_settings import edit_setting, setting_value
from gui_modules.application.receiving_endcap_thumbnail import (
    endcap_preview_geometry, paint_endcap_thumbnail,
)
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def circle():
    return CircleFeature(
        diameter=20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(40, 30), layer="CUTTING",
    )


def rectangle():
    return RectFeature(
        width=40, height=20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(120, 60), layer="MARKING", rotation_deg=90,
    )


def test_endcap_geometries_come_from_real_coordinates_and_layers():
    shapes, unsupported = endcap_preview_geometry(
        [circle(), rectangle()], 200, 100,
    )
    assert unsupported == 0
    assert shapes[0] == ("circle", "CUTTING", (40, 30, 10))
    assert shapes[1][0:2] == ("path", "MARKING")
    corners, closed = shapes[1][2]
    assert closed
    assert set(corners) == {(130, 40), (130, 80), (110, 80), (110, 40)}

    profile = ProfileFeature(
        points=(Vec2(0, 0), Vec2(15, 0), Vec2(15, 15)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(20, 20), layer="CUTTING",
    )
    shapes, unsupported = endcap_preview_geometry([profile], 200, 100)
    assert unsupported == 0
    assert shapes[0][2] == (((20, 20), (35, 20), (35, 35)), True)

    legacy = {"type": "圓形", "x": 55, "y": 25,
              "params": {"diameter": 12, "layer": "CUTTING"}}
    shapes, unsupported = endcap_preview_geometry([legacy], 200, 100)
    assert unsupported == 0
    assert shapes == (("circle", "CUTTING", (55.0, 25.0, 6.0)),)


def test_endcap_unknown_feature_is_reported_not_fabricated_as_hole():
    shapes, count = endcap_preview_geometry([{"tag": "legacy-unknown"}], 200, 100)
    assert shapes == ()
    assert count == 1


def test_endcap_canvas_has_true_scaled_circle_and_never_promotes_unknown_to_hole():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=220, height=134)
        canvas.pack()
        result = paint_endcap_thumbnail(
            canvas, [circle(), rectangle()], 200, 100, title="封頭目前",
        )
        assert result["unsupported"] == 0
        assert result["counts"] == {"CUTTING": 1, "MARKING": 1}
        assert len(canvas.find_withtag("feature")) == 2
        oval = next(item for item in canvas.find_withtag("feature")
                    if canvas.type(item) == "oval")
        x0, y0, x1, y1 = canvas.coords(oval)
        assert abs((x0+x1)/2 - (42.5+40*0.68)) < 1
        assert abs((y0+y1)/2 - (29+70*0.68)) < 1
        assert abs(x1-x0 - 20*0.68) < 1
        result = paint_endcap_thumbnail(
            canvas, [{"tag": "unknown"}], 200, 100,
        )
        assert result["unsupported"] == 1
        assert not canvas.find_withtag("feature")
        assert any("無法預覽" in canvas.itemcget(i, "text")
                   for i in canvas.find_all() if canvas.type(i) == "text")
        result = paint_endcap_thumbnail(canvas, None, 200, 100)
        assert result["source_count"] is None
        assert any("尚未選擇" in canvas.itemcget(i, "text")
                   for i in canvas.find_all() if canvas.type(i) == "text")
    finally:
        root.destroy()


def test_head_tail_candidates_are_separately_previewed_and_applied_to_real_bay():
    root = tk.Tk()
    root.withdraw()
    library, head_id = create_candidate(None, "head", [circle()])
    library, tail_id = create_candidate(library, "tail", [rectangle()])
    layout = {"value": new_receiving_layout(width=200, height=1600, depth=100)}
    selected = {"bay": 0}
    applied_calls = []

    def ports(_si):
        def change(kind, value, indices=()):
            for i in indices or (selected["bay"],):
                layout["value"] = edit_setting(
                    layout["value"], set_index=0, bay_index=i,
                    kind=kind, value=value,
                )
        return {
            "row": lambda: layout["value"]["sets"][0],
            "select": lambda index: selected.__setitem__("bay", index),
            "change": change,
        }

    def get_candidate_ports():
        def apply(role, version, si, bays):
            assert si == 0
            for bay in bays:
                layout["value"] = edit_setting(
                    layout["value"], set_index=si, bay_index=bay,
                    kind=role + "_features",
                    value=candidate_features(library, role, version),
                )
            applied_calls.append((role, version, tuple(bays)))
        return {
            "versions": lambda role: candidates_for(library, role),
            "apply": apply,
            "edit": lambda *_args: None,
        }

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
            get_candidate_ports=get_candidate_ports,
            get_settings_ports=ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        lst = win._receiving_multi_setting_list
        lst.selection_set(0)
        lst.event_generate("<<ListboxSelect>>")
        root.update()

        # Both endcap roles keep independent settings; the old embedded
        # thumbnails have been replaced by one opt-in floating true view.
        assert win._receiving_multi_real_preview["win"] is None
        assert not any(
            isinstance(w, tk.Canvas)
            for w in win._receiving_multi_settings_host.winfo_children()
        )
        head_combo = win._receiving_multi_candidate_combos["head"]
        head_combo.set("版本一")
        head_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        row_head = win._receiving_multi_settings_host.winfo_children()[0]
        next(w for w in row_head.winfo_children()
             if isinstance(w, ttk.Button) and w.cget("text") == "套用").invoke()
        root.update()
        assert applied_calls == [("head", head_id, (0,))]
        assert setting_value(layout["value"]["sets"][0], 0, "tail_features") == []

        tail_combo = win._receiving_multi_candidate_combos["tail"]
        tail_combo.set("版本一")
        tail_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        row_tail = win._receiving_multi_settings_host.winfo_children()[1]
        next(w for w in row_tail.winfo_children()
             if isinstance(w, ttk.Button) and w.cget("text") == "套用").invoke()
        root.update()
        assert applied_calls[-1] == ("tail", tail_id, (0,))
        assert setting_value(layout["value"]["sets"][0], 0, "head_features") == [circle()]
        assert setting_value(layout["value"]["sets"][0], 0, "tail_features") == [rectangle()]
        win._receiving_multi_close()
    finally:
        root.destroy()
