"""Opt-in, read-only CADCraft preview of the existing Hole Editor.

The WHD 2D editor/session and its manufacturing/DXF authority remain unchanged.
CADCraft receives only a disposable CHECK-layer inspection copy; drawings
edited in CADCraft are NEVER imported, committed, or written to baseline files.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from .cadcraft_paths import cadcraft_binary
from ae_engine import manufacturing_api
from ae_engine.operator_cadcraft_preview import CadcraftPreviewError


def find_cadcraft_gui(*, configured=None):
    """Prefer WHD's local ./cadcraft portable directory, not PATH or env."""
    path = (Path(configured).expanduser() if configured is not None
            else cadcraft_binary("gui"))
    if not path.is_file():
        raise CadcraftPreviewError(
            f"找不到 CADCraft 程式：{path}。"
            "請將 CADCraft 免安裝版放在 WHD 主程式旁的 cadcraft 資料夾。"
        )
    return str(path)


def build_hole_editor_cadcraft_scene(*, surface, features, width, height, baseline_scene=None):
    """Only pass operator context; Engine owns CHECK preview geometry."""
    return manufacturing_api.project_cadcraft_check_scene(
        surface=surface, features=features, width=width, height=height,
        baseline_scene=baseline_scene,
    )


def save_cadcraft_preview_dxf(path, scene):
    """Disposable CHECK-only external viewer serialization belongs to Engine."""
    return manufacturing_api.save_cadcraft_check_scene_dxf(path, scene)


def open_hole_editor_cadcraft_preview(
    *, surface, features, width, height, baseline_scene=None,
    executable=None, output_dir=None, launcher=None,
):
    """Start CADCraft only on explicit button click; do not block Tk.

    The disposable .dxf remains in the OS temp directory so the external app
    can read it after this call returns. No CADCraft output is read back.
    """
    binary = find_cadcraft_gui(configured=executable)
    scene = build_hole_editor_cadcraft_scene(
        surface=surface, features=features, width=width, height=height,
        baseline_scene=baseline_scene,
    )
    directory = Path(output_dir) if output_dir is not None else Path(
        tempfile.mkdtemp(prefix="whd-cadcraft-preview-")
    )
    directory.mkdir(parents=True, exist_ok=True)
    # mkstemp guarantees one unique, non-canonical path even across editors.
    fd, filename = tempfile.mkstemp(prefix="whd-inspection-", suffix=".dxf", dir=directory)
    os.close(fd)
    target = Path(filename)
    try:
        save_cadcraft_preview_dxf(target, scene)
        spawn = launcher if launcher is not None else subprocess.Popen
        spawn([binary, str(target)])  # argv only: never shell=True
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "CadcraftPreviewError", "find_cadcraft_gui",
    "build_hole_editor_cadcraft_scene", "save_cadcraft_preview_dxf",
    "open_hole_editor_cadcraft_preview",
]
