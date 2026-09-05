# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest
from matplotlib.figure import Figure

import fold_designer_bridge as bridge


def _door_profiles():
    snapshot = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 15.0,
        "door_fold_t": 15.0, "door_fold_b": 15.0,
        "part_dimensions": {"door": {"width": 335.0, "height": 535.0}},
    }
    return snapshot, bridge.build_standard_part_profiles(snapshot, "door")


def test_configured_3d_view_hides_coordinate_axes():
    fig = Figure(figsize=(5, 4))
    ax3d = fig.add_subplot(121, projection="3d")
    ax2d = fig.add_subplot(122)
    holder = SimpleNamespace(renderer=SimpleNamespace(ax3d=ax3d, ax2d=ax2d))

    bridge._phase6_configure_3d_only_figure(holder)

    assert ax2d.get_visible() is False
    assert ax3d.axison is False


def test_operator_dimensions_use_finished_door_w_h_not_engine_core_lengths():
    snapshot, profiles = _door_profiles()
    fig = Figure(figsize=(5, 4))
    ax = fig.add_subplot(111, projection="3d")
    holder = SimpleNamespace(
        active_part_key="door",
        renderer=SimpleNamespace(ax3d=ax),
        _phase6_input_snapshot=snapshot,
        _settings_values={},
    )

    bridge._phase6_draw_operator_dimensions(holder, profiles["X"], profiles["Y"])
    texts = [str(t.get_text()) for t in ax.texts]

    assert any("W 335" in t for t in texts)
    assert any("H 535" in t for t in texts)
    assert not any("W 331" in t for t in texts)
    assert not any("H 531" in t for t in texts)


def test_default_operator_view_projects_tall_door_taller_than_wide():
    # Camera contract: W is screen-horizontal, H is screen-vertical enough that
    # a 335x535 door still looks portrait instead of visually swapped.
    elev, azim = bridge._PHASE6_DEFAULT_VIEW
    assert elev >= 45
    assert azim == pytest.approx(-90.0)


def test_existing_main_text_scale_controller_is_reused_without_root_rescan():
    calls = []
    main_root = object()
    top = object()
    controller = SimpleNamespace(root=main_root, factor=1.25, apply=lambda value: calls.append(value))

    result = bridge._phase6_prepare_text_scale_controller(top, "medium", controller=controller)

    assert result is controller
    assert calls == []


def test_real_first_door_selection_coalesces_to_one_canvas_draw():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        canvas = designer.renderer.canvas
        original_draw = canvas.draw
        calls = []

        def counted_draw(*args, **kwargs):
            calls.append(1)
            return original_draw(*args, **kwargs)

        canvas.draw = counted_draw
        designer.activate_part("door")
        root.update_idletasks(); root.update()
        assert len(calls) == 1
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
