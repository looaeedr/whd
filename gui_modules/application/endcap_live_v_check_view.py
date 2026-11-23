# -*- coding: utf-8 -*-
"""Read-only saved EndCap live CHECK viewer; no new CAD or manufacturing owner."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


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
            if hasattr(row, "points"):
                points.extend((p.x, p.y) for p in row.points)
            elif hasattr(row, "p1") and hasattr(row, "p2"):
                points.extend(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y)))
            elif hasattr(row, "center") and hasattr(row, "radius"):
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
    if (scene is None or not getattr(scene, "primitives", None)
            or any(row.layer not in ("CHECK", "DATUM") for row in scene.primitives)):
        raise ValueError("ENDCAP_SAVED_CHECK_2D_SOURCE_UNAVAILABLE")
    no_hole_3d = (true_t is None and replayed.factory_true_t_failure
                  == "V_MITER_LIVE_EXISTING_CUTTING_HOLE_3D_UNSUPPORTED")
    if not no_hole_3d and (true_t is None or not true_t.first_thick_solid_triangles
            or not true_t.second_thick_solid_triangles
            or not true_t.manufacturing_status.endswith("UNCERTIFIED")):
        raise ValueError("ENDCAP_SAVED_CHECK_FORMED_3D_UNAVAILABLE")
    first = () if no_hole_3d else tuple(true_t.first_thick_solid_triangles)
    second = () if no_hole_3d else tuple(true_t.second_thick_solid_triangles)

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
            "既有 CUTTING 穿孔已在同源 Engine 2D CHECK 保留；"
            "現有 Engine 不支援含孔厚板折後模型，因此不提供 3D。"
            if no_hole_3d else
            "2D 與 3D 均取自同一 Engine replay；"
            "3D 為避空前網格，不含左圖所選圓角／孔，"
            "不代表 R／BA 或折後密合已驗收。"
        )).pack(anchor="w")
        ttk.Button(
            header, text="關閉檢視／返回編輯",
            command=lambda: close_saved_live_check_window(host),
        ).pack(anchor="e")

        body = ttk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="2D 展開｜原料 DATUM／V 候選 CHECK").grid(
            row=0, column=0, sticky="w", padx=6)
        warning = ttk.Label(
            body, text=(
                "折後 3D｜既有穿孔未建模，不提供含孔厚板 3D"
                if no_hole_3d else
                "折後 3D｜避空前，不含左圖所選圓角／孔（非加工）"
            ),
        )
        warning.grid(row=0, column=1, sticky="w", padx=6)
        flat = tk.Canvas(body, width=675, height=640, bg="#162534",
                         highlightthickness=0)
        flat.grid(row=1, column=0, sticky="nsew", padx=6)
        viewport = _ReadOnlyViewport(scene, 675, 640)
        render_drawing_scene(flat, scene, viewport)
        flat.create_text(12, 624, anchor="w", fill="#dadfe6",
                         text="綠：CHECK 候選　紫：原板／折線 DATUM　單位 mm")

        figure = None
        canvas = None
        if no_hole_3d:
            ttk.Label(
                body, text=(
                    "此片有原生 CUTTING 內孔。現有 Engine 只有無孔的厚板折後網格；"
                    "不得以該網格冒充含孔的 3D。此處只提供可信的 2D CHECK。"
                ), wraplength=580, justify="left",
            ).grid(row=1, column=1, sticky="nw", padx=12, pady=24)
        else:
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
            axis.set_title("Pre-relief 3D | NO selected R / relief hole | CHECK")
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
        win._saved_endcap_check_3d_warning = warning
        # While this snapshot is displayed, prevent normal interaction with
        # the editable primary GUI (W, Fold, corner). No source can be edited
        # through the GUI until the operator closes this read-only window.
        if parent is not None and parent.winfo_viewable():
            win.transient(parent)
        win.wait_visibility()
        win.grab_set()
        win.focus_set()
        setattr(host, WINDOW_ATTR, win)
        win.protocol("WM_DELETE_WINDOW", lambda: close_saved_live_check_window(host))
        return win
    except Exception:
        win.destroy()
        raise


def show_saved_endcap_live_bottom_pair_window(
    host, replays, saved_records, *,
    one_sheet_check=None, one_sheet_unavailable=None,
):
    """Keep both individual CHECK scenes; optionally show Engine-proven ONE 2D.

    The new single-sheet scene is a separate Engine source/material delta
    result, NEVER an overlay of the two full-sheet corner scenes. 3D remains
    unsupported even when this strictly unmanufacturable 2D is valid.
    """
    from collections.abc import Mapping

    targets = ("bottom_left", "bottom_right")
    if (not isinstance(replays, Mapping) or not isinstance(saved_records, Mapping)
            or set(replays) != set(targets)
            or not set(targets) <= set(saved_records)):
        raise ValueError("ENDCAP_SAVED_TAIL_PAIR_BOTH_REPLAYS_REQUIRED")
    scenes = {}
    for key in targets:
        candidate = replays[key]
        record = saved_records[key]
        scene = candidate.full_sheet_check_scene
        if (candidate.part_key != "tail" or candidate.corner_key != key
                or candidate.first_bend_axis != "x"
                or record["corner_key"] != key or record["first_bend_axis"] != "x"
                or not candidate.manufacturing_status.endswith("UNCERTIFIED")
                or scene is None or not scene.primitives
                or any(row.layer not in ("CHECK", "DATUM") for row in scene.primitives)):
            raise ValueError("ENDCAP_SAVED_TAIL_PAIR_UNVERIFIED_SCENE")
        scenes[key] = scene

    if one_sheet_check is not None:
        combined_scene = one_sheet_check.scene
        # Presentation-only shape check; the public Engine projection
        # already owns typed geometry and the full physical source proof.
        # GUI must not import ae_engine internal drawing modules.
        check_outlines = [
            row for row in combined_scene.primitives
            if row.layer == "CHECK"
        ]
        if (not one_sheet_check.manufacturing_status.endswith("UNCERTIFIED")
                or not combined_scene.primitives
                or any(row.layer not in ("CHECK", "DATUM")
                       for row in combined_scene.primitives)
                or len(check_outlines) != 1
                or not getattr(check_outlines[0], "closed", False)
                or not getattr(check_outlines[0], "points", None)):
            raise ValueError("ENDCAP_SAVED_TAIL_PAIR_SINGLE_2D_UNVERIFIED")
    else:
        combined_scene = None

    parent = getattr(host, "root", None)
    win = tk.Toplevel(parent)
    try:
        win.title("已保存試算／非加工｜同片封尾 左下與右下分別 CHECK")
        win.geometry("1460x810")
        header = ttk.Frame(win)
        header.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(
            header, text=(
                "同一片封尾｜左右兩角已各自驗證來源｜X 先折、共用原 Y 折線"
                "｜兩張獨立 CHECK，非加工"
            ),
        ).pack(anchor="w")
        ttk.Label(
            header, text=(
                "Engine 已獨立證明真 Factory 角料的互斥 signed deltas，"
                "保留原始全部有限 BEND；新增一張真正同片雙角 2D CHECK。"
                "另可切換查看原左右各自的獨立 CHECK。"
                if combined_scene is not None else
                "同片完整雙 V 2D 物理證據未通過；只可查看左右獨立單角 CHECK，"
                "不可把兩張全板圖相疊冒充單片。拒絕原因：" +
                str(one_sheet_unavailable or "來源未通過 Factory/物理 BEND 核驗")
            ), wraplength=1370,
        ).pack(anchor="w", pady=(3, 4))
        ttk.Button(
            header, text="關閉檢視／返回編輯",
            command=lambda: close_saved_live_check_window(host),
        ).pack(anchor="e")

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        combined_canvas = None
        if combined_scene is not None:
            merged_area = ttk.Frame(notebook)
            notebook.add(merged_area, text="單片雙角 2D CHECK（非加工）")
            merged_area.columnconfigure(0, weight=1)
            merged_area.rowconfigure(1, weight=1)
            signed = dict(one_sheet_check.corner_signed_area_deltas_mm2)
            ttk.Label(
                merged_area,
                text=(
                    "同一原生 Custom 封尾｜下方左右雙 V，單一有效外輪廓"
                    "｜Factory 理論淨保留面積（左／右）"
                    f" {signed['bottom_left']:+.9f} / "
                    f"{signed['bottom_right']:+.9f} mm²；"
                    "非實際已切板補料，禁止加工"
                ), wraplength=1380,
            ).grid(row=0, column=0, sticky="w", padx=10, pady=4)
            combined_canvas = tk.Canvas(
                merged_area, width=1380, height=585, bg="#162534",
                highlightthickness=0,
            )
            combined_canvas.grid(row=1, column=0, sticky="nsew", padx=8)
            render_drawing_scene(
                combined_canvas, combined_scene,
                _ReadOnlyViewport(combined_scene, 1380, 585),
            )
            combined_canvas.create_text(
                12, 567, anchor="w", fill="#dadfe6",
                text=(
                    "單片雙角候選外輪廓 CHECK｜原 CUTTING／有限 BEND DATUM"
                    "｜mm｜非加工，無雙角成形 3D／R／BA 認證"
                ),
            )
        pair_area = ttk.Frame(notebook)
        notebook.add(pair_area, text="左右獨立單角 CHECK")
        pair_area.columnconfigure(0, weight=1)
        pair_area.columnconfigure(1, weight=1)
        pair_area.rowconfigure(1, weight=1)
        canvases = {}
        for column, key in enumerate(targets):
            label = "左下" if key == "bottom_left" else "右下"
            ttk.Label(
                pair_area,
                text=f"{label}｜原全板 DATUM + {label}單角 V 候選 CHECK (mm)",
            ).grid(row=0, column=column, sticky="w", padx=12, pady=(0, 4))
            canvas = tk.Canvas(
                pair_area, width=690, height=640, bg="#162534",
                highlightthickness=0,
            )
            canvas.grid(row=1, column=column, sticky="nsew", padx=8)
            viewport = _ReadOnlyViewport(scenes[key], 690, 640)
            render_drawing_scene(canvas, scenes[key], viewport)
            canvas.create_text(
                12, 622, anchor="w", fill="#dadfe6",
                text=f"{label}單角 CHECK｜不含另一角 V｜非加工",
            )
            canvases[key] = canvas

        warning = ttk.Label(
            win, text=(
                "折後 3D：不提供雙角合成 3D（同片 2D 不等於完整折後厚板"
                "／R／BA／兩折及接面驗收）。"
                "禁止把兩個單角 3D mesh 疊成同一片。"
            ),
        )
        warning.pack(anchor="w", padx=16, pady=(2, 10))
        win._saved_endcap_pair_replays = dict(replays)
        win._saved_endcap_pair_scenes = scenes
        win._saved_endcap_pair_2d_canvases = canvases
        win._saved_endcap_pair_combined_check = one_sheet_check
        win._saved_endcap_pair_combined_scene = combined_scene
        win._saved_endcap_pair_combined_canvas = combined_canvas
        win._saved_endcap_pair_2d_notebook = notebook
        win._saved_endcap_pair_3d_figure = None
        win._saved_endcap_pair_3d_warning = warning
        if parent is not None and parent.winfo_viewable():
            win.transient(parent)
        win.wait_visibility()
        win.grab_set()
        win.focus_set()
        setattr(host, WINDOW_ATTR, win)
        win.protocol("WM_DELETE_WINDOW", lambda: close_saved_live_check_window(host))
        return win
    except Exception:
        win.destroy()
        raise
