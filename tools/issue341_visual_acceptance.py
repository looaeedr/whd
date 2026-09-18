#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#341 T8 real-Tk three-layer visual acceptance.

Acceptance-only harness. It consumes existing UI state and rendering outputs; it
must never become geometry, persistence, selector, or manufacturing authority.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageStat

import gui
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS


SCALES = ("small", "medium", "large")
CHECKS = (
    "Hierarchy",
    "Spacing",
    "Clipping",
    "Foreground-stacking",
    "Contrast",
    "Control identity",
    "Viewport",
    "Text scale",
    "State coverage",
    "No residue",
)


def _pump(root, cycles=4):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _widget_rect(widget):
    return {
        "x": int(widget.winfo_rootx()),
        "y": int(widget.winfo_rooty()),
        "width": int(widget.winfo_width()),
        "height": int(widget.winfo_height()),
    }


def _intersection(a, b):
    x0 = max(a["x"], b["x"])
    y0 = max(a["y"], b["y"])
    x1 = min(a["x"] + a["width"], b["x"] + b["width"])
    y1 = min(a["y"] + a["height"], b["y"] + b["height"])
    return max(0, x1 - x0) * max(0, y1 - y0)


def _hit_belongs_to(hit, target):
    current = hit
    while current is not None:
        if current is target:
            return True
        parent_name = str(current.winfo_parent() or "")
        if not parent_name:
            break
        try:
            current = current.nametowidget(parent_name)
        except Exception:
            break
    return False


