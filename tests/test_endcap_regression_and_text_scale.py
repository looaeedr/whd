# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    EndCapGeometry,
    ReliefConfig,
    calculate_endcap_relief_dimensions,
    resolve_corner_relief,
)
import phase6_settings_center as settings


def test_insert_overlay_secondary_cut_returns_to_legacy_c04_geometry():
    relief = resolve_corner_relief(
        CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY,
            amount_t=1.0,
            secondary_retain_t=0.5,
            secondary_depth_t=2.0,
        ),
        fold_u=15.0,
        fold_v=16.0,
        thickness=2.0,
        fw=25.0,
    )
    assert relief.primary_u == pytest.approx(40.0)
    assert relief.primary_v == pytest.approx(39.0)
    # UI 顯示「嵌入留肉 0.5T」，但實際 C04 二級切線仍是側折 + 0.5T。
    assert relief.secondary_u == pytest.approx(16.0)
    assert relief.secondary_depth == pytest.approx(4.0)


def test_fixed_vault_endcap_secondary_cut_returns_to_legacy_c04_geometry():
    geometry = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    dims = calculate_endcap_relief_dimensions(geometry, ReliefConfig())
    assert dims.top_secondary_left == pytest.approx(16.0)
    assert dims.top_secondary_right == pytest.approx(16.0)
    assert dims.top_secondary_depth_left == pytest.approx(4.0)
    assert dims.top_secondary_depth_right == pytest.approx(4.0)


def test_text_size_setting_is_global_choice_with_current_size_as_small():
    spec = next(spec for spec in settings.settings_for_context(settings.GLOBAL_CONTEXT) if spec.key == "ui_text_size")
    assert spec.label == "文字大小"
    assert spec.kind == "choice"
    assert spec.default == "small"
    assert settings.ui_text_size_label("small") == "小"
    assert settings.ui_text_size_label("medium") == "中"
    assert settings.ui_text_size_label("large") == "大"
    assert settings.ui_text_size_factor("small") == pytest.approx(1.0)
    assert settings.ui_text_size_factor("medium") > 1.0
    assert settings.ui_text_size_factor("large") > settings.ui_text_size_factor("medium")


def test_text_size_setting_persists_to_ini(monkeypatch, tmp_path):
    class FakeAE:
        INI_PATH = str(tmp_path / "config.ini")
        config = __import__("configparser").ConfigParser()
        default_config = {}

    ae = FakeAE()
    settings.save_defaults_to_ini(ae, {"ui_text_size": "large"}, keys=("ui_text_size",))
    loaded = settings.load_settings_from_ae(ae)
    assert loaded["ui_text_size"] == "large"
    text = Path(ae.INI_PATH).read_text(encoding="utf-8")
    assert "[UI]" in text
    assert "text_size = large" in text


def test_ui_sources_expose_small_medium_large_text_size_controls():
    root = Path(__file__).resolve().parents[1]
    gui_source = (root / "gui.py").read_text(encoding="utf-8")
    panel_source = (root / "phase6_settings_panel.py").read_text(encoding="utf-8")
    assert "文字大小" in gui_source
    assert "文字大小" in panel_source
    assert "UI_TEXT_SIZE_LABELS" in panel_source
    assert tuple(settings.UI_TEXT_SIZE_LABELS.values()) == ("小", "中", "大")
    for label in ("小", "中", "大"):
        assert label in gui_source


def test_text_scale_controller_scales_existing_and_future_tk_text(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import tkinter.font as tkfont
    from ui_text_scale import TextScaleController

    root = tk.Tk()
    try:
        label = tk.Label(root, text="測試", font=("Arial", 10))
        label.pack()
        canvas = tk.Canvas(root, width=200, height=80)
        canvas.pack()
        existing = canvas.create_text(50, 20, text="舊文字", font=("Arial", 10))
        root.update_idletasks()

        controller = TextScaleController.for_widget(root)
        controller.apply("medium")
        root.update_idletasks()
        label_size = tkfont.Font(root=root, font=label.cget("font")).actual("size")
        canvas_size = tkfont.Font(root=root, font=canvas.itemcget(existing, "font")).actual("size")
        assert label_size == 12
        assert canvas_size == 12

        future = canvas.create_text(50, 50, text="新文字", font=("Arial", 10))
        future_size = tkfont.Font(root=root, font=canvas.itemcget(future, "font")).actual("size")
        assert future_size == 12

        controller.apply("large")
        root.update_idletasks()
        assert tkfont.Font(root=root, font=label.cget("font")).actual("size") == 14
        assert tkfont.Font(root=root, font=canvas.itemcget(existing, "font")).actual("size") == 14
        assert tkfont.Font(root=root, font=canvas.itemcget(future, "font")).actual("size") == 14
    finally:
        root.destroy()
