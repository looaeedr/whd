"""Fail-closed atomic Task Acceptance gate for the #262 X task chain.

The gate grants only eligibility to *consider* a later Integration Acceptance.  It never
performs integration and never treats a partial set of successful stages as sufficient.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ELIGIBLE_CODE = "ELIGIBLE_FOR_INTEGRATION_ACCEPTANCE_CONSIDERATION"
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "master_task_id",
    "master_base_sha",
    "target",
    "chain_head",
    "stages",
}
_STAGE_FIELDS = {
    "stage_id",
    "issue_number",
    "test_status",
    "task_acceptance",
    "parent_sha",
    "accepted_head",
    "evidence",
}


class AtomicChainAcceptanceError(RuntimeError):
    """Raised whenever atomic chain eligibility cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise AtomicChainAcceptanceError(
                f"ambiguous JSON: duplicate key {key!r}"
            )
        payload[key] = value
    return payload


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise AtomicChainAcceptanceError(f"{label} not found: {path}") from exc
    except AtomicChainAcceptanceError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise AtomicChainAcceptanceError(f"malformed {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AtomicChainAcceptanceError(f"malformed {label}: root must be an object")
    return payload


def _require_exact_fields(payload: dict[str, object], expected: set[str], *, label: str) -> None:
    observed = set(payload)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise AtomicChainAcceptanceError(
            f"{label} schema mismatch: missing={missing} extra={extra}"
        )


def _require_text(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AtomicChainAcceptanceError(f"{label} {key} must be nonblank text")
    return value.strip()


def _require_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise AtomicChainAcceptanceError(
            f"{label} must be a 40-character lowercase SHA"
        )
    return value


@dataclass(frozen=True)
class AtomicChainContract:
    schema_version: int
    master_task_id: str
    master_base_sha: str
    target: str
    expected_stages: tuple[str, ...]
    expected_issue_numbers: tuple[int, ...]
    required_evidence: tuple[str, ...]


@dataclass(frozen=True)
class AtomicChainDecision:
    eligible: bool
    code: str
    chain_head: str


def load_contract(path: Path) -> AtomicChainContract:
    payload = _read_json(path, label="atomic-chain contract")
    expected_fields = {
        "schema_version",
        "master_task_id",
        "master_base_sha",
        "target",
        "expected_stages",
        "expected_issue_numbers",
        "required_evidence",
    }
    _require_exact_fields(payload, expected_fields, label="atomic-chain contract")

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise AtomicChainAcceptanceError("atomic-chain contract schema_version must be 1")

    master_task_id = _require_text(payload, "master_task_id", label="contract")
    master_base_sha = _require_sha(
        payload.get("master_base_sha"), label="contract master_base_sha"
    )
    target = _require_text(payload, "target", label="contract")
    if target != "X":
        raise AtomicChainAcceptanceError(
            f"contract TARGET identity must be 'X', got {target!r}"
        )

    raw_stages = payload.get("expected_stages")
    if not isinstance(raw_stages, list) or not raw_stages or not all(
        isinstance(value, str) and value for value in raw_stages
    ):
        raise AtomicChainAcceptanceError("contract expected_stages must be a nonempty text list")
    expected_stages = tuple(raw_stages)
    if len(set(expected_stages)) != len(expected_stages):
        raise AtomicChainAcceptanceError("contract expected_stages contains duplicate stage ids")

    raw_issues = payload.get("expected_issue_numbers")
    if not isinstance(raw_issues, list) or len(raw_issues) != len(expected_stages):
        raise AtomicChainAcceptanceError(
            "contract expected_issue_numbers must align 1:1 with expected_stages"
        )
    expected_issue_numbers: list[int] = []
    for value in raw_issues:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AtomicChainAcceptanceError(
                "contract expected_issue_numbers must contain positive integers"
            )
        expected_issue_numbers.append(value)
    if len(set(expected_issue_numbers)) != len(expected_issue_numbers):
        raise AtomicChainAcceptanceError("contract expected_issue_numbers contains duplicates")

    raw_evidence = payload.get("required_evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence or not all(
        isinstance(value, str) and value for value in raw_evidence
    ):
        raise AtomicChainAcceptanceError("contract required_evidence must be a nonempty text list")
    required_evidence = tuple(raw_evidence)
    if len(set(required_evidence)) != len(required_evidence):
        raise AtomicChainAcceptanceError("contract required_evidence contains duplicates")

    return AtomicChainContract(
        schema_version=1,
        master_task_id=master_task_id,
        master_base_sha=master_base_sha,
        target=target,
        expected_stages=expected_stages,
        expected_issue_numbers=tuple(expected_issue_numbers),
        required_evidence=required_evidence,
    )


def _validate_manifest_identity(
    payload: dict[str, object], contract: AtomicChainContract
) -> None:
    _require_exact_fields(payload, _TOP_LEVEL_FIELDS, label="manifest")

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != contract.schema_version:
        raise AtomicChainAcceptanceError("manifest identity schema_version mismatch")

    master_task_id = _require_text(payload, "master_task_id", label="manifest")
    if master_task_id != contract.master_task_id:
        raise AtomicChainAcceptanceError(
            "manifest master identity mismatch: "
            f"expected={contract.master_task_id!r} observed={master_task_id!r}"
        )

    master_base_sha = _require_sha(
        payload.get("master_base_sha"), label="manifest master_base_sha"
    )
    if master_base_sha != contract.master_base_sha:
        raise AtomicChainAcceptanceError(
            "manifest base identity mismatch: "
            f"expected={contract.master_base_sha} observed={master_base_sha}"
        )

    target = _require_text(payload, "target", label="manifest")
    if target != contract.target:
        raise AtomicChainAcceptanceError(
            f"manifest TARGET identity mismatch: expected={contract.target!r} observed={target!r}"
        )


def evaluate_manifest(manifest_path: Path, contract_path: Path) -> AtomicChainDecision:
    contract = load_contract(contract_path)
    payload = _read_json(manifest_path, label="atomic-chain manifest")
    _validate_manifest_identity(payload, contract)

    raw_stages = payload.get("stages")
    if not isinstance(raw_stages, list):
        raise AtomicChainAcceptanceError("stages must be a list")

    observed_stage_ids = [
        stage.get("stage_id") if isinstance(stage, dict) else None
        for stage in raw_stages
    ]
    if tuple(observed_stage_ids) != contract.expected_stages:
        expected = "..".join((contract.expected_stages[0], contract.expected_stages[-1]))
        raise AtomicChainAcceptanceError(
            "partial or invalid stage chain: complete ordered "
            f"{expected} stage sequence required; observed={observed_stage_ids!r}"
        )

    expected_parent = contract.master_base_sha
    final_head = ""
    required_evidence = set(contract.required_evidence)

    for index, raw_stage in enumerate(raw_stages):
        if not isinstance(raw_stage, dict):
            raise AtomicChainAcceptanceError(f"stage {index} must be an object")
        _require_exact_fields(raw_stage, _STAGE_FIELDS, label=f"stage {index}")

        stage_id = _require_text(raw_stage, "stage_id", label=f"stage {index}")
        expected_stage = contract.expected_stages[index]
        if stage_id != expected_stage:
            raise AtomicChainAcceptanceError(
                f"stage order mismatch: expected={expected_stage} observed={stage_id}"
            )

        issue_number = raw_stage.get("issue_number")
        expected_issue = contract.expected_issue_numbers[index]
        if (
            isinstance(issue_number, bool)
            or not isinstance(issue_number, int)
            or issue_number != expected_issue
        ):
            raise AtomicChainAcceptanceError(
                f"{stage_id} issue identity mismatch: expected={expected_issue} observed={issue_number!r}"
            )

        test_status = _require_text(raw_stage, "test_status", label=stage_id)
        if test_status != "PASS":
            raise AtomicChainAcceptanceError(
                f"{stage_id} test_status must be PASS, got {test_status!r}"
            )

        task_acceptance = _require_text(raw_stage, "task_acceptance", label=stage_id)
        if task_acceptance != "ACCEPTED":
            raise AtomicChainAcceptanceError(
                f"{stage_id} Task Acceptance must be ACCEPTED, got {task_acceptance!r}"
            )

        parent_sha = _require_sha(raw_stage.get("parent_sha"), label=f"{stage_id} parent_sha")
        if parent_sha != expected_parent:
            raise AtomicChainAcceptanceError(
                f"{stage_id} lineage parent mismatch: expected={expected_parent} observed={parent_sha}"
            )

        accepted_head = _require_sha(
            raw_stage.get("accepted_head"), label=f"{stage_id} accepted_head"
        )
        if accepted_head == parent_sha:
            raise AtomicChainAcceptanceError(
                f"{stage_id} lineage must advance beyond its parent"
            )

        evidence = raw_stage.get("evidence")
        if not isinstance(evidence, dict):
            raise AtomicChainAcceptanceError(f"{stage_id} evidence must be an object")
        evidence_keys = set(evidence)
        if evidence_keys != required_evidence:
            raise AtomicChainAcceptanceError(
                f"{stage_id} evidence incomplete or ambiguous: "
                f"missing={sorted(required_evidence - evidence_keys)} "
                f"extra={sorted(evidence_keys - required_evidence)}"
            )
        for key in contract.required_evidence:
            value = evidence.get(key)
            if not isinstance(value, str) or not value.strip():
                raise AtomicChainAcceptanceError(
                    f"{stage_id} evidence {key!r} must be nonblank"
                )

        expected_parent = accepted_head
        final_head = accepted_head

    manifest_chain_head = _require_sha(
        payload.get("chain_head"), label="manifest chain_head"
    )
    if manifest_chain_head != final_head:
        raise AtomicChainAcceptanceError(
            "manifest chain_head mismatch: "
            f"expected final accepted head={final_head} observed={manifest_chain_head}"
        )

    return AtomicChainDecision(
        eligible=True,
        code=_ELIGIBLE_CODE,
        chain_head=final_head,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed atomic task-chain eligibility verifier"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        decision = evaluate_manifest(args.manifest, args.contract)
    except AtomicChainAcceptanceError as exc:
        print(f"ATOMIC_CHAIN_DENY reason={exc}")
        return 2

    print(
        "ATOMIC_CHAIN_GREEN "
        f"code={decision.code} chain_head={decision.chain_head}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
