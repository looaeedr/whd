"""#1959 optional WHD -> CADCraft new-drawing UI adapter (not manufacturing).

Uses frozen WHD finished-face features and official cadcraft-cli.exe; never
opens, overwrites, or imports an existing board/manufacturing DXF. The caller
must run the subprocess off the Tk event thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Sequence

from .cadcraft_paths import cadcraft_binary
from ae_engine import manufacturing_api
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, DrawInstruction,
    from_whd_resolved, run_proof,
)


@dataclass(frozen=True)
class CadcraftCommandDrawingResult:
    output_dxf: Path
    preview_png: Path
    geometry_evidence: dict


def find_cadcraft_cli(*, configured=None) -> str:
    """Find the portable CLI in WHD's application-relative ./cadcraft folder."""
    path = (Path(configured).expanduser() if configured is not None
            else cadcraft_binary("cli"))
    if not path.is_file():
        raise CadcraftCommandProofError(
            f"CADCRAFT_CLI_NOT_FOUND: {path}；"
            "請將 cadcraft-cli 放在 WHD 主程式旁的 cadcraft 資料夾。"
        )
    return str(path)


def open_cadcraft_hole_editor(exchange_dxf: Path, *, executable=None, launcher=None,
                              control_port=None):
    """Launch the real CADCraft GUI with the verified WHD isolated exchange.

    CLI output alone does not open a visible editor. Launch only after the
    caller has established a live WHD Session return ticket; never pass a
    baseline, original manufacturing DXF, or arbitrary user-selected file.
    Keep the GUI process non-blocking so WHD can receive edits later.
    """
    import subprocess
    from .cadcraft_preview_bridge import find_cadcraft_gui

    path = Path(exchange_dxf).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".dxf":
        raise CadcraftCommandProofError("CADCRAFT_EDIT_EXCHANGE_INVALID")
    binary = find_cadcraft_gui(configured=executable)
    spawn = launcher if launcher is not None else subprocess.Popen
    args = [binary]
    if control_port is not None:
        if (isinstance(control_port, bool) or not isinstance(control_port, int)
                or not 1 <= control_port <= 65535):
            raise CadcraftCommandProofError("CADCRAFT_INVALID_CONTROL_PORT")
        args.extend(["--control", str(control_port)])
    args.append(str(path))
    try:
        return spawn(args)
    except OSError as exc:
        raise CadcraftCommandProofError(
            f"CADCRAFT_GUI_LAUNCH_FAILED: {binary} ({exc})"
        ) from exc


def focus_started_cadcraft_window(process_id: int):
    """Best-effort foreground handoff after a real WHD user click on Windows.

    Return False while the native CADCraft top-level window does not exist or
    if the user has switched to another application. Never steal focus from
    Chrome/another foreground process. No external dependency is required.
    """
    import os
    if os.name != "nt" or isinstance(process_id, bool) or not isinstance(process_id, int) or process_id <= 0:
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    pid = wintypes.DWORD()
    get_pid = user32.GetWindowThreadProcessId
    get_pid.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_pid.restype = wintypes.DWORD
    foreground = user32.GetForegroundWindow()
    get_pid(foreground, ctypes.byref(pid))
    if pid.value == process_id:
        return True
    # Foreground may be this WHD process only when launched by actual
    # interaction. An unrelated foreground owner must never be disturbed.
    if pid.value != os.getpid():
        return False

    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL

    def inspect(hwnd, unused):
        owner = wintypes.DWORD()
        get_pid(hwnd, ctypes.byref(owner))
        if owner.value == process_id and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    callback = callback_type(inspect)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(callback, 0)
    if not found:
        return False
    hwnd = found[0]
    user32.IsIconic.argtypes = [wintypes.HWND]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    return user32.GetForegroundWindow() == hwnd


def prepare_whd_cadcraft_commands(*, surface, features: Sequence,
                                   width: float, height: float) -> tuple[DrawInstruction, ...]:
    """Only forward WHD operator input; Engine validates all physical holes."""
    return manufacturing_api.project_whd_cadcraft_command_instructions(
        surface=surface, features=features, width=width, height=height,
    )



def draw_whd_commands_with_cadcraft(
    *, instructions: tuple[DrawInstruction, ...],
    executable: str, output_dir: Path | None = None,
    runner=run_proof,
) -> CadcraftCommandDrawingResult:
    """Run by background GUI worker only; cannot commit holes into WHD."""
    directory = (Path(output_dir) if output_dir is not None else Path(
        tempfile.mkdtemp(prefix="whd-cadcraft-command-1959-")
    ))
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/"whd-command-drawing.dxf"
    preview=directory/"whd-command-drawing.png"
    if target.exists() or preview.exists():
        raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE")
    if not instructions:
        # Engine is the sole owner of metric DXF/blank PNG bytes and refusal.
        # GUI only manages the disposable exchange path and returned ticket.
        evidence = manufacturing_api.save_blank_cadcraft_exchange_drawing(
            target, preview,
        )
        return CadcraftCommandDrawingResult(
            output_dxf=target, preview_png=preview, geometry_evidence=evidence,
        )
    # run_proof refuses existing target/preview, makes a NEW drawing with
    # --metric and independently verifies exact CADCraft output geometry.
    evidence=runner(str(executable),instructions,target,preview)
    if evidence.get("status")!="PASS":
        raise CadcraftCommandProofError("CADCRAFT_GEOMETRY_PROOF_NOT_GREEN")
    if not target.is_file() or not preview.is_file():
        raise CadcraftCommandProofError("CADCRAFT_OUTPUT_NOT_CREATED")
    return CadcraftCommandDrawingResult(
        output_dxf=target,preview_png=preview,geometry_evidence=evidence)
