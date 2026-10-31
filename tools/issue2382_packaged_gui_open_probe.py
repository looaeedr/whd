# -*- coding: utf-8 -*-
"""#2382: real packaged WHD.exe .p6fold open/error discrimination on Windows.

This probes the released-style windowed EXE, not an imported gui.main or a
source-only Tk test. Both candidates are in an isolated temporary directory.
A corrupt existing project is the negative control: the packaged app must
show the real "專案開啟失敗" dialog rather than silently ignoring argv.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_real_gui_project(path: Path) -> dict:
    import tkinter as tk
    import gui
    from phase6_project_file import read_project

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.project_controller.set_project_path(path)
        saved = app.save_phase6_project(_active_part_hint="box_body")
        if saved != str(path) or not path.is_file():
            raise AssertionError("W07_SOURCE_GUI_SAVE_FAILED")
        payload = read_project(path)
        snapshot = payload["snapshot"]
        if not snapshot.get("model") or "workspace" not in snapshot:
            raise AssertionError("W07_SAVED_PROJECT_AUTHORITY_MISSING")
        return {"model": snapshot["model"], "sha256": _sha(path),
                "schema": payload["schema"]}
    finally:
        try:
            window = app.fold_designer_window
            if window is not None and window.winfo_exists():
                window.destroy()
        finally:
            root.destroy()


def _visible_process_windows(pid: int) -> list[dict]:
    if os.name != "nt":
        raise RuntimeError("W07_WINDOWS_REQUIRED")
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    windows = []

    @cb_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value:
                windows.append({"handle": int(hwnd), "title": title.value})
        return True

    if not user32.EnumWindows(visit, 0):
        raise OSError("W07_ENUM_WINDOWS_FAILED")
    return windows


def _observe(exe: Path, project: Path, *, expect_error: bool,
             deadline_seconds: float = 35) -> dict:
    before = _sha(project)
    process = subprocess.Popen([str(exe), str(project)], cwd=str(exe.parent))
    t0 = time.monotonic()
    seen_main = False
    seen_error = False
    last_titles = []
    try:
        while time.monotonic() - t0 < deadline_seconds:
            if process.poll() is not None:
                raise AssertionError(
                    f"W07_PACKAGED_GUI_EARLY_EXIT rc={process.returncode} "
                    f"error_case={expect_error} titles={last_titles!r}")
            rows = _visible_process_windows(process.pid)
            titles = [row["title"] for row in rows]
            last_titles = titles
            if any("Box Unfolding Calculator" in title for title in titles):
                seen_main = True
            if any("專案開啟失敗" in title for title in titles):
                seen_error = True
            if expect_error and seen_error and seen_main:
                break
            # Loading runs after_idle, not at root creation. Continue observing
            # for 12 seconds so a delayed failure cannot count as valid open.
            if not expect_error and seen_main and time.monotonic() - t0 >= 12:
                break
            time.sleep(0.25)
        if not seen_main:
            raise AssertionError(
                f"W07_PACKAGED_GUI_WINDOW_MISSING error_case={expect_error} "
                f"titles={last_titles!r}")
        if seen_error != expect_error:
            raise AssertionError(
                f"W07_PACKAGED_PROJECT_OPEN_WRONG_RESULT error_case={expect_error} "
                f"error_dialog={seen_error} titles={last_titles!r}")
        if before != _sha(project):
            raise AssertionError("W07_PACKAGED_GUI_MODIFIED_SOURCE_PROJECT")
        return {"error_case": expect_error, "visible_main": seen_main,
                "error_dialog": seen_error, "titles": last_titles,
                "project_sha256": before,
                "observation_seconds": round(time.monotonic() - t0, 3)}
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=6)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("W07_REQUIRES_ACTUAL_WINDOWS_EXE")
    exe = args.exe.resolve(strict=True)
    if exe.name.lower() != "whd.exe":
        raise RuntimeError("W07_EXPECTED_PACKAGED_WHD_EXE")
    folder = args.out.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    valid = folder / "已儲存 專案.p6fold"
    invalid = folder / "損壞 專案.p6fold"
    source = _make_real_gui_project(valid)
    invalid.write_text("{ invalid project JSON", encoding="utf-8")
    valid_result = _observe(exe, valid, expect_error=False)
    invalid_result = _observe(exe, invalid, expect_error=True)
    result = {
        "kind": "W07_PACKAGED_WHD_GUI_PROJECT_OPEN_NEGATIVE_CONTROL",
        "source": source,
        "valid": valid_result,
        "invalid": invalid_result,
        "gui_exe_sha256": _sha(exe),
        "note": "Real packaged window process and Tk native error dialog; "
                "not automated mouse editing or local workstation UAT.",
    }
    (folder / "packaged-gui-open.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("W07_PACKAGED_GUI_POSITIVE_AND_NEGATIVE_PROJECT_OPEN_PASS "
          + result["gui_exe_sha256"], flush=True)


if __name__ == "__main__":
    main()
