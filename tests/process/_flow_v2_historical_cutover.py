from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/process/WHD_PROCESS_TEST_CLASSIFICATION_V1.json"
FLOW = ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"


def retirement_contract() -> dict[str, object]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["status"] == "CURRENT"
    assert payload["current_execution_authority"] == ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    assert payload["policy"] == "RETIRED_EXECUTION_SURFACES_MUST_BE_ABSENT"
    return payload


def assert_retired_execution_surfaces_absent() -> None:
    payload = retirement_contract()
    for rel in payload["retired_paths"]:
        assert not (ROOT / rel).exists(), f"retired path regrew: {rel}"

    for rel in payload["current_surfaces"]:
        path = ROOT / rel
        assert path.exists(), f"CURRENT surface missing: {rel}"
        text = path.read_text(encoding="utf-8")
        for token in payload["retired_tokens"]:
            assert token not in text, f"retired token {token!r} regrew in {rel}"

    flow = FLOW.read_text(encoding="utf-8")
    assert "WHD_EXECUTION_RECORD_V2" in flow
    assert "MERGE → FINALIZE → DONE" in flow
