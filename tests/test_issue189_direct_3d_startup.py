import inspect

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
