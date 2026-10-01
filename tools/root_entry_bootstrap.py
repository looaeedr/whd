from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

CANONICAL_WORKING_ROOT = "/Google Drive/WHD"
WORK_ROOT_SCHEMA = "WHD_WORK_ROOT_HARD_GATE_V1"
ROOT_LOCAL_SCHEMA = "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1"


def validate_entry_order(
    *,
    working_root: str,
    work_root_gate: Mapping[str, object],
    root_local_gate: Mapping[str, object],
) -> dict[str, object]:
    observed = str(working_root).strip().rstrip("/")
    if observed != CANONICAL_WORKING_ROOT:
        raise ValueError(
            f"working root must be explicitly bound to {CANONICAL_WORKING_ROOT}; got {working_root!r}"
        )
    if work_root_gate.get("schema") != WORK_ROOT_SCHEMA:
        raise ValueError("unexpected work-root hard gate schema")
    sequence = tuple(str(x) for x in work_root_gate.get("required_sequence", ()) or ())
    try:
        root_index = sequence.index("ROOT_LOCAL_FIRST_GATE_READ")
        operation_index = sequence.index("REQUESTED_OPERATION")
    except ValueError as exc:
        raise ValueError("work-root hard gate sequence is incomplete") from exc
    if root_index >= operation_index:
        raise ValueError("ROOT_LOCAL_FIRST must run before requested operation")
    next_gate = work_root_gate.get("next_gate")
    if not isinstance(next_gate, Mapping) or next_gate.get("schema") != ROOT_LOCAL_SCHEMA:
        raise ValueError("work-root hard gate does not wire to ROOT_LOCAL_FIRST")
    if root_local_gate.get("schema") != ROOT_LOCAL_SCHEMA:
        raise ValueError("unexpected root-local-first hard gate schema")
    return {
        "working_root": observed,
        "sequence": [WORK_ROOT_SCHEMA, ROOT_LOCAL_SCHEMA, "REQUESTED_OPERATION"],
    }


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate WHD root bootstrap order")
    parser.add_argument("--working-root", required=True)
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    evidence = validate_entry_order(
        working_root=args.working_root,
        work_root_gate=_json(root / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"),
        root_local_gate=_json(root / ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"),
    )
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
