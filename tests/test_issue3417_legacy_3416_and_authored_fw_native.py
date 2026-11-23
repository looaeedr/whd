"""#3417 cross-SHA real Tk old-file and authored-EndCap-Fold source regression.

No fixture is fabricated: the baseline .p6fold is written by an isolated
actual #3416 localX@eacc790 Tk Python process using its real Save button,
then opened with the *current* candidate's actual GUI View button.
CI Product Regression preflight checks out full Git history (fetch-depth=0);
the exact base commit is an existing ancestor, no network fetch needed.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.endcap_live_v_check_consumer import ATTR, KEY, _selected_source
from gui_modules.application.endcap_live_v_check_view import close_saved_live_check_window
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project

ORIGINAL_3416_LOCALX = "eacc79022b7404c29f9f4eb0c904d58956b2e452"
_REPO = Path(__file__).resolve().parents[1]


def _select_head(app):
    app.workspace_controller.set_active_part("head")
    app.manual_corner_pair_same["head"]["bottom"] = False
    app.manual_active_corner_var.set("bottom_left")
    app.v_miter_gui_check_corners = {"head": {"bottom_left": "V_MITER_CHECK"}}
    app.v_miter_gui_first_bend_axes = {"head": {"bottom_left": "x"}}
    app.v_miter_gui_relief_modes = {"head": {"bottom_left": "ROUND_R"}}
    app.v_miter_relief_mode_var.set("ROUND_R")


def _new_gui():
    from gui import BoxCalculatorGUI

    root = tk.Tk()
    root.withdraw()
    return root, BoxCalculatorGUI(root)


def _old_3416_native_writer(path: Path, tmp_path: Path):
    # A real #3416 *separate* Tk process, not copied digest or mocked
    # PartSpec. Leave no worktree behind, even if the old writer fails.
    original = tmp_path / "original-3416-src"
    subprocess.run(
        ["git", "-C", str(_REPO), "cat-file", "-e", f"{ORIGINAL_3416_LOCALX}^{{commit}}"],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(_REPO), "worktree", "add", "--detach",
         str(original), ORIGINAL_3416_LOCALX],
        check=True, capture_output=True, text=True,
    )
    script = """
import sys
import tkinter as tk
from tkinter import messagebox
from gui import BoxCalculatorGUI
from gui_modules.application.endcap_live_v_check_consumer import ATTR, KEY
from phase6_project_file import PROJECT_SCHEMA_V1, write_project
messagebox.showinfo = lambda *args, **kw: None
messagebox.showerror = lambda *args, **kw: (_ for _ in ()).throw(
    AssertionError("ORIGINAL_3416_BUTTON_ERROR:" + repr(args))
)
root = tk.Tk()
root.withdraw()
try:
    app = BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part("head")
    app.manual_corner_pair_same["head"]["bottom"] = False
    app.manual_active_corner_var.set("bottom_left")
    app.v_miter_gui_check_corners = {"head": {"bottom_left": "V_MITER_CHECK"}}
    app.v_miter_gui_first_bend_axes = {"head": {"bottom_left": "x"}}
    app.v_miter_gui_relief_modes = {"head": {"bottom_left": "ROUND_R"}}
    app.v_miter_relief_mode_var.set("ROUND_R")
    app.v_miter_capture_live_source_button.invoke()
    record = getattr(app, ATTR)["head"]["bottom_left"]
    saved = app._compose_phase6_project_snapshot_from_main_gui()
    assert saved[KEY]["head"]["bottom_left"] == record
    assert not saved.get("part_features", {}).get("head")
    write_project(sys.argv[1], {"schema": PROJECT_SCHEMA_V1, "snapshot": saved})
    print("EXACT_3416_TK_WRITER_OK " + record["source_fold_sha256"])
finally:
    root.destroy()
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(path)], cwd=original,
            env={**os.environ, "PYTHONPATH": str(original)},
            check=True, capture_output=True, text=True, timeout=120,
        )
        assert "EXACT_3416_TK_WRITER_OK " in result.stdout, (
            result.stdout, result.stderr
        )
        assert path.is_file()
    finally:
        subprocess.run(
            ["git", "-C", str(_REPO), "worktree", "remove", "--force", str(original)],
            check=True, capture_output=True, text=True,
        )


