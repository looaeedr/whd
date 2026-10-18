"""#1959 CADCraft portable ./cadcraft location works without setup.

Tests both the source checkout and packaged app root, with unrelated CWD and
stale environment variables. No external binary is executed here.
"""
from pathlib import Path
import sys

import pytest

from gui_modules.editors import cadcraft_paths
from gui_modules.editors.cadcraft_preview_bridge import (
    CadcraftPreviewError, find_cadcraft_gui,
)
from gui_modules.editors.cadcraft_command_preview_bridge import (
    find_cadcraft_cli,
)
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError


def _build_portable(directory):
    folder = directory / "cadcraft"
    folder.mkdir()
    gui = folder / ("cadcraft.exe" if cadcraft_paths.os.name == "nt" else "cadcraft")
    cli = folder / ("cadcraft-cli.exe" if cadcraft_paths.os.name == "nt"
                    else "cadcraft-cli")
    gui.write_bytes(b"test stub")
    cli.write_bytes(b"test stub")
    return gui, cli


def test_source_root_is_module_relative_not_the_current_working_directory():
    assert cadcraft_paths.whd_application_directory() == (
        Path(cadcraft_paths.__file__).resolve().parents[2]
    )


def test_default_gui_and_cli_use_same_app_relative_portable_folder(tmp_path, monkeypatch):
    app_root = tmp_path / "whd-application"
    app_root.mkdir()
    gui, cli = _build_portable(app_root)
    other = tmp_path / "not-project-root"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setattr(cadcraft_paths, "whd_application_directory", lambda: app_root)
    monkeypatch.setenv("WHD_CADCRAFT_GUI", str(tmp_path / "nonexistent-gui.exe"))
    monkeypatch.setenv("WHD_CADCRAFT_CLI", str(tmp_path / "nonexistent-cli.exe"))
    monkeypatch.setenv("PATH", "")
    assert find_cadcraft_gui() == str(gui)
    assert find_cadcraft_cli() == str(cli)
    assert not (other / "cadcraft").exists()


def test_packaged_whd_exe_uses_sibling_cadcraft_directory(tmp_path, monkeypatch):
    folder = tmp_path / "portable-whd"
    folder.mkdir()
    exe = folder / "WHD.exe"
    exe.write_bytes(b"stub")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    gui, cli = _build_portable(folder)
    assert cadcraft_paths.whd_application_directory() == folder
    assert find_cadcraft_gui() == str(gui)
    assert find_cadcraft_cli() == str(cli)


def test_missing_local_binaries_fail_closed_with_expected_folder(tmp_path, monkeypatch):
    folder = tmp_path / "WHD"
    folder.mkdir()
    monkeypatch.setattr(cadcraft_paths, "whd_application_directory", lambda: folder)
    monkeypatch.setenv("WHD_CADCRAFT_GUI", "ignored-invalid-env")
    monkeypatch.setenv("WHD_CADCRAFT_CLI", "ignored-invalid-env")
    with pytest.raises(CadcraftPreviewError, match=r"cadcraft"):
        find_cadcraft_gui()
    with pytest.raises(CadcraftCommandProofError, match=r"CADCRAFT_CLI_NOT_FOUND"):
        find_cadcraft_cli()
    assert not (folder / "cadcraft").exists()


def test_explicit_executable_paths_remain_supported_for_injected_tests(tmp_path):
    explicit = tmp_path / "custom"
    explicit.mkdir()
    gui = explicit / "my-gui"
    cli = explicit / "my-cli"
    gui.write_bytes(b"stub")
    cli.write_bytes(b"stub")
    assert find_cadcraft_gui(configured=gui) == str(gui)
    assert find_cadcraft_cli(configured=cli) == str(cli)
    with pytest.raises(CadcraftPreviewError):
        find_cadcraft_gui(configured=explicit / "absent")
    with pytest.raises(CadcraftCommandProofError):
        find_cadcraft_cli(configured=explicit / "absent")


def test_only_known_binary_roles_are_accepted():
    with pytest.raises(ValueError, match="Unsupported CADCraft binary kind"):
        cadcraft_paths.cadcraft_binary("manufacturing")
