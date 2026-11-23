"""Temporary #3415 Windows control. Verify disposable CADCraft DXF in a fresh child.

This module is deliberately NOT a manufacturing interface. The child invokes
the existing, unmodified Engine verify_dxf, failing closed on any bad input.
It is only used by the isolated diagnosis PR and MUST NOT be merged.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from ae_engine.cadcraft_exchange_proof import DrawInstruction, verify_dxf


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("PROOF_CHILD_EXPECTS_ONE_DXF_PATH")
    raw = json.load(sys.stdin)
    if not isinstance(raw, list) or not raw:
        raise ValueError("PROOF_CHILD_EMPTY_EXPECTED")
    expected = tuple(
        DrawInstruction(
            kind=item["kind"],
            points=tuple((float(x), float(y)) for x, y in item["points"]),
            radius=float(item["radius"]),
        )
        for item in raw
    )
    proof = verify_dxf(Path(sys.argv[1]), expected)
    if proof.get("status") != "PASS":
        raise RuntimeError("PROOF_CHILD_ENGINE_REJECTED")
    print(json.dumps(proof, ensure_ascii=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