def test_original_3416_native_saved_nohole_opens_without_drift_but_w_change_rejects(
    tmp_path, monkeypatch,
):
    from tkinter import messagebox
    original_file = tmp_path / "unchanged-native-3416.p6fold"
    _old_3416_native_writer(original_file, tmp_path)
    original_bytes = original_file.read_bytes()
    source = read_project(original_file)["snapshot"]
    old_digest = source[KEY]["head"]["bottom_left"]["source_fold_sha256"]
    assert not source.get("part_features", {}).get("head")
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args: errors.append(args))
    monkeypatch.setattr(messagebox, "showinfo", lambda *args: None)
    root, app = _new_gui()
    try:
        app._apply_phase6_project_snapshot(source)
        _select_head(app)
        native = app._make_original_fold_designer_snapshot()
        _, _, spec, render = _selected_source(app, native)
        assert spec.fold_profile_x and spec.fold_profile_y  # Main Tk Open links Fold
        assert not spec.holes
        errors.clear()
        app.v_miter_check_source_button.invoke()
        assert not errors, errors
        win = app._endcap_live_saved_check_window
        win.update()
        assert win.winfo_viewable() == 1 and win.grab_status() == "local"
        assert win._saved_endcap_check_replay.factory_true_t_check is not None
        assert getattr(app, ATTR)["head"]["bottom_left"]["source_fold_sha256"] == old_digest
        close_saved_live_check_window(app)
        app.w_var.set(str(float(app.w_var.get()) + 10))
        errors.clear()
        app.v_miter_check_source_button.invoke()
        assert errors and "V_MITER_LIVE_SOURCE_CHANGED" in errors[-1][1]
        assert getattr(app, "_endcap_live_saved_check_window", None) is None
        assert original_file.read_bytes() == original_bytes
    finally:
        close_saved_live_check_window(app)
        root.destroy()


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_native_authored_lower_fw_minus_75_5_invalidates_old_saved_digest(
    tmp_path, monkeypatch, mode,
):
    from tkinter import messagebox
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args: errors.append(args))
    monkeypatch.setattr(messagebox, "showinfo", lambda *args: None)
    root, app = _new_gui()
    fresh_root = None
    try:
        app.baseline_var.set("自訂")
        app.w_var.set("400")
        app.d_var.set("250")
        app.t_var.set("2")
        _select_head(app)
        app.v_miter_relief_mode_var.set(mode)
        app.v_miter_capture_live_source_button.invoke()
        assert not errors, errors
        original = deepcopy(getattr(app, ATTR)["head"]["bottom_left"])
        source = app._compose_phase6_project_snapshot_from_main_gui()
        project = tmp_path / "authored-fw-angle.p6fold"
        write_project(project, {"schema": PROJECT_SCHEMA_V1, "snapshot": source})
        saved = read_project(project)["snapshot"]

        fresh_root, fresh = _new_gui()
        fresh._apply_phase6_project_snapshot(saved)
        _select_head(fresh)
        fresh_snapshot = fresh._make_original_fold_designer_snapshot()
        _, _, before, original_render = _selected_source(fresh, fresh_snapshot)
        assert before.model_name is None
        # Normal saved source plays normally before the genuine operator edit.
        errors.clear()
        fresh.v_miter_check_source_button.invoke()
        assert not errors, errors
        close_saved_live_check_window(fresh)
        profiles = fresh.workspace_controller.part_profiles_snapshot()
        authored = deepcopy(profiles["head"])
        lower = [seg for seg in authored["Y"] if seg.get("phase6_key") == "fw"]
        assert len(lower) == 1
        assert lower[0]["angle"] == pytest.approx(-90)
        lower[0]["angle"] = -75.5
        profiles["head"] = authored
        fresh.workspace_controller.replace_part_profiles(profiles)
        changed_snapshot = fresh._make_original_fold_designer_snapshot()
        _, _, after, changed_render = _selected_source(fresh, changed_snapshot)
        actual = [seg for seg in after.fold_profile_y if seg.phase6_key == "fw"]
        assert len(actual) == 1 and actual[0].angle == pytest.approx(-75.5)
        assert changed_render.scene is not None
        assert after.fold_profile_y != before.fold_profile_y
        # The saved digest is bound to the original signed Fold even if the
        # physically drawn 2D BEND segment stayed at the same location.
        errors.clear()
        fresh.v_miter_check_source_button.invoke()
        assert errors and "V_MITER_LIVE_SOURCE_CHANGED" in errors[-1][1]
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert getattr(fresh, ATTR)["head"]["bottom_left"] == original
        # Fresh capture of the actually authored -75.5 Fold is accepted,
        # not silently flattened back to linked default -90.
        errors.clear()
        fresh.v_miter_relief_mode_var.set(mode)
        fresh.v_miter_capture_live_source_button.invoke()
        assert not errors, errors
        fresh_record = getattr(fresh, ATTR)["head"]["bottom_left"]
        assert fresh_record["source_fold_sha256"] != original["source_fold_sha256"]
        assert fresh_record["first_bend_axis"] == "x"
        assert fresh_record["relief_mode"] == mode
    finally:
        if fresh_root is not None:
            fresh_root.destroy()
        root.destroy()
