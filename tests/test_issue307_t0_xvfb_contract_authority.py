"""Authority regression: T3 inherited Xvfb failures must come from accepted T0."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
T0_WORKFLOW = ROOT / ".github/workflows/issue304-t0-baseline.yml"
T3_CONTRACT = ROOT / "config/issue307_t0_xvfb_failure_contract.json"


def _authoritative_t0_xvfb_nodes() -> set[str]:
    text = T0_WORKFLOW.read_text(encoding="utf-8")
    marker = "expected_xvfb = {"
    assert marker in text, "T0_EXPECTED_XVFB_SOURCE_MISSING"
    block = text.split(marker, 1)[1].split("\n          }", 1)[0]
    nodes = set(re.findall(r"'(tests/[^']+::[^']+)'", block))
    assert len(nodes) == 13, f"T0_EXPECTED_XVFB_COUNT_MISMATCH={len(nodes)}"
    return nodes


def test_issue307_t0_failure_contract_uses_exact_authoritative_t0_xvfb_node_set() -> None:
    authoritative = _authoritative_t0_xvfb_nodes()
    contract = json.loads(T3_CONTRACT.read_text(encoding="utf-8"))
    actual = set(contract["failures"])
    assert actual == authoritative, {
        "missing_from_contract": sorted(authoritative - actual),
        "extra_in_contract": sorted(actual - authoritative),
    }


def test_issue307_t0_contract_provenance_is_exact_accepted_t0_artifact() -> None:
    contract = json.loads(T3_CONTRACT.read_text(encoding="utf-8"))
    assert contract["provenance"] == {
        "workflow": ".github/workflows/issue304-t0-baseline.yml",
        "run_id": 35092857584,
        "head_sha": "2a99806493c69f4a6c9142d43dd502c7eb65757a",
        "artifact_name": "issue304-t0-baseline-evidence-v2",
        "artifact_id": 10445586630,
        "artifact_digest": "sha256:d27bbb5dddbba7b10364c830875e4289d362a7f256dc6e1b425b2bf320166d77",
    }
