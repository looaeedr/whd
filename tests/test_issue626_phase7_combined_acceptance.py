from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "P7-A": ("issue613-a1-dt-p7-a.json", "issue624-a7-target-completion.json"),
    "P7-B": ("issue613-a1-dt-p7-b.json", "issue617-a2-target-completion.json"),
    "P7-C": ("issue613-a1-dt-p7-c.json", "issue618-a3-target-completion.json"),
    "P7-D": ("issue613-a1-dt-p7-d.json", "issue620-a4-target-completion.json"),
    "P7-E": ("issue613-a1-dt-p7-e.json", "issue621-a5-target-completion.json"),
    "P7-F": ("issue613-a1-dt-p7-f.json", "issue623-a6-target-completion.json"),
    "P7-G": ("issue613-a1-dt-p7-g.json", "issue625-a8-target-completion.json"),
}


def _load(name: str) -> dict:
    path = ROOT / "docs" / "superpowers" / "checkpoints" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase7_all_targets_are_machine_terminal() -> None:
    errors: list[str] = []
    for target, (dt_name, completion_name) in TARGETS.items():
        dt = _load(dt_name)
        decision = dt.get("dt_6_decision", {})
        if decision.get("status") != "COMPLETE":
            errors.append(f"{target} canonical DT-6 not COMPLETE")
        if decision.get("result") != "ACCEPTED":
            errors.append(f"{target} canonical DT-6 result not ACCEPTED")

        completion_path = ROOT / "docs" / "superpowers" / "checkpoints" / completion_name
        if not completion_path.exists():
            errors.append(f"{target} target completion missing: {completion_name}")
            continue
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        if completion.get("schema") != "WHD_PHASE7_TARGET_COMPLETION_V1":
            errors.append(f"{target} target completion schema invalid")
        if completion.get("result") != "ACCEPTED":
            errors.append(f"{target} target completion result not ACCEPTED")
        if completion.get("target_id", completion.get("target")) != target:
            errors.append(f"{target} target completion identity mismatch")

    assert not errors, "PHASE_NOT_COMPLETE:\n" + "\n".join(errors)
