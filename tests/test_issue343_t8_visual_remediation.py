# -*- coding: utf-8 -*-
"""#343 — T8 visual-remediation contracts for text-scale width and CJK Matplotlib."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from phase6_settings_center import ui_text_size_factor


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


TARGET_LEFT_WIDTHS = {"small": 338, "medium": 430, "large": 480}


def expected_left_width(scale: str) -> int:
    return TARGET_LEFT_WIDTHS[str(scale)]


def test_v2_width_floor_after_manual_screenshot_review():
    import fold_designer_bridge as bridge

    actual = {scale: bridge._phase6_left_workspace_width(scale) for scale in TARGET_LEFT_WIDTHS}
    failures = {
        scale: {"actual": actual[scale], "required": required}
        for scale, required in TARGET_LEFT_WIDTHS.items()
        if actual[scale] < required
    }
    assert not failures, (
        "#343 V2 EXPECTED RED: fresh T8 screenshot review still clips medium/large "
        f"left-pane controls; failures={failures!r}"
    )



def test_red_adaptive_left_workspace_and_cjk_theme_contract_exist():
    bridge = _text("fold_designer_bridge.py")
    theme = _text("whd_theme.py")
    text_scale = _text("ui_text_scale.py")
    required = (
        "def _phase6_left_workspace_width",
        "def _phase6_update_left_workspace_width",
        "canvas.configure(width=target)",
        '"Microsoft JhengHei"',
        '"Noto Sans CJK TC"',
        '"Noto Sans CJK SC"',
        "axes.unicode_minus",
    )
    combined = bridge + "\n" + theme
    missing = [token for token in required if token not in combined]
    assert "ui_text_size_factor" in text_scale
    assert not missing, (
        "#343 adaptive width/CJK presentation contracts drifted: "
        f"missing={missing!r}"
    )

@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
@pytest.mark.parametrize("scale", ("small", "medium", "large"))
def test_real_tk_left_workspace_width_tracks_text_scale_without_crushing_viewport(scale):
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": scale})
        for _ in range(4):
            root.update_idletasks(); root.update()

        actual = int(designer.left_scroll_canvas.winfo_width())
        assert actual >= expected_left_width(scale), (scale, actual, expected_left_width(scale))

        viewport = designer.renderer.canvas.get_tk_widget()
        assert viewport.winfo_ismapped()
        assert viewport.winfo_width() >= 760, (scale, viewport.winfo_width())
    finally:
        root.destroy()


def test_shared_mpl_theme_declares_cross_platform_cjk_fallbacks():
    import whd_theme

    families = tuple(whd_theme.MPL_CJK_FONT_FAMILIES)
    assert "Microsoft JhengHei" in families
    assert "Noto Sans CJK TC" in families
    assert "Noto Sans CJK SC" in families
    assert "sans-serif" in families


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_installed_cjk_font_is_selected_for_actual_matplotlib_text():
    import matplotlib
    from matplotlib import font_manager
    from matplotlib.figure import Figure
    import whd_theme

    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    whd_theme.apply_mpl_dark_theme(fig, ax)
    artist = ax.text2D(0.05, 0.95, "截角資料／組合體", transform=ax.transAxes)
    path = font_manager.findfont(artist.get_fontproperties(), fallback_to_default=True)
    normalized = path.replace("\\", "/").lower()
    assert "noto" in normalized or "jhenghei" in normalized or "pingfang" in normalized, path


def test_remediation_stays_presentation_only():
    changed_sources = (_text("fold_designer_bridge.py"), _text("whd_theme.py"))
    joined = "\n".join(changed_sources)
    assert "save_project_file(" not in _text("whd_theme.py")
    assert "manufacturing_api" not in _text("whd_theme.py")
    assert "PartSpec(" not in _text("whd_theme.py")
    assert "designer_workspace.add_part(" not in _text("whd_theme.py")