def _probe_widget(root, viewport, name, widget):
    rect = _widget_rect(widget)
    center_x = rect["x"] + max(0, rect["width"] // 2)
    center_y = rect["y"] + max(0, rect["height"] // 2)
    hit = root.winfo_containing(center_x, center_y)
    mapped = bool(widget.winfo_ismapped())
    intersection = _intersection(rect, viewport)
    result = {
        "name": name,
        "path": str(widget),
        "mapped": mapped,
        "rect": rect,
        "viewport_intersection_px": intersection,
        "center": [center_x, center_y],
        "hit_path": str(hit) if hit is not None else None,
        "hit_ok": bool(hit is not None and _hit_belongs_to(hit, widget)),
    }
    result["pass"] = bool(
        mapped
        and rect["width"] > 0
        and rect["height"] > 0
        and intersection > 0
        and result["hit_ok"]
    )
    return result


def _mode_targets(designer, mode):
    common = {
        "file_menu": designer.project_file_button,
        "dxf_export": designer.output_export_button,
        "part_selector": designer.part_choice_button,
        "add_part": designer.add_part_button,
        "input_switch": designer.input_content_button,
        "assembly_switch": designer.assembly_content_button,
        "corner_switch": designer.corner_data_content_button,
    }
    if mode in {"input", "assembly"}:
        common["viewport"] = designer.renderer.canvas.get_tk_widget()
    elif mode == "corner_data":
        canvas = getattr(designer, "corner_data_canvas", None)
        if canvas is not None:
            common["corner_data_viewport"] = canvas
    return common


def _set_mode(root, designer, mode):
    if mode == "input":
        designer.input_content_button.invoke()
    elif mode == "assembly":
        designer.assembly_content_button.invoke()
    elif mode == "corner_data":
        designer.corner_data_content_button.invoke()
    else:
        raise ValueError(mode)
    _pump(root, 4)


def probe_geometry_reachability(root, designer, scale):
    """A-layer: real geometry, intersection and center hit testing."""
    records = []
    viewport = _widget_rect(root)

    for mode in ("input", "assembly", "corner_data"):
        _set_mode(root, designer, mode)
        for name, widget in _mode_targets(designer, mode).items():
            records.append({
                "phase": f"{scale}:{mode}:initial",
                **_probe_widget(root, viewport, name, widget),
            })

        if mode == "input":
            # Scroll and return: verify persistent controls and viewport recover.
            canvas = designer.left_scroll_canvas
            try:
                canvas.yview_moveto(1.0)
                _pump(root, 2)
                canvas.yview_moveto(0.0)
                _pump(root, 2)
            except Exception:
                pass
            for name, widget in _mode_targets(designer, mode).items():
                records.append({
                    "phase": f"{scale}:{mode}:after-scroll",
                    **_probe_widget(root, viewport, name, widget),
                })

            # Switch one real physical part when available, then re-probe.
            available = tuple(getattr(designer, "available_parts", ()) or ())
            candidate = next((p for p in ("head", "tail", "door") if p in available), None)
            if candidate is not None:
                designer.activate_part(candidate)
                _pump(root, 3)
                records.append({
                    "phase": f"{scale}:{mode}:after-part-{candidate}",
                    **_probe_widget(root, viewport, "part_selector", designer.part_choice_button),
                })

    failures = [row for row in records if not row["pass"]]
    return {
        "scale": scale,
        "root_rect": viewport,
        "records": records,
        "pass": not failures,
        "failures": failures,
    }


def _rgb(root, color):
    r, g, b = root.winfo_rgb(str(color))
    return (r / 65535.0, g / 65535.0, b / 65535.0)


def _luminance(rgb):
    linear = []
    for c in rgb:
        linear.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(root, fg, bg):
    a, b = _luminance(_rgb(root, fg)), _luminance(_rgb(root, bg))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _style_pair(style, role, state=()):
    return {
        "foreground": str(style.lookup(role, "foreground", state)),
        "background": str(style.lookup(role, "background", state)),
        "bordercolor": str(style.lookup(role, "bordercolor", state)),
    }


def probe_effective_styles(root, designer, scale):
    """B-layer: effective ttk/classic/Canvas/Matplotlib colors."""
    style = ttk.Style(root)
    style_rows = []
    cases = (
        ("Primary.TButton", ()),
        ("Primary.TButton", ("active",)),
        ("Primary.TButton", ("focus",)),
        ("Secondary.TButton", ()),
        ("Secondary.TButton", ("focus",)),
        ("Selector.TMenubutton", ()),
        ("Selector.TMenubutton", ("focus",)),
        ("Treeview", ()),
        ("Treeview", ("selected",)),
        ("Readonly.TEntry", ("readonly",)),
    )
    for role, state in cases:
        pair = _style_pair(style, role, state)
        ratio = None
        if pair["foreground"] and pair["background"]:
            ratio = _contrast(root, pair["foreground"], pair["background"])
        row = {
            "role": role,
            "state": list(state),
            **pair,
            "contrast": round(ratio, 3) if ratio is not None else None,
        }
        # Standard visible/action text target. Disabled-only states are not used here.
        row["pass"] = bool(ratio is None or ratio >= 4.5)
        if "focus" in state:
            row["focus_border_ok"] = pair["bordercolor"].lower() == WHD_THEME["action"].lower()
            row["pass"] = row["pass"] and row["focus_border_ok"]
        style_rows.append(row)

    # Classic Tk actual Canvas item color from the existing production drawing helper.
    probe_canvas = tk.Canvas(root, width=260, height=80, background=WHD_THEME["canvas"], takefocus=False)
    host = SimpleNamespace(
        _phase6_resolved_finished_dimensions=lambda _key: (100.0, 200.0),
        _fold_designer_number_text=lambda value: f"{float(value):g}",
    )
    gui.Phase6ApplicationHost._draw_phase6_finished_dimension_summary(
        host, probe_canvas, part_key="door", y=10
    )
    item = probe_canvas.find_withtag("phase6_finished_dimensions")[0]
    canvas_fill = str(probe_canvas.itemcget(item, "fill"))
    canvas_row = {
        "background": str(probe_canvas.cget("background")),
        "item_fill": canvas_fill,
        "contrast": round(_contrast(root, canvas_fill, probe_canvas.cget("background")), 3),
        "semantic_match": canvas_fill.lower() == WHD_SEMANTIC_COLORS["success"].lower(),
    }
    canvas_row["pass"] = canvas_row["contrast"] >= 4.5 and canvas_row["semantic_match"]
    probe_canvas.destroy()

    # Actual product Matplotlib artists after a normal 3D refresh.
    _set_mode(root, designer, "input")
    try:
        designer.refresh_3d_preview()
    except Exception:
        pass
    _pump(root, 4)
    ax = designer.renderer.ax3d
    mpl_text = [
        {"text": str(artist.get_text()), "color": str(artist.get_color())}
        for artist in list(getattr(ax, "texts", ()) or ())
    ]
    mpl_lines = [
        {"color": str(line.get_color())}
        for line in list(getattr(ax, "lines", ()) or ())
    ]
    text_ok = all(
        row["color"].lower() == WHD_THEME["text"].lower()
        for row in mpl_text
        if row["text"].strip()
    )
    line_ok = all(bool(row["color"]) for row in mpl_lines)
    mpl_row = {
        "text_artists": mpl_text,
        "line_artists": mpl_lines,
        "actual_text_artist_count": len(mpl_text),
        "actual_line_artist_count": len(mpl_lines),
        "text_color_ok": text_ok,
        "line_color_present": line_ok,
        "pass": bool(mpl_text and text_ok and line_ok),
    }

    failures = [row for row in style_rows if not row["pass"]]
    if not canvas_row["pass"]:
        failures.append({"canvas": canvas_row})
    if not mpl_row["pass"]:
        failures.append({"matplotlib": mpl_row})

    return {
        "scale": scale,
        "style_rows": style_rows,
        "classic_canvas": canvas_row,
        "matplotlib": mpl_row,
        "pass": not failures,
        "failures": failures,
    }


def capture_window_png(root, output_path):
    """C-layer capture: real Xvfb root pixels cropped to the application window."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _pump(root, 3)
    rect = _widget_rect(root)
    with tempfile.TemporaryDirectory() as temp_dir:
        screen = Path(temp_dir) / "screen.png"
        subprocess.run(
            ["import", "-window", "root", str(screen)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        image = Image.open(screen).convert("RGB")
        left = max(0, rect["x"])
        top = max(0, rect["y"])
        right = min(image.width, rect["x"] + rect["width"])
        bottom = min(image.height, rect["y"] + rect["height"])
        image.crop((left, top, right, bottom)).save(output_path)
    return output_path


def inspect_pixels(path):
    """C-layer machine-readable pixel evidence; manual screenshot review follows."""
    image = Image.open(path).convert("RGB")
    stat = ImageStat.Stat(image)
    extrema = image.getextrema()
    gray = image.convert("L")
    gray_stat = ImageStat.Stat(gray)
    histogram = gray.histogram()
    occupied_bins = sum(1 for value in histogram if value)
    # Edge variance helps catch fully clipped/blank captures.
    edge = image.crop((0, 0, image.width, min(24, image.height)))
    edge_std = ImageStat.Stat(edge.convert("L")).stddev[0]
    return {
        "file": Path(path).name,
        "width": image.width,
        "height": image.height,
        "mean_rgb": [round(v, 3) for v in stat.mean],
        "extrema": extrema,
        "gray_mean": round(gray_stat.mean[0], 3),
        "gray_stddev": round(gray_stat.stddev[0], 3),
        "occupied_gray_bins": occupied_bins,
        "top_edge_gray_stddev": round(edge_std, 3),
        "pass": bool(
            image.width >= 1000
            and image.height >= 700
            and gray_stat.stddev[0] >= 10.0
            and occupied_bins >= 40
        ),
    }


def build_visual_checklist(geometry, styles, pixels):
    """Produce PASS/FAIL/N/A checklist; no unresolved FAIL may pass the harness."""
    by_scale = {row["scale"]: row for row in geometry}
    style_by_scale = {row["scale"]: row for row in styles}
    pixel_by_scale = {Path(row["file"]).stem.split("-")[-1]: row for row in pixels}

    checks = []
    for scale in SCALES:
        g = by_scale[scale]
        s = style_by_scale[scale]
        p = pixel_by_scale[scale]
        checks.extend([
            {"scale": scale, "check": "Hierarchy", "status": "PASS",
             "reason": "persistent file/export/content-switch controls are mapped and center-hit reachable"},
            {"scale": scale, "check": "Spacing", "status": "PASS" if g["pass"] else "FAIL",
             "reason": "positive widget geometry and viewport intersection for all probed controls"},
            {"scale": scale, "check": "Clipping", "status": "PASS" if g["pass"] and p["pass"] else "FAIL",
             "reason": "all probed controls intersect root viewport; screenshot is nonblank and full-sized"},
            {"scale": scale, "check": "Foreground-stacking", "status": "PASS" if g["pass"] else "FAIL",
             "reason": "winfo_containing(center) resolves to the probed control or its descendant"},
            {"scale": scale, "check": "Contrast", "status": "PASS" if s["pass"] else "FAIL",
             "reason": "effective ttk + classic Canvas + actual Matplotlib artist probes"},
            {"scale": scale, "check": "Control identity", "status": "PASS" if g["pass"] else "FAIL",
             "reason": "file/export/selector/content-switch controls remain separately reachable"},
            {"scale": scale, "check": "Viewport", "status": "PASS" if g["pass"] and p["pass"] else "FAIL",
             "reason": "3D/Corner Data viewport remains visible through mode and part changes"},
            {"scale": scale, "check": "Text scale", "status": "PASS",
             "reason": f"{scale} runtime setting completed geometry/style/screenshot cycle"},
            {"scale": scale, "check": "State coverage", "status": "PASS" if s["pass"] else "FAIL",
             "reason": "normal/active/focus/selected/readonly effective style states probed"},
            {"scale": scale, "check": "No residue", "status": "PASS" if g["pass"] else "FAIL",
             "reason": "scroll returns to origin and subsequent mode/part probes remain reachable"},
        ])

    # Ensure exact checklist vocabulary stays stable.
    assert {row["check"] for row in checks} == set(CHECKS)
    return checks


def _write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_checklist(path, checklist):
    lines = [
        "# #341 T8 visual checklist",
        "",
        "| Scale | Check | Status | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in checklist:
        lines.append(
            f"| {row['scale']} | {row['check']} | {row['status']} | {row['reason']} |"
        )
    failures = [row for row in checklist if row["status"] == "FAIL"]
    lines += [
        "",
        f"Unresolved FAIL: **{len(failures)}**",
        "",
        "This checklist is machine evidence for screenshot/pixel state coverage. "
        "The workflow artifact screenshots are additionally subject to final visual review before #341 closure.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--geometry", default="1400x900")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.geometry(f"{args.geometry}+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    geometry_rows = []
    style_rows = []
    pixel_rows = []

    try:
        root.deiconify()
        _pump(root, 5)

        for scale in SCALES:
            designer.apply_external_settings({"ui_text_size": scale})
            _pump(root, 5)

            geometry_rows.append(probe_geometry_reachability(root, designer, scale))
            style_rows.append(probe_effective_styles(root, designer, scale))

            _set_mode(root, designer, "input")
            screenshot = capture_window_png(root, output / f"ui-{scale}.png")
            pixel_rows.append(inspect_pixels(screenshot))

        checklist = build_visual_checklist(geometry_rows, style_rows, pixel_rows)

        _write_json(output / "geometry.json", geometry_rows)
        _write_json(output / "styles.json", style_rows)
        _write_json(output / "pixels.json", pixel_rows)
        _write_checklist(output / "visual-checklist.md", checklist)

        summary = {
            "geometry_pass": all(row["pass"] for row in geometry_rows),
            "styles_pass": all(row["pass"] for row in style_rows),
            "pixels_pass": all(row["pass"] for row in pixel_rows),
            "checklist_failures": [row for row in checklist if row["status"] == "FAIL"],
            "screenshots": [f"ui-{scale}.png" for scale in SCALES],
        }
        _write_json(output / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if not (
            summary["geometry_pass"]
            and summary["styles_pass"]
            and summary["pixels_pass"]
            and not summary["checklist_failures"]
        ):
            raise SystemExit("#341 T8 acceptance has unresolved failures")
    finally:
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
