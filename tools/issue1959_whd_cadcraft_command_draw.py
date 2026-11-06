"""#1959: WHD resolved holes -> new CADCraft drawing, isolated roundtrip proof only.

No existing DXF is opened; no WHD holes, sessions, CSV, or manufacturing
files are modified. CADCraft is a renderer and disposable geometry witness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedProfile, ResolvedRect


from ae_engine.cadcraft_exchange_proof import (
    CadcraftCommandProofError, DrawInstruction, MAX_ENTITY_COUNT,
    MAX_COORD, TOLERANCE_MM, _number, _point, _ring, _near,
    from_whd_resolved, verify_dxf,
)

def cadcraft_argv(cli: str, instructions: tuple[DrawInstruction, ...],
                  output: Path, preview: Path | None = None) -> list[str]:
    if not cli or not instructions or len(instructions) > MAX_ENTITY_COUNT:
        raise CadcraftCommandProofError("INVALID_COMMAND_REQUEST")
    args = [str(cli), "run", "--metric"]
    for item in instructions:
        if item.kind == "circle":
            command = "circle"
            payload = {"center": list(item.points[0]), "radius": item.radius}
        elif item.kind in ("rectangle", "profile"):
            command = "pline"
            payload = {"vertices": [list(p) for p in item.points], "closed": True}
        else:
            raise CadcraftCommandProofError("UNKNOWN_DRAW_INSTRUCTION")
        args.extend(("--cmd", command + " " + json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False)))
    args.extend(("--save", str(output)))
    if preview is not None:
        args.extend(("--export", str(preview)))
    return args


def run_proof(cli: str, instructions: tuple[DrawInstruction, ...],
              output: Path, preview: Path | None = None) -> dict:
    """Create a NEW disposable CADCraft drawing and independently inspect it."""
    output = Path(output)
    if output.exists() or (preview is not None and Path(preview).exists()):
        raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE")
    output.parent.mkdir(parents=True, exist_ok=True)
    args = cadcraft_argv(cli, instructions, output, preview)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
        if proc.returncode != 0:
            raise CadcraftCommandProofError("CADCRAFT_COMMAND_FAILED:" + proc.stderr[-350:])
        result = verify_dxf(output, instructions)
        if preview is not None and not Path(preview).is_file():
            raise CadcraftCommandProofError("PREVIEW_NOT_CREATED")
        return result
    except Exception:
        output.unlink(missing_ok=True)
        if preview is not None:
            Path(preview).unlink(missing_ok=True)
        raise


def demo_instructions() -> tuple[DrawInstruction, ...]:
    """WHD actual ResolvedFeature types, not hand-built DXF geometry."""
    from ae_engine.sheetmetal_features import Vec2
    return from_whd_resolved((
        ResolvedCircle(center=Vec2(25, 30), radius=5),
        ResolvedRect(center=Vec2(70, 45), width=20, height=12, rotation_deg=90),
        ResolvedProfile(points=(
            Vec2(-20, 5), Vec2(-7, 4), Vec2(-5, 16), Vec2(-24, 20),
        )),
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cadcraft-cli", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = run_proof(args.cadcraft_cli, demo_instructions(), args.output, args.preview)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
