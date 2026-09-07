from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)


def _make_snapshot(*, top_level_fw=None, nested_fw=24.0):
    snapshot = {
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": float(nested_fw)},
    }
    if top_level_fw is not None:
        snapshot["t"] = 2.0
        snapshot["fw"] = float(top_level_fw)
    return snapshot


def test_nested_settings_are_effective_before_first_box_body_profile_build():
    import tkinter as tk

    from fold_designer_bridge import Phase6FoldDesignerApp
    from phase6_fold_profiles import read_box_body_profile

    root = tk.Tk()
    app = None
    try:
        app = Phase6FoldDesignerApp(root, _make_snapshot())
        values = read_box_body_profile(
            app.state.profiles_vault["箱身"], app._phase6_input_snapshot
        )
        assert values["fw"] == pytest.approx(24.0)

        # Exact Combined-Acceptance lifecycle: assembly backing box_body -> single box_body.
        app.activate_part("box_body")
        root.update_idletasks()
        assert app._settings_values["fw"] == pytest.approx(24.0)
        assert app._phase6_input_snapshot["fw"] == pytest.approx(24.0)
    finally:
        try:
            if app is not None:
                app.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


def test_explicit_top_level_fw_wins_over_older_nested_settings():
    import tkinter as tk

    from fold_designer_bridge import Phase6FoldDesignerApp
    from phase6_fold_profiles import read_box_body_profile

    root = tk.Tk()
    app = None
    try:
        app = Phase6FoldDesignerApp(
            root, _make_snapshot(top_level_fw=25.0, nested_fw=24.0)
        )
        values = read_box_body_profile(
            app.state.profiles_vault["箱身"], app._phase6_input_snapshot
        )
        assert values["fw"] == pytest.approx(25.0)

        app.activate_part("box_body")
        root.update_idletasks()
        assert app._settings_values["fw"] == pytest.approx(25.0)
        assert app._phase6_input_snapshot["fw"] == pytest.approx(25.0)
    finally:
        try:
            if app is not None:
                app.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
