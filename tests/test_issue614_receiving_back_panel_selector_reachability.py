from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="#614 exact selector reachability requires real Tk/Xvfb",
)


def _pump(root, cycles=6):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _invoke_menu_label(menu, label: str):
    end = menu.index("end")
    assert end is not None
    for index in range(int(end) + 1):
        try:
            if str(menu.entrycget(index, "label")) == label:
                menu.invoke(index)
                return
        except Exception:
            continue
    raise AssertionError(f"visible part menu does not contain {label!r}")


def _open_receiving_box_body():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    assert designer is not None
    try:
        designer.root.deiconify()
        designer.root.geometry("1400x900+0+0")
    except Exception:
        pass
    _pump(root)

    designer.baseline_model_var.set("受電箱")
    _pump(root, 8)

    # Exact operator path: use the visible top-level part menu.  Do not call
    # activate_part("box_body:back") and do not use the hidden Structure Tree.
    _invoke_menu_label(designer.part_choice_menu, "箱身")
    _pump(root, 6)

    assert designer.part_var.get() == "箱身"
    assert designer.designer_workspace.active_part == "box_body"
    assert designer._phase6_3d_display_mode == "single"
    return tk, root, designer


def _close(tk, root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_receiving_box_body_directly_exposes_back_panel_mode_without_parameter_unlock():
    tk, root, designer = _open_receiving_box_body()
    try:
        # 後面板形式 is a normal Receiving product choice.  The operator must not
        # need parameter unlock or a hidden physical-child activation to reach it.
        assert not bool(getattr(designer, "_phase6_parameters_unlocked", False))
        assert not bool(designer.settings_center.winfo_ismapped())

        selector = designer.back_panel_mode_selector
        control = designer.back_panel_mode_control
        assert bool(control.winfo_ismapped()), (
            "受電箱 → 箱身 must directly expose 後面板形式; "
            "current UI hides it unless box_body:back is activated internally"
        )
        assert bool(selector.winfo_ismapped())
        assert tuple(selector.cget("values")) == ("全板", "半截", "背開孔")
        assert str(selector.cget("state")) == "readonly"
        assert designer.back_panel_mode_var.get() == "全板"

        parent = control
        inside_normal_input = False
        while parent is not None:
            if parent is designer.input_content_host:
                inside_normal_input = True
                break
            parent = getattr(parent, "master", None)
        assert inside_normal_input
    finally:
        _close(tk, root, designer)


def test_receiving_direct_selector_commits_existing_back_opening_contract():
    tk, root, designer = _open_receiving_box_body()
    try:
        from phase6_box_body_structure import BackPanelMode, back_panel_mode

        selector = designer.back_panel_mode_selector
        assert bool(selector.winfo_ismapped())

        selector.current(2)
        selector.event_generate("<<ComboboxSelected>>")
        _pump(root, 8)

        assert back_panel_mode(
            designer.designer_workspace.box_body_structure_state()
        ) is BackPanelMode.BACK_OPENING

        # This GUI regression test owns only the operator path and canonical
        # state commit.  BACK_OPENING manufacturing/DXF geometry is already
        # certified by the focused #510 tests and is run beside this test in CI.
    finally:
        _close(tk, root, designer)
