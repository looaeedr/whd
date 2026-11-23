"""Child-only CADCraft exchange verifier, using the unchanged WHD Engine owner.

Never launched as a GUI, never imports Tk or modifies a WHD Session. Input is
a detached DrawInstruction JSON list over stdin, and the disposable DXF path
is a CLI argument. Exit nonzero on any invalid source or Engine rejection.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from ae_engine.cadcraft_exchange_proof import (
    DrawInstruction, MAX_ENTITY_COUNT, verify_dxf,
)


def main() -> None:
    if len(sys.argv) != 2:
        raise ValueError("CADCRAFT_PROOF_CHILD_ARGUMENTS_INVALID")
    raw = json.load(sys.stdin)
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ENTITY_COUNT:
        raise ValueError("CADCRAFT_PROOF_CHILD_INPUT_INVALID")
    instructions = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"kind", "points", "radius"}:
            raise ValueError("CADCRAFT_PROOF_CHILD_INSTRUCTION_INVALID")
        if item["kind"] not in {"circle", "rectangle", "profile"}:
            raise ValueError("CADCRAFT_PROOF_CHILD_KIND_INVALID")
        points = item["points"]
        if not isinstance(points, list) or not all(
            isinstance(point, list) and len(point) == 2
            and all(type(v) in (int, float) for v in point)
            for point in points
        ):
            raise ValueError("CADCRAFT_PROOF_CHILD_POINTS_INVALID")
        radius = item["radius"]
        if type(radius) not in (int, float):
            raise ValueError("CADCRAFT_PROOF_CHILD_RADIUS_INVALID")
        instructions.append(DrawInstruction(
            kind=item["kind"], points=tuple(tuple(point) for point in points),
            radius=radius,
        ))
    proof = verify_dxf(Path(sys.argv[1]), tuple(instructions))
    print(json.dumps(proof, ensure_ascii=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
