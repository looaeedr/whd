"""#1959 optional WHD -> CADCraft new-drawing UI adapter (not manufacturing).

Uses frozen WHD finished-face features and official cadcraft-cli.exe; never
opens, overwrites, or imports an existing board/manufacturing DXF. The caller
must run the subprocess off the Tk event thread.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Sequence

from ae_engine.sheetmetal_features import resolve_surface_features
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
    """Find an installed CLI only when explicitly invoked. No downloads."""
    explicit = configured if configured is not None else os.environ.get("WHD_CADCRAFT_CLI")
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise CadcraftCommandProofError(f"CADCRAFT_CLI_NOT_FOUND: {path}")
        return str(path)

    # Portable Windows CADCraft bundles cadcraft-cli.exe near its GUI.
    gui = os.environ.get("WHD_CADCRAFT_GUI")
    if gui:
        sibling = Path(gui).expanduser().parent / (
            "cadcraft-cli.exe" if os.name == "nt" else "cadcraft-cli"
        )
        if sibling.is_file():
            return str(sibling)

    for name in ("cadcraft-cli", "cadcraft-cli.exe"):
        located = shutil.which(name)
        if located and Path(located).is_file():
            return located
    raise CadcraftCommandProofError(
        "CADCRAFT_CLI_NOT_FOUND: 請指定 WHD_CADCRAFT_CLI 的 cadcraft-cli.exe 完整路徑"
    )


def prepare_whd_cadcraft_commands(*, surface, features: Sequence,
                                   width: float, height: float) -> tuple[DrawInstruction, ...]:
    """Read-only WHD authority check; captures immutable geometry for worker."""
    w,h=float(width),float(height)
    if not all(math.isfinite(v) and v>0 for v in (w,h)):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    originals=tuple(features)
    if not originals or len(originals)>100:
        raise CadcraftCommandProofError("INVALID_WHD_CUTTING_FEATURE_COUNT")
    if any(getattr(f, "layer", None)!="CUTTING" for f in originals):
        raise CadcraftCommandProofError("CADCRAFT_TRIAL_SUPPORTS_CUTTING_HOLES_ONLY")
    try:
        resolved=tuple(resolve_surface_features(surface,originals,w,h))
    except (ValueError,TypeError,AttributeError) as exc:
        raise CadcraftCommandProofError("WHD_FEATURE_SURFACE_REJECTED") from exc
    return from_whd_resolved(resolved)


def draw_whd_commands_with_cadcraft(
    *, instructions: tuple[DrawInstruction, ...],
    executable: str, output_dir: Path | None = None,
    runner=run_proof,
) -> CadcraftCommandDrawingResult:
    """Run by background GUI worker only; cannot commit holes into WHD."""
    if not instructions:
        raise CadcraftCommandProofError("NO_WHD_COMMANDS")
    directory = (Path(output_dir) if output_dir is not None else Path(
        tempfile.mkdtemp(prefix="whd-cadcraft-command-1959-")
    ))
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/"whd-command-drawing.dxf"
    preview=directory/"whd-command-drawing.png"
    # run_proof refuses existing target/preview, makes a NEW drawing with
    # --metric and independently verifies exact CADCraft output geometry.
    evidence=runner(str(executable),instructions,target,preview)
    if evidence.get("status")!="PASS":
        raise CadcraftCommandProofError("CADCRAFT_GEOMETRY_PROOF_NOT_GREEN")
    return CadcraftCommandDrawingResult(
        output_dxf=target,preview_png=preview,geometry_evidence=evidence)
