# -*- coding: utf-8 -*-
"""Read-only saved EndCap live CHECK viewer; no new CAD or manufacturing owner."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, LinePrimitive, PolylinePrimitive, DrawingScene,
)
from gui_modules.drawing import render_drawing_scene

WINDOW_ATTR = "_endcap_live_saved_check_window"


def close_saved_live_check_window(host):
    """Invalidate the old window on project switch, replay failure or new view."""
    old = getattr(host, WINDOW_ATTR, None)
    setattr(host, WINDOW_ATTR, None)
    if old is not None:
        try:
            if old.winfo_exists():
                old.destroy()
        except tk.TclError:
            pass


class _ReadOnlyViewport:
    """Screen fit only. All CAD points remain original Engine CHECK points."""

    def __init__(self, scene, width, height):
        points = []
        for row in scene.primitives:
            if isinstance(row, PolylinePrimitive):
                points.extend((p.x, p.y) for p in row.points)
            elif isinstance(row, LinePrimitive):
                points.extend(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y)))
            elif isinstance(row, CirclePrimitive):
                x, y, r = row.center.x, row.center.y, row.radius
                points.extend(((x-r, y-r), (x+r, y+r)))
        if not points:
            raise ValueError("ENDCAP_SAVED_CHECK_2D_EMPTY")
        xmin = min(p[0] for p in points)
        xmax = max(p[0] for p in points)
        ymin = min(p[1] for p in points)
        ymax = max(p[1] for p in points)
        if xmax <= xmin or ymax <= ymin:
            raise ValueError("ENDCAP_SAVED_CHECK_2D_BOUNDS_INVALID")
        self.scale = min((width-60)/(xmax-xmin), (height-70)/(ymax-ymin))
        self._xmin = xmin
        self._ymax = ymax
        self._x0 = 30 + (width-60-(xmax-xmin)*self.scale)/2
        self._y0 = 34 + (height-70-(ymax-ymin)*self.scale)/2

    def world_to_canvas(self, p):
        return (self._x0+(p.x-self._xmin)*self.scale,
                self._y0+(self._ymax-p.y)*self.scale)


def show_saved_endcap_live_check_window(host, replayed, saved_record):
    """Render exactly ONE validated Engine replay, never live GUI choice/geometry."""
    if (replayed.part_key not in ("head", "tail")
            or replayed.corner_key != saved_record["corner_key"]
            or replayed.first_bend_axis != saved_record["first_bend_axis"]
            or not replayed.manufacturing_status.endswith("UNCERTIFIED")):
        raise ValueError("ENDCAP_SAVED_CHECK_REPLAY_SCOPE_INVALID")
    scene = replayed.full_sheet_check_scene
    true_t = replayed.factory_true_t_check
    if (not isinstance(scene, DrawingScene) or not scene.primitives
            or any(row.layer not in ("CHECK", "DATUM") for row in scene.primitives)):
        raise ValueError("ENDCAP_SAVED_CHECK_2D_SOURCE_UNAVAILABLE")
    if (true_t is None or not true_t.first_thick_solid_triangles
            or not true_t.second_thick_solid_triangles
            or not true_t.manufacturing_status.endswith("UNCERTIFIED")):
        raise ValueError("ENDCAP_SAVED_CHECK_FORMED_3D_UNAVAILABLE")
    first = tuple(true_t.first_thick_solid_triangles)
    second = tuple(true_t.second_thick_solid_triangles)

    # Delay graphics import until the operator opens the CHECK viewer.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from gui_modules.application.tail_d4_check_view import _fit_equal_3d

    parent = getattr(host, "root", None)
    win = tk.Toplevel(parent)
    try:
        part_label = {"head": "封頭", "tail": "封尾"}[replayed.part_key]
        corner_label = {
            "top_left": "左上", "top_right": "右上",
            "bottom_left": "左下", "bottom_right": "右下",
        }[replayed.corner_key]
        mode_label = {
            "ROUND_R": "圓角 R", "RELIEF_HOLE": "避空孔 Ø",
        }[saved_record["relief_mode"]]
        win.title("已保存試算／非加工｜" + part_label + " " + corner_label)
        win.geometry("1420x810")
        header = ttk.Frame(win)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(header, text=(
            "已保存試算／非加工　" + part_label + " " + corner_label
            + "　第一折：" + replayed.first_bend_axis.upper()
            + "　避裂：" + mode_label + "　｜僅 CHECK，不是加工圖"
        )).pack(anchor="w")
        ttk.Label(header, text=(
            "展開 2D 與折後 3D 均來自同一 Engine replay；"
            "3D 為未認證的零內 R／真板厚候選，不代表已驗密合。"
        )).pack(anchor="w")

        body = ttk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="2D 展開｜原料 DATUM／V 候選 CHECK").grid(
            row=0, column=0, sticky="w", padx=6)
        ttk.Label(body, text="折後 3D｜同源 Engine 真 T 候選").grid(
            row=0, column=1, sticky="w", padx=6)
        flat = tk.Canvas(body, width=675, height=640, bg="#162534",
                         highlightthickness=0)
        flat.grid(row=1, column=0, sticky="nsew", padx=6)
        viewport = _ReadOnlyViewport(scene, 675, 640)
        render_drawing_scene(flat, scene, viewport)
        flat.create_text(12, 624, anchor="w", fill="#dadfe6",
                         text="綠：CHECK 候選　紫：原板／折線 DATUM　單位 mm")

        figure = Figure(figsize=(6.7, 6.4), dpi=100)
        axis = figure.add_subplot(111, projection="3d")
        axis.add_collection3d(Poly3DCollection(
            first, facecolors="#0ea5e9", edgecolors="none", alpha=.65))
        axis.add_collection3d(Poly3DCollection(
            second, facecolors="#f59e0b", edgecolors="none", alpha=.65))
        _fit_equal_3d(axis, first + second)
        seam = replayed.ideal
        axis.plot((seam.formed_seam_start[0], seam.formed_seam_end[0]),
                  (seam.formed_seam_start[1], seam.formed_seam_end[1]),
                  (seam.formed_seam_start[2], seam.formed_seam_end[2]),
                  color="#dc2626", linewidth=2)
        axis.set_xlabel("X mm")
        axis.set_ylabel("Y mm")
        axis.set_zlabel("Z mm")
        axis.view_init(elev=25, azim=-55)
        axis.set_title("未認證折後真 T 候選｜紅線＝名義接縫")
        figure.tight_layout()
        canvas = FigureCanvasTkAgg(figure, master=body)
        canvas.get_tk_widget().grid(row=1, column=1, sticky="nsew", padx=6)
        canvas.draw()

        # These references live on the read-only popup only, never on Project.
        win._saved_endcap_check_replay = replayed
        win._saved_endcap_check_scene = scene
        win._saved_endcap_check_2d_canvas = flat
        win._saved_endcap_check_3d_figure = figure
        win._saved_endcap_check_3d_canvas = canvas
        win._saved_endcap_check_3d_triangles = (first, second)
        setattr(host, WINDOW_ATTR, win)
        win.protocol("WM_DELETE_WINDOW", lambda: close_saved_live_check_window(host))
        return win
    except Exception:
        win.destroy()
        raise
