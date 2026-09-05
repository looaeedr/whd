from pathlib import Path
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


def test_home_no_longer_exposes_duplicate_relief_or_legacy_notch_controls():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    assert "顯示截角底層相容參數" not in source
    assert "left_advanced_settings_frame" not in source


def test_unfolded_size_uses_canonical_final_material_not_raw_profiles(monkeypatch):
    from shapely.geometry import box
    from ae_engine.manufacturing_api import PartRenderData

    holder = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="door"),
        active_part_key="door",
        state=SimpleNamespace(
            profiles={"X": [{"len": 999}], "Y": [{"len": 999}]},
            profiles_vault={"箱身": [{"len": 999}]},
        ),
        _phase6_part_profiles={},
        _settings_values={"h": 600, "t": 2, "fw": 25, "z_comp": 6},
        _phase6_corner_state={},
    )
    render = PartRenderData(scene=object(), material=box(-10, -20, 120, 220))
    monkeypatch.setattr(bridge, "_phase6_query_final_render_data", lambda _self: render)

    assert bridge._phase6_current_unfolded_size(holder, "door") == (130.0, 240.0)
    assert bridge._phase6_format_unfolded_blank_text(render, part_key="door").startswith(
        "展開料：130 × 240 mm"
    )
    assert "淨面積" not in bridge._phase6_format_unfolded_blank_text(render, part_key="door")


def test_scroll_zoom_changes_only_view_scale_and_is_bounded():
    holder = SimpleNamespace(_phase6_zoom_scale=1.0)
    bridge._phase6_adjust_zoom_scale(holder, "up")
    assert holder._phase6_zoom_scale < 1.0
    for _ in range(100):
        bridge._phase6_adjust_zoom_scale(holder, "up")
    assert holder._phase6_zoom_scale >= bridge._PHASE6_ZOOM_MIN
    for _ in range(200):
        bridge._phase6_adjust_zoom_scale(holder, "down")
    assert holder._phase6_zoom_scale <= bridge._PHASE6_ZOOM_MAX


def test_real_tk_3d_only_layout_scroll_zoom_and_unfolded_size_label():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("door")
        root.update_idletasks(); root.update()

        assert designer.renderer.ax2d.get_visible() is False
        assert designer.renderer.ax3d.get_position().height > 0.80
        assert "展開料：" in designer.unfolded_size_var.get()
        assert "×" in designer.unfolded_size_var.get()
        assert not any(key.startswith(("relief_", "notch_")) for key in designer.left_global_vars)

        old = designer._phase6_zoom_scale
        settings_before = dict(designer._settings_values)
        event = SimpleNamespace(inaxes=designer.renderer.ax3d, button="up")
        designer.on_3d_scroll(event)
        assert designer._phase6_zoom_scale < old
        assert designer._settings_values == settings_before

        old_text = designer.unfolded_size_var.get()
        designer.activate_part("head")
        root.update_idletasks(); root.update()
        assert designer.unfolded_size_var.get() != old_text
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_phase6_3d_view_configuration_does_not_rewrite_fold_geometry_through_projection_policy():
    from matplotlib.figure import Figure
    from types import SimpleNamespace

    fig = Figure()
    ax3d = fig.add_subplot(121, projection='3d')
    ax2d = fig.add_subplot(122)
    ax3d.set_proj_type('persp', focal_length=1.25)
    before = float(ax3d._focal_length)
    holder = SimpleNamespace(renderer=SimpleNamespace(ax3d=ax3d, ax2d=ax2d))

    bridge._phase6_configure_3d_only_figure(holder)

    # View setup must not be used as a band-aid for bend-angle bugs.
    assert float(ax3d._focal_length) == pytest.approx(before)
