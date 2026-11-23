"""#3415 isolated real-Windows Tcl/Tk startup A/B only; never production.

Tests run on GitHub Windows runner with the unmodified #1959 CADCraft native
GUI/Confirm/Cancel/Undo test. Neither Tcl library environment nor installed
files are modified. All evidence is printed before and after Tk creation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import tkinter as tk

import pytest


def _candidate_scripts(extra=()):
    locations = set()
    for env_name in ("TCL_LIBRARY", "TK_LIBRARY"):
        value = os.environ.get(env_name)
        if value:
            base = Path(value)
            locations.add(base / ("init.tcl" if env_name == "TCL_LIBRARY" else "tk.tcl"))
            locations.add(base)
    bases = {
        Path(sys.executable).resolve().parent,
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(sys.exec_prefix),
        Path(sys.base_exec_prefix),
        Path(tk.__file__).resolve().parent.parent,
    }
    for base in bases:
        for sub in ("tcl", "Tcl", "lib", "Lib"):
            folder = base / sub
            for pattern in ("tcl*/init.tcl", "tk*/tk.tcl"):
                locations.update(folder.glob(pattern))
            locations.update((
                folder / "tcl8.6" / "init.tcl",
                folder / "tk8.6" / "tk.tcl",
            ))
    for path in extra:
        if path:
            p = Path(path)
            if p.suffix.lower() == ".tcl":
                locations.add(p)
            else:
                locations.update((p / "init.tcl", p / "tk.tcl"))
    return sorted(locations, key=lambda p: str(p).casefold())


def _file_audit(path: Path):
    info = {"path": str(path)}
    try:
        # Open and hash the actual bytes, not just stat/existence. Catch cases
        # where the file exists but cannot be read at Tk startup time.
        with path.open("rb") as inp:
            content = inp.read()
        info.update(read_ok=True, bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest())
    except OSError as exc:
        info.update(read_ok=False, error=f"{type(exc).__name__}: {exc}")
    return info


def _live_tcl_paths(root):
    seen = {}
    for label, query in (
        ("info_library", ("info", "library")),
        ("auto_path", ("set", "auto_path")),
        ("tcl_library", ("set", "tcl_library")),
        ("tk_library", ("set", "tk_library")),
        ("tcl_patchlevel", ("info", "patchlevel")),
        ("tk_patchlevel", ("package", "provide", "Tk")),
    ):
        try:
            value = root.tk.call(*query)
            if isinstance(value, (tuple, list)):
                value = [str(x) for x in value]
            seen[label] = str(value) if not isinstance(value, list) else value
        except Exception as exc:
            seen[label] = {"error": f"{type(exc).__name__}: {exc}"}
    paths = []
    for name in ("info_library", "tcl_library", "tk_library"):
        value = seen.get(name)
        if isinstance(value, str):
            paths.append(value)
    return seen, paths


def _checkpoint(label, extra=()):
    result = {
        "stage": label,
        "pid": os.getpid(),
        "thread": threading.get_ident(),
        "executable": sys.executable,
        "version": sys.version,
        "sys_prefix": sys.prefix,
        "sys_base_prefix": sys.base_prefix,
        "tkinter_module": tk.__file__,
        "tcl_version": tk.TclVersion,
        "tk_version": tk.TkVersion,
        "environment": {key: os.environ.get(key)
                        for key in ("TCL_LIBRARY", "TK_LIBRARY",
                                    "PYTHONHOME", "PYTHONPATH")},
        "direct_read": [_file_audit(p) for p in _candidate_scripts(extra)],
    }
    print("WHD_3415_TK_INIT_AUDIT " + json.dumps(
        result, ensure_ascii=True, sort_keys=True, default=str
    ), flush=True)


def _record_live(label, root):
    actual, paths = _live_tcl_paths(root)
    print("WHD_3415_TK_ACTUAL_PATHS " + json.dumps({
        "stage": label, "pid": os.getpid(), "actual": actual,
        "resolved_file_read": [_file_audit(p) for p in _candidate_scripts(paths)],
    }, ensure_ascii=True, sort_keys=True, default=str), flush=True)


def test_sequential_tk_roots_in_one_python_process():
    """Control: Tk()→destroy()→Tk() with NO WHD/editor/CADCraft/worker."""
    for number in (1, 2):
        root = None
        _checkpoint(f"control_before_root_{number}")
        try:
            root = tk.Tk()
            root.update_idletasks()
            _record_live(f"control_root_{number}_created", root)
        finally:
            if root is not None:
                root.destroy()
            _checkpoint(f"control_after_root_{number}")


@pytest.mark.parametrize("confirmed", (True, False), ids=("confirm", "cancel"))
def test_original_native_button_same_process(monkeypatch, confirmed):
    """Use ORIGINAL native Windows E2E, with only read-only path observation.

    Both param cases in a single pytest command share the Python interpreter.
    The standard pytest fixture reverts its own GUI/CLI test monkeypatches.
    """
    from test_issue1959_native_windows_whd_button_e2e import (
        test_whd_real_tk_button_opens_real_native_cadcraft_and_returns_unsaved_hole
        as original_test,
    )
    import test_issue1959_native_windows_whd_button_e2e as native_module

    kind = "confirm" if confirmed else "cancel"
    old_shell = native_module._tk_shell
    def traced_shell(*args, **kwargs):
        _checkpoint(f"{kind}_immediately_before_original_tk_shell")
        result = old_shell(*args, **kwargs)
        _record_live(f"{kind}_original_shell_ready", result[0])
        return result

    _checkpoint(f"{kind}_before_original_test")
    try:
        with monkeypatch.context() as isolated:
            isolated.setattr(native_module, "_tk_shell", traced_shell)
            original_test(isolated, confirmed)
        print("WHD_3415_TK_NATIVE_FULL_E2E_PASS " + kind, flush=True)
    finally:
        _checkpoint(f"{kind}_after_original_test")
