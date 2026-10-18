"""#1959 optional WHD -> CADCraft new-drawing UI adapter (not manufacturing).

Uses frozen WHD finished-face features and official cadcraft-cli.exe; never
opens, overwrites, or imports an existing board/manufacturing DXF. The caller
must run the subprocess off the Tk event thread.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tempfile
from typing import Sequence

from .cadcraft_paths import cadcraft_binary
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
    """Find the portable CLI in WHD's application-relative ./cadcraft folder."""
    path = (Path(configured).expanduser() if configured is not None
            else cadcraft_binary("cli"))
    if not path.is_file():
        raise CadcraftCommandProofError(
            f"CADCRAFT_CLI_NOT_FOUND: {path}；"
            "請將 cadcraft-cli 放在 WHD 主程式旁的 cadcraft 資料夾。"
        )
    return str(path)


def prepare_whd_cadcraft_commands(*, surface, features: Sequence,
                                   width: float, height: float) -> tuple[DrawInstruction, ...]:
    """Read-only WHD authority check; captures immutable geometry for worker."""
    w,h=float(width),float(height)
    if not all(math.isfinite(v) and v>0 for v in (w,h)):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    originals=tuple(features)
    if len(originals)>100:
        raise CadcraftCommandProofError("INVALID_WHD_CUTTING_FEATURE_COUNT")
    if any(getattr(f, "layer", None)!="CUTTING" for f in originals):
        raise CadcraftCommandProofError("CADCRAFT_TRIAL_SUPPORTS_CUTTING_HOLES_ONLY")
    try:
        resolved=tuple(resolve_surface_features(surface,originals,w,h))
    except (ValueError,TypeError,AttributeError) as exc:
        raise CadcraftCommandProofError("WHD_FEATURE_SURFACE_REJECTED") from exc
    # Empty original faces are allowed: WHD emits a fresh blank metric exchange
    # that CADCraft can open to draw the *first* hole. No manufacturing is made.
    return from_whd_resolved(resolved) if resolved else ()


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
        # CADCraft cannot draw a first hole from nonexistent prior geometry.
        # WHD creates a disposable empty DXF in mm; CADCraft is then its editor,
        # never the production drawing author. Both files are new and isolated.
        import ezdxf
        import struct
        import zlib
        blank = ezdxf.new("R2010", units=ezdxf.units.MM)
        blank.saveas(target)
        # Small valid blank PNG, constructed from the Python stdlib; no Pillow
        # or native CADCraft process required to author the initial empty page.
        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
        w, h = 320, 200
        pixels = (bytes([0]) + bytes([255, 255, 255]) * w) * h
        preview.write_bytes(
            bytes([137, 80, 78, 71, 13, 10, 26, 10])
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels))
            + chunk(b"IEND", b"")
        )
        return CadcraftCommandDrawingResult(
            output_dxf=target, preview_png=preview,
            geometry_evidence={"status": "PASS", "scope": "EMPTY_WHD_ISSUED_EXCHANGE"},
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
