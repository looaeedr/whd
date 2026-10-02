from __future__ import annotations

import os
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.contracts import BoxBodyPartSpec
from ae_engine.manufacturing_api import build_part_render_data
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments


def _receiving_values():
    values = apply_family_defaults({
        "model": "金庫型",
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 2.0,
    })
    values["model"] = "受電箱"
    return values


def _box_spec(values, *, profile):
    return BoxBodyPartSpec(
        width=float(values["w"]),
        height=float(values["h"]),
        depth=float(values["d"]),
        thickness=float(values["t"]),
        frame_width=float(values["fw"]),
        model_name=str(values.get("model") or ""),
        zl1=float(values["zl1"]),
        zl2=float(values["zl2"]),
        zr1=float(values.get("zr1", 15.0)),
        zr2=float(values["zr2"]),
        z_comp=float(values.get("z_comp", 2.0)),
        fold_profile=profile,
    )


def test_receiving_canonical_profile_guard_is_1596():
    values = _receiving_values()
    profile = build_box_body_profile(values)
    assert [row.get("phase6_key") for row in profile] == [
        "zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"
    ]
    assert [float(row["len"]) for row in profile] == pytest.approx(
        [22.0, 20.0, 25.0, 346.0, 796.0, 346.0, 25.0, 16.0]
    )
    assert sum(float(row["len"]) for row in profile) == pytest.approx(1596.0)

    render = build_part_render_data(
        _box_spec(values, profile=profile_to_fold_segments(profile))
    )
    minx, _miny, maxx, _maxy = map(float, render.material.bounds)
    assert maxx - minx == pytest.approx(1596.0)


def test_manufacturing_fails_closed_without_canonical_box_body_profile():
    values = _receiving_values()
    with pytest.raises(ValueError, match="canonical.*Fold Profile|Fold Profile.*required"):
        build_part_render_data(_box_spec(values, profile=()))


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_fresh_main_gui_materializes_canonical_box_body_profile_before_first_calculation():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        profile = app.workspace_controller.box_body_profile()
        assert profile, "fresh GUI must materialize canonical BoxBody profile before first calculation"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_legacy_receiving_project_without_profile_migrates_once_to_controller():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        values = _receiving_values()
        snapshot["model"] = "受電箱"
        settings = dict(snapshot.get("settings") or {})
        for key in ("w", "h", "d", "t", "fw", "zl1", "zl2", "zr2"):
            snapshot[key] = values[key]
            settings[key] = values[key]
        snapshot["settings"] = settings

        snapshot.pop("box_body_profile", None)
        workspace = dict(snapshot.get("workspace") or {})
        workspace.pop("box_body_profile", None)
        snapshot["workspace"] = workspace

        app._apply_phase6_project_snapshot(snapshot)
        first = app.workspace_controller.box_body_profile()
        assert first, "legacy load must migrate missing BoxBody profile once"
        assert [row.get("phase6_key") for row in first] == [
            "zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"
        ]
        assert sum(float(row["len"]) for row in first) == pytest.approx(1596.0)

        # Re-applying the now-canonical snapshot must not rebuild a different profile.
        saved = app._compose_phase6_project_snapshot_from_main_gui()
        app._apply_phase6_project_snapshot(saved)
        second = app.workspace_controller.box_body_profile()
        assert second == first
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_vault_profile_guard_keeps_terminal_zr1():
    values = {
        "model": "金庫型",
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": -15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 2.0,
    }
    profile = build_box_body_profile(values)
    assert profile[-1].get("phase6_key") == "zr1"
    render = build_part_render_data(
        _box_spec(values, profile=profile_to_fold_segments(profile))
    )
    assert not render.material.is_empty
