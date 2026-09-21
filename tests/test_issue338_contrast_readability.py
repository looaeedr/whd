# -*- coding: utf-8 -*-
"""#338 T5 — shared-theme contrast and actual annotation colors."""
from __future__ import annotations

import math
import os
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_ttk_dark_theme


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _relative_luminance(color: str) -> float:
    value = str(color).strip().lstrip("#")
    assert len(value) == 6, f"expected #RRGGBB color, got {color!r}"
    channels = [int(value[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    a, b = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def test_shared_theme_standard_text_contrast_meets_4_5():
    pairs = {
        "normal-panel": (WHD_THEME["text"], WHD_THEME["panel"]),
        "normal-input": (WHD_THEME["text"], WHD_THEME["input"]),
        "muted-panel": (WHD_THEME["muted_text"], WHD_THEME["panel"]),
        "selected-action": ("#ffffff", WHD_THEME["action"]),
    }
    failures = {
        name: round(_contrast(fg, bg), 3)
        for name, (fg, bg) in pairs.items()
        if _contrast(fg, bg) < 4.5
    }
    assert not failures, (
        "#338 EXPECTED RED: standard-size text/effective selected text must "
        f"reach 4.5:1 using current WHD_THEME tokens; failures={failures!r}"
    )


def test_shared_theme_owns_secondary_warning_and_hidden_text_colors():
    bridge = _text("fold_designer_bridge.py")
    settings_panel = _text("phase6_settings_panel.py")
    gui = _text("gui.py")
    final_scene = _text("phase6_final_scene_renderer.py")

    for source in (bridge, settings_panel):
        assert "#777777" not in source
        assert 'foreground="#333"' not in source
        assert 'foreground="#b45309"' not in source
    assert 'WHD_THEME["muted_text"]' in bridge
    assert 'WHD_SEMANTIC_COLORS["warning"]' in settings_panel

    assert 'fill=WHD_SEMANTIC_COLORS["success"]' in gui
    assert 'color=WHD_THEME["text"]' in final_scene
    assert 'color=WHD_THEME["muted_text"]' in final_scene


def test_future_token_changes_are_not_duplicated_in_t5_contract():
    source = Path(__file__).read_text(encoding="utf-8").lower()
    # Resolve current palette values dynamically: the test must reference
    # production token names, not carry a second copy of their literal hex truth.
    for token in (
        WHD_THEME["muted_text"],
        WHD_THEME["panel"],
        WHD_THEME["input"],
        WHD_THEME["action"],
        WHD_THEME["action_hover"],
        WHD_THEME["action_pressed"],
    ):
        assert str(token).lower() not in source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
@pytest.mark.parametrize("ui_text_size", ("small", "medium", "large"))
def test_effective_ttk_and_tree_colors_remain_readable_at_all_text_scales(ui_text_size):
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": ui_text_size})
        for _ in range(4):
            root.update_idletasks(); root.update()

        style = ttk.Style(root)
        role_pairs = {
            "label": (
                style.lookup("TLabel", "foreground"),
                style.lookup("TLabel", "background"),
            ),
            "primary": (
                style.lookup("Primary.TButton", "foreground"),
                style.lookup("Primary.TButton", "background"),
            ),
            "primary-active": (
                style.lookup("Primary.TButton", "foreground", ("active",)),
                style.lookup("Primary.TButton", "background", ("active",)),
            ),
            "selector": (
                style.lookup("Selector.TMenubutton", "foreground"),
                style.lookup("Selector.TMenubutton", "background"),
            ),
        }
        for name, (fg, bg) in role_pairs.items():
            assert _contrast(fg, bg) >= 4.5, (
                f"{ui_text_size} {name} contrast too low: {fg} on {bg} = "
                f"{_contrast(fg, bg):.3f}"
            )

        hidden = str(designer.structure_tree.tag_configure("hidden", "foreground"))
        assert hidden.lower() == WHD_THEME["muted_text"].lower()
        assert _contrast(hidden, WHD_THEME["input"]) >= 4.5
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_canvas_finished_dimension_item_uses_shared_semantic_success_color():
    import gui

    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, background=WHD_THEME["canvas"])
        host = SimpleNamespace(
            _phase6_resolved_finished_dimensions=lambda _key: (100.0, 200.0),
            _fold_designer_number_text=lambda value: f"{float(value):g}",
        )
        dims = gui.Phase6ApplicationHost._draw_phase6_finished_dimension_summary(
            host, canvas, part_key="door"
        )
        assert dims == (100.0, 200.0)
        item = canvas.find_withtag("phase6_finished_dimensions")[0]
        fill = str(canvas.itemcget(item, "fill"))
        assert fill.lower() == WHD_SEMANTIC_COLORS["success"].lower()
        assert _contrast(fill, WHD_THEME["canvas"]) >= 4.5
    finally:
        root.destroy()


def test_matplotlib_dimension_artists_use_actual_shared_colors():
    matplotlib = pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure
    from phase6_final_scene_view import FinalSceneViewRequest, Phase6FinalSceneView

    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    renderer = SimpleNamespace(ax3d=ax)
    view = Phase6FinalSceneView(renderer)
    view._resolved_finished_dimensions = lambda _request, _triangles: (100.0, 200.0)
    request = FinalSceneViewRequest(
        render_data=SimpleNamespace(),
        x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 200.0, "core": "H"},),
        part_key="door",
        finished_dimensions=(100.0, 200.0),
    )
    view._draw_operator_dimensions(request, ())

    assert len(ax.texts) >= 3
    for artist in ax.texts:
        assert str(artist.get_color()).lower() == WHD_THEME["text"].lower()
        assert _contrast(str(artist.get_color()), WHD_THEME["canvas"]) >= 4.5
    assert len(ax.lines) >= 6
    for line in ax.lines[-6:]:
        assert str(line.get_color()).lower() == WHD_THEME["muted_text"].lower()
