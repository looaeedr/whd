import inspect
import tkinter as tk

import gui


def test_issue189_main_does_not_instantiate_legacy_box_calculator_gui():
    """The production entrypoint must boot the 3D primary workspace directly."""
    source = inspect.getsource(gui.main)
    assert "BoxCalculatorGUI(" not in source


def test_issue189_main_does_not_fake_remove_legacy_shell_with_withdraw():
    """T4 removes the legacy shell; hiding a legacy root is not acceptance."""
    source = inspect.getsource(gui.main)
    assert ".withdraw(" not in source
    assert "withdraw()" not in source


def test_issue189_file_association_remains_non_fatal_startup_convenience():
    """Direct-3D startup must preserve the existing non-fatal association boundary."""
    source = inspect.getsource(gui.main)
    assert "register_windows_file_association(" in source
    assert "except Exception" in source


def test_issue189_command_line_project_path_is_still_resolved_at_startup():
    """The .p6fold argv seam survives the shell retirement."""
    source = inspect.getsource(gui.main)
    assert "project_path_from_argv(argv)" in source


def test_issue189_primary_application_is_not_legacy_box_calculator_type():
    assert not issubclass(gui.Phase6PrimaryApplication, gui.BoxCalculatorGUI)


def test_issue189_primary_application_does_not_borrow_legacy_controller_lifecycle():
    """The direct 3D application must own its lifecycle instead of proxying BoxCalculatorGUI."""
    source = inspect.getsource(gui.Phase6PrimaryApplication)
    assert "BoxCalculatorGUI.__init__" not in source
    assert "vars(BoxCalculatorGUI)" not in source
    assert "def __getattr__" not in source


def test_issue189_real_tk_mounts_3d_designer_directly_on_single_root():
    root = tk.Tk()
    app = None
    try:
        app = gui.Phase6PrimaryApplication(root)
        root.update_idletasks()

        assert not isinstance(app, gui.BoxCalculatorGUI)
        assert app.fold_designer_window is root
        assert isinstance(app.fold_designer_app, gui.Phase6FoldDesignerApp)
        assert getattr(app, "_legacy_2d_compat_host", "missing") is None

        legacy_toplevels = [
            child for child in root.winfo_children() if isinstance(child, tk.Toplevel)
        ]
        assert legacy_toplevels == []
    finally:
        try:
            if app is not None and getattr(app, "fold_designer_app", None) is not None:
                app.fold_designer_app.flush_pending_settings()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
