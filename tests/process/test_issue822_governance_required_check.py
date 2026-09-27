from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "governance_parity_gate.py"
WORKFLOW = ROOT / ".github" / "workflows" / "whd-governance-mirror-gate.yml"


def _load():
    spec = importlib.util.spec_from_file_location("governance_parity_gate_issue822", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "schema": "WHD_GOVERNANCE_MIRROR_MANIFEST_V1",
        "branches": ["main", "cleanup/2d-3d-sync"],
        "product_authority": "cleanup/2d-3d-sync",
        "governance_mode": "BIDIRECTIONAL_MIRROR",
        "governance_paths": [
            "AGENTS.md",
            "tools/governance_parity_gate.py",
            ".github/workflows/whd-governance-mirror-gate.yml",
        ],
        "governance_prefixes": [],
    }


def test_issue822_candidate_parity_seam_exists_and_fails_mismatch(monkeypatch) -> None:
    gate = _load()
    manifest = _manifest()

    monkeypatch.setattr(
        gate,
        "_governed_tree_paths",
        lambda ref, payload: set(payload["governance_paths"]),
    )

    candidate = {
        "AGENTS.md": "1" * 40,
        "tools/governance_parity_gate.py": "2" * 40,
        ".github/workflows/whd-governance-mirror-gate.yml": "3" * 40,
    }
    opposite = {
        "AGENTS.md": "1" * 40,
        "tools/governance_parity_gate.py": "9" * 40,
        ".github/workflows/whd-governance-mirror-gate.yml": "3" * 40,
    }

    def blob_at(ref: str, path: str) -> str | None:
        if ref == "candidate":
            return candidate[path]
        if ref == "opposite":
            return opposite[path]
        raise AssertionError(ref)

    monkeypatch.setattr(gate, "_blob_at", blob_at)

    result = gate.evaluate_pr_candidate_parity(
        candidate_ref="candidate",
        target_branch="main",
        opposite_ref="opposite",
        mirror_manifest=manifest,
    )
    assert result["result"] == "FAIL"
    assert result["reason"] == "UNKNOWN_DIVERGENCE"
    assert result["path"] == "tools/governance_parity_gate.py"


def test_issue822_candidate_parity_passes_when_governed_blobs_match(monkeypatch) -> None:
    gate = _load()
    manifest = _manifest()

    monkeypatch.setattr(
        gate,
        "_governed_tree_paths",
        lambda ref, payload: set(payload["governance_paths"]),
    )
    blobs = {
        "AGENTS.md": "1" * 40,
        "tools/governance_parity_gate.py": "2" * 40,
        ".github/workflows/whd-governance-mirror-gate.yml": "3" * 40,
    }
    monkeypatch.setattr(gate, "_blob_at", lambda ref, path: blobs[path])

    result = gate.evaluate_pr_candidate_parity(
        candidate_ref="candidate",
        target_branch="cleanup/2d-3d-sync",
        opposite_ref="opposite",
        mirror_manifest=manifest,
    )
    assert result["result"] == "GREEN"
    assert result["reason"] == "PR_CANDIDATE_GOVERNANCE_PARITY_PROVEN"


def test_issue822_workflow_runs_candidate_parity_on_pull_request() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "Verify merge-time governance candidate parity",
        "--verify-pr-candidate-parity",
        "github.event_name == 'pull_request'",
        "github.base_ref",
        "refs/remotes/origin/main",
        "refs/remotes/origin/cleanup/2d-3d-sync",
        "WHD-Governance-Mirror-Pair",
        "GOVERNANCE_MIRROR_PAIR_NOT_RECIPROCAL",
        "pull/$PAIR/head",
        "types: [opened, synchronize, reopened, edited]",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: merge-time governance hard gate missing tokens: {missing}"


def test_issue822_regression_is_in_governance_manifest() -> None:
    import json

    manifest = json.loads(
        (ROOT / "docs" / "governance" / "governance_mirror_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert "tests/process/test_issue822_governance_required_check.py" in manifest[
        "governance_paths"
    ]
