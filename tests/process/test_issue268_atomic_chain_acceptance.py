from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/task_chain_atomic_acceptance_gate.py"
CONTRACT = ROOT / "docs/governance/issue268-t5-atomic-chain-contract.json"
MASTER_TASK_ID = "262"
MASTER_BASE_SHA = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
TARGET = "X"
EXPECTED_STAGES = [f"T{i}" for i in range(8)]


def _load_gate():
    assert GATE.is_file(), "#268 requires tools/task_chain_atomic_acceptance_gate.py"
    spec = importlib.util.spec_from_file_location("task_chain_atomic_acceptance_issue268", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(index: int) -> str:
    return f"{index:040x}"


def _full_manifest() -> dict:
    stages = []
    parent = MASTER_BASE_SHA
    for index, stage_id in enumerate(EXPECTED_STAGES, start=1):
        head = _sha(index)
        stages.append(
            {
                "stage_id": stage_id,
                "issue_number": 262 + index,
                "test_status": "PASS",
                "task_acceptance": "ACCEPTED",
                "parent_sha": parent,
                "accepted_head": head,
                "evidence": {
                    "red": f"{stage_id}-red",
                    "green": f"{stage_id}-green",
                    "lineage": f"{stage_id}-lineage",
                    "acceptance_record": f"{stage_id}-acceptance",
                },
            }
        )
        parent = head
    return {
        "schema_version": 1,
        "master_task_id": MASTER_TASK_ID,
        "master_base_sha": MASTER_BASE_SHA,
        "target": TARGET,
        "chain_head": stages[-1]["accepted_head"],
        "stages": stages,
    }


def _write_json(tmp_path: Path, payload: dict, name: str = "manifest.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _evaluate(gate, tmp_path: Path, payload: dict):
    return gate.evaluate_manifest(_write_json(tmp_path, payload), CONTRACT)


def test_full_t0_to_t7_chain_is_eligible_for_integration_acceptance_consideration(
    tmp_path: Path,
) -> None:
    gate = _load_gate()
    decision = _evaluate(gate, tmp_path, _full_manifest())
    assert decision.eligible is True
    assert decision.code == "ELIGIBLE_FOR_INTEGRATION_ACCEPTANCE_CONSIDERATION"
    assert decision.chain_head == _sha(8)


@pytest.mark.parametrize("kept_count", [0, 1, 2, 5, 6, 7])
def test_any_partial_stage_subset_is_denied(tmp_path: Path, kept_count: int) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"] = payload["stages"][:kept_count]
    if payload["stages"]:
        payload["chain_head"] = payload["stages"][-1]["accepted_head"]
    with pytest.raises(gate.AtomicChainAcceptanceError, match="partial|complete|T0.*T7|stage"):
        _evaluate(gate, tmp_path, payload)


def test_current_t0_through_t5_all_pass_still_has_no_x_eligibility(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"] = payload["stages"][:6]
    payload["chain_head"] = payload["stages"][-1]["accepted_head"]
    with pytest.raises(gate.AtomicChainAcceptanceError, match="partial|complete|T0.*T7|stage"):
        _evaluate(gate, tmp_path, payload)


@pytest.mark.parametrize("stage_index", range(8))
def test_pass_without_task_acceptance_is_denied(tmp_path: Path, stage_index: int) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"][stage_index]["task_acceptance"] = "PENDING"
    with pytest.raises(gate.AtomicChainAcceptanceError, match="Task Acceptance|task_acceptance|ACCEPTED"):
        _evaluate(gate, tmp_path, payload)


@pytest.mark.parametrize("evidence_key", ["red", "green", "lineage", "acceptance_record"])
def test_missing_evidence_is_denied(tmp_path: Path, evidence_key: str) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"][3]["evidence"].pop(evidence_key)
    with pytest.raises(gate.AtomicChainAcceptanceError, match="evidence"):
        _evaluate(gate, tmp_path, payload)


def test_nonpass_stage_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"][6]["test_status"] = "FAIL"
    with pytest.raises(gate.AtomicChainAcceptanceError, match="PASS|test_status"):
        _evaluate(gate, tmp_path, payload)


def test_broken_lineage_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"][4]["parent_sha"] = _sha(99)
    with pytest.raises(gate.AtomicChainAcceptanceError, match="lineage|parent"):
        _evaluate(gate, tmp_path, payload)


def test_chain_head_must_match_final_accepted_head(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["chain_head"] = _sha(99)
    with pytest.raises(gate.AtomicChainAcceptanceError, match="chain_head|head"):
        _evaluate(gate, tmp_path, payload)


def test_duplicate_stage_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload["stages"][7]["stage_id"] = "T6"
    with pytest.raises(gate.AtomicChainAcceptanceError, match="stage|T0.*T7|order|duplicate"):
        _evaluate(gate, tmp_path, payload)


def test_extra_stage_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    extra = dict(payload["stages"][-1])
    extra["stage_id"] = "T8"
    extra["issue_number"] = 271
    extra["parent_sha"] = payload["stages"][-1]["accepted_head"]
    extra["accepted_head"] = _sha(9)
    payload["stages"].append(extra)
    payload["chain_head"] = extra["accepted_head"]
    with pytest.raises(gate.AtomicChainAcceptanceError, match="stage|T0.*T7|order|extra"):
        _evaluate(gate, tmp_path, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("master_task_id", "999"),
        ("master_base_sha", "f" * 40),
        ("target", "cleanup/2d-3d-sync"),
    ],
)
def test_frozen_identity_mismatch_is_denied(tmp_path: Path, field: str, value: str) -> None:
    gate = _load_gate()
    payload = _full_manifest()
    payload[field] = value
    with pytest.raises(gate.AtomicChainAcceptanceError, match="identity|master|base|TARGET|target"):
        _evaluate(gate, tmp_path, payload)


def test_malformed_or_ambiguous_json_fails_closed(tmp_path: Path) -> None:
    gate = _load_gate()
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version": 1,', encoding="utf-8")
    with pytest.raises(gate.AtomicChainAcceptanceError, match="malformed"):
        gate.evaluate_manifest(malformed, CONTRACT)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps(_full_manifest())[:-1] + ', "target": "main"}',
        encoding="utf-8",
    )
    with pytest.raises(gate.AtomicChainAcceptanceError, match="duplicate|ambiguous"):
        gate.evaluate_manifest(duplicate, CONTRACT)


def test_cli_denies_partial_chain_with_nonzero_exit_and_never_claims_x_merge(
    tmp_path: Path,
) -> None:
    _load_gate()
    payload = _full_manifest()
    payload["stages"] = payload["stages"][:6]
    payload["chain_head"] = payload["stages"][-1]["accepted_head"]
    result = subprocess.run(
        [sys.executable, str(GATE), "--manifest", str(_write_json(tmp_path, payload)), "--contract", str(CONTRACT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "ATOMIC_CHAIN_DENY" in result.stdout
    assert "merge" not in result.stdout.lower()


def test_cli_full_chain_allows_consideration_only_not_integration_or_merge(tmp_path: Path) -> None:
    _load_gate()
    result = subprocess.run(
        [sys.executable, str(GATE), "--manifest", str(_write_json(tmp_path, _full_manifest())), "--contract", str(CONTRACT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ATOMIC_CHAIN_GREEN" in result.stdout
    assert "ELIGIBLE_FOR_INTEGRATION_ACCEPTANCE_CONSIDERATION" in result.stdout
    assert "merge" not in result.stdout.lower()


def test_checked_in_contract_pins_master_identity_and_exact_stage_set() -> None:
    gate = _load_gate()
    contract = gate.load_contract(CONTRACT)
    assert contract.master_task_id == MASTER_TASK_ID
    assert contract.master_base_sha == MASTER_BASE_SHA
    assert contract.target == TARGET
    assert list(contract.expected_stages) == EXPECTED_STAGES
