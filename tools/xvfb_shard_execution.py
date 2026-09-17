"""T3 Xvfb extension for the authoritative T2 shard execution system.

Shard ownership stays in ``tools.test_shard_execution``. This module adds only
the Xvfb-specific process/display and terminal-classification boundary plus
fail-closed acceptance evidence derived from pytest JUnit output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.phase6_release_test_runner import managed_xvfb, run_process_group
from tools.test_shard_execution import (
    ROOT,
    XVFB_LANE,
    ExecutionError,
    ExecutionPlan,
    _require_manifest,
    _validate_budget,
    _write_json,
    load_execution_config,
    select_shard_nodes,
)


XVFB_SHARD_COUNT = 4
XVFB_ACCEPTED_CLASSIFICATIONS = {"GREEN", "INHERITED_BASELINE_RED"}


def _matrix_entry(shard_id: str, item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ExecutionError(f"MANIFEST_SHARD_INVALID: {XVFB_LANE}:{shard_id}")
    nodes = item.get("nodes")
    count = item.get("count")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise ExecutionError(f"MANIFEST_NODES_INVALID: {XVFB_LANE}:{shard_id}")
    if count != len(nodes):
        raise ExecutionError(
            f"MANIFEST_COUNT_MISMATCH: {XVFB_LANE}:{shard_id} count={count!r} nodes={len(nodes)}"
        )
    return {"lane": XVFB_LANE, "shard_id": shard_id, "node_count": len(nodes)}


def build_xvfb_matrix(
    shard_manifest: dict[str, object],
    *,
    concurrency_budget: int,
) -> ExecutionPlan:
    """Build exactly four logical Xvfb jobs from accepted manifest ownership."""
    budget = _validate_budget(concurrency_budget)
    shards = _require_manifest(shard_manifest)
    lane_shards = shards.get(XVFB_LANE)
    if not isinstance(lane_shards, dict):
        raise ExecutionError(f"MANIFEST_LANE_INVALID: {XVFB_LANE}")
    if len(lane_shards) != XVFB_SHARD_COUNT:
        raise ExecutionError(
            f"XVFB_SHARD_COUNT_MISMATCH: expected={XVFB_SHARD_COUNT} actual={len(lane_shards)}"
        )
    matrix = [
        _matrix_entry(shard_id, lane_shards[shard_id])
        for shard_id in sorted(str(name) for name in lane_shards)
    ]
    return ExecutionPlan(matrix=matrix, max_parallel=min(budget, len(matrix)))


def validate_gui_pytest_args(args: Sequence[str]) -> None:
    """Fail closed on xdist process-count options for real GUI tests."""
    for raw in args:
        arg = str(raw)
        if (
            arg == "-n"
            or re.fullmatch(r"-n(?:auto|\d+)", arg) is not None
            or arg == "--numprocesses"
            or arg.startswith("--numprocesses=")
        ):
            raise ExecutionError(f"XVFB_PARALLEL_PYTEST_FORBIDDEN: {arg}")


def classify_xvfb_failed_nodes(
    *,
    child_rc: int,
    failed_nodes: Iterable[str],
    expected_failed_nodes: Iterable[str],
) -> tuple[int, str]:
    """Preserve accepted T0 failed-node semantics after a terminal child rc."""
    actual = {str(node) for node in failed_nodes}
    expected = {str(node) for node in expected_failed_nodes}
    if child_rc == 0 and not actual:
        return 0, "GREEN"
    if child_rc == 1 and actual and actual == expected:
        return 0, "INHERITED_BASELINE_RED"
    return 1, "UNCLASSIFIED_RED"


def resolve_xvfb_terminal_state(
    *,
    child_rc: int | None,
    timed_out: bool,
    classifier_started: bool,
    classifier_rc: int | None,
    classifier_classification: str | None,
) -> str:
    """Keep terminal rc failures distinct from true no-terminal timeout paths."""
    if timed_out:
        if child_rc is None:
            return "HANG_TIMEOUT"
        return "TIMEOUT_TERMINAL_AMBIGUOUS"
    if child_rc is None:
        return "CHILD_TERMINAL_MISSING"
    if not classifier_started:
        return "CLASSIFICATION_NOT_RUN"
    if classifier_rc is None or classifier_classification is None:
        return "CLASSIFIER_INFRA_FAILURE"
    if classifier_classification in XVFB_ACCEPTED_CLASSIFICATIONS:
        return classifier_classification if classifier_rc == 0 else "CLASSIFIER_INFRA_FAILURE"
    if classifier_classification == "UNCLASSIFIED_RED":
        return classifier_classification if classifier_rc != 0 else "CLASSIFIER_INFRA_FAILURE"
    return "CLASSIFIER_INFRA_FAILURE"


def _failed_nodes_from_output(output: str) -> list[str]:
    failed: set[str] = set()
    for line in str(output).splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                failed.add(parts[1])
    return sorted(failed)


def _normalise_failure_message(message: str) -> str:
    return re.sub(r"0x[0-9a-fA-F]+", "0xADDR", str(message))


def _exception_type(item: ET.Element, *, kind: str, message: str) -> tuple[str, str]:
    raw_type = (item.get("type") or "").strip()
    if raw_type:
        return raw_type, "junit_type"
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))\b", message)
    if match:
        return match.group(1).split(".")[-1], "message_prefix"
    if kind == "failure" and (message.lstrip().startswith("assert ") or "AssertionError" in message):
        return "AssertionError", "pytest_assertion"
    return kind.upper(), "junit_kind_fallback"


def _failure_location(case: ET.Element, item: ET.Element, node: str) -> tuple[str, int | None]:
    """Read pytest source location from testcase attrs or its failure traceback."""
    node_file = node.split("::", 1)[0].replace("\\", "/")
    file_name = (case.get("file") or node_file).replace("\\", "/")
    raw_line = case.get("line")
    if raw_line is not None and raw_line.isdigit():
        return file_name, int(raw_line)

    traceback = item.text or ""
    for match in re.finditer(r"(?m)^([^:\n]+\.py):(\d+):", traceback):
        candidate = match.group(1).replace("\\", "/").lstrip("./")
        if candidate == node_file.lstrip("./"):
            return node_file, int(match.group(2))
    return file_name, None


def read_xvfb_junit(path: Path, assigned: Iterable[str]) -> dict[str, object]:
    """Reconcile actual terminal testcase identities with immutable assignment.

    The returned failure evidence is derived only from actual JUnit testcase
    records and carries the source location, JUnit failure/error kind, and a
    provenance-tagged exception type for aggregate T0 comparison.
    """
    expected = list(assigned)
    identities: dict[tuple[str, str], str] = {}
    for node in expected:
        file, *names = node.split("::")
        identity = (".".join([file[:-3].replace("/", "."), *names[:-1]]), names[-1])
        if identity in identities:
            raise ExecutionError("XVFB_EXECUTION_NODE_MISMATCH: ambiguous assignment")
        identities[identity] = node
    executed: list[str] = []
    signatures: dict[str, str] = {}
    failure_evidence: dict[str, dict[str, object]] = {}
    counts = dict(passed=0, failures=0, errors=0, skipped=0)
    try:
        root = ET.parse(path).getroot()
        for case in root.iter("testcase"):
            identity = (case.get("classname"), case.get("name"))
            if identity not in identities:
                raise ExecutionError(f"XVFB_EXECUTION_NODE_MISMATCH: unassigned {identity}")
            node = identities[identity]
            executed.append(node)
            failure, error, skipped = case.find("failure"), case.find("error"), case.find("skipped")
            if error is not None or failure is not None:
                item = error if error is not None else failure
                assert item is not None
                kind = "error" if error is not None else "failure"
                counts["errors" if error is not None else "failures"] += 1
                message = _normalise_failure_message(item.get("message", ""))
                signature = f"{kind}:{message}"
                signatures[node] = signature
                exception_type, exception_type_source = _exception_type(
                    item, kind=kind, message=message
                )
                file_name, line = _failure_location(case, item, node)
                failure_evidence[node] = {
                    "file": file_name,
                    "line": line,
                    "junit_kind": kind,
                    "exception_type": exception_type,
                    "exception_type_source": exception_type_source,
                    "signature": signature,
                }
            elif skipped is not None:
                counts["skipped"] += 1
            else:
                counts["passed"] += 1
    except (OSError, ET.ParseError, ValueError) as exc:
        raise ExecutionError(f"XVFB_JUNIT_INVALID: {exc}") from exc
    if sorted(executed) != sorted(expected):
        raise ExecutionError("XVFB_EXECUTION_NODE_MISMATCH: missing or duplicate testcase")
    return {
        "executed_nodes": sorted(executed),
        "failure_signatures": signatures,
        "failure_evidence": failure_evidence,
        **counts,
    }


def validate_xvfb_acceptance_evidence(
    *,
    manifest: dict[str, object],
    results: Sequence[dict[str, object]],
    expected_source_sha: str,
    expected_manifest_sha256: str,
    expected_failure_contract: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Fail closed unless four JUnit-proven shards match one manifest and T0 contract."""
    if not expected_source_sha or not expected_manifest_sha256:
        raise ExecutionError("XVFB_ACCEPTANCE_OWNER_EVIDENCE_MISSING")
    if manifest.get("source_sha") != expected_source_sha:
        raise ExecutionError("XVFB_ACCEPTANCE_SOURCE_SHA_MISMATCH")
    shards = _require_manifest(manifest)
    lane = shards.get(XVFB_LANE)
    if not isinstance(lane, dict) or len(lane) != XVFB_SHARD_COUNT:
        raise ExecutionError("XVFB_ACCEPTANCE_SHARD_SET_INVALID")
    expected_shards = set(str(x) for x in lane)
    if len(results) != XVFB_SHARD_COUNT:
        raise ExecutionError(f"XVFB_RESULT_COUNT={len(results)}")
    actual_ids = [str(p.get("shard_id", "")) for p in results]
    if set(actual_ids) != expected_shards or len(set(actual_ids)) != len(actual_ids):
        raise ExecutionError("XVFB_ACCEPTANCE_SHARD_ID_MISMATCH")

    executed_all: list[str] = []
    failure_evidence: dict[str, dict[str, object]] = {}
    classifications: dict[str, object] = {}
    for payload in results:
        shard_id = str(payload.get("shard_id", ""))
        if payload.get("source_sha") != expected_source_sha:
            raise ExecutionError(f"XVFB_ACCEPTANCE_RESULT_SOURCE_SHA_MISMATCH:{shard_id}")
        if payload.get("manifest_sha256") != expected_manifest_sha256:
            raise ExecutionError(f"XVFB_ACCEPTANCE_MANIFEST_DIGEST_MISMATCH:{shard_id}")
        if payload.get("classification") not in XVFB_ACCEPTED_CLASSIFICATIONS:
            raise ExecutionError(f"XVFB_ACCEPTANCE_CLASSIFICATION_INVALID:{shard_id}")
        if payload.get("timed_out") is not False:
            raise ExecutionError(f"XVFB_ACCEPTANCE_TIMEOUT:{shard_id}")
        if payload.get("classifier_started") is not True or payload.get("classifier_rc") != 0:
            raise ExecutionError(f"XVFB_ACCEPTANCE_CLASSIFIER_INVALID:{shard_id}")
        if payload.get("child_rc") not in {0, 1}:
            raise ExecutionError(f"XVFB_ACCEPTANCE_CHILD_RC_INVALID:{shard_id}")
        executed = payload.get("executed_nodes")
        if not isinstance(executed, list) or not all(isinstance(x, str) for x in executed):
            raise ExecutionError(f"XVFB_ACCEPTANCE_EXECUTED_NODES_MISSING:{shard_id}")
        expected_nodes = lane[shard_id].get("nodes") if isinstance(lane[shard_id], dict) else None
        if not isinstance(expected_nodes, list) or sorted(executed) != sorted(expected_nodes):
            raise ExecutionError(f"XVFB_ACCEPTANCE_JUNIT_SHARD_NODE_MISMATCH:{shard_id}")
        executed_all.extend(executed)
        evidence = payload.get("failure_evidence")
        if not isinstance(evidence, dict):
            raise ExecutionError(f"XVFB_ACCEPTANCE_FAILURE_EVIDENCE_MISSING:{shard_id}")
        failed_nodes = payload.get("failed_nodes")
        if isinstance(failed_nodes, list) and set(evidence) != set(failed_nodes):
            raise ExecutionError(f"XVFB_ACCEPTANCE_JUNIT_LOG_FAILURE_MISMATCH:{shard_id}")
        for node, record in evidence.items():
            if node in failure_evidence or not isinstance(record, dict):
                raise ExecutionError(f"XVFB_ACCEPTANCE_FAILURE_EVIDENCE_DUPLICATE:{node}")
            failure_evidence[node] = record
        classifications[shard_id] = payload.get("classification")

    counts = Counter(executed_all)
    duplicates = sorted(node for node, count in counts.items() if count != 1)
    if duplicates:
        raise ExecutionError(f"XVFB_ACCEPTANCE_JUNIT_DUPLICATE={duplicates}")
    expected_union = {
        node
        for item in lane.values()
        if isinstance(item, dict)
        for node in item.get("nodes", [])
    }
    if set(executed_all) != expected_union:
        raise ExecutionError("XVFB_ACCEPTANCE_JUNIT_UNION_MISMATCH")
    if set(failure_evidence) != set(expected_failure_contract):
        raise ExecutionError("XVFB_ACCEPTANCE_T0_FAILURE_NODE_MISMATCH")

    required_fields = ("file", "line", "junit_kind", "exception_type")
    for node, expected in expected_failure_contract.items():
        actual = failure_evidence[node]
        for field in required_fields:
            if field not in expected or field not in actual or actual[field] != expected[field]:
                raise ExecutionError(
                    f"XVFB_ACCEPTANCE_T0_FAILURE_EVIDENCE_MISMATCH:{node}:{field}:"
                    f"expected={expected.get(field)!r}:actual={actual.get(field)!r}"
                )

    return {
        "source_sha": expected_source_sha,
        "manifest_sha256": expected_manifest_sha256,
        "xvfb_shards": XVFB_SHARD_COUNT,
        "xvfb_unique_nodes": len(expected_union),
        "xvfb_failed_nodes": len(failure_evidence),
        "classifications": dict(sorted(classifications.items())),
    }


def execute_xvfb_shard(
    *,
    nodes: Iterable[str],
    shard_id: str,
    expected_failed_nodes: Iterable[str],
    result_json: Path,
    log_path: Path,
    basetemp: Path,
    timeout_seconds: float,
    pytest_args: Sequence[str] = ("-q", "-ra", "--tb=short", "--durations=30"),
) -> dict[str, object]:
    """Run one exact shard serially in one owned Xvfb display/process."""
    assigned = sorted(str(node) for node in nodes)
    expected = sorted(str(node) for node in expected_failed_nodes)
    if not assigned:
        raise ExecutionError(f"XVFB_EMPTY_SHARD: {shard_id}")
    if timeout_seconds <= 0:
        raise ExecutionError(f"XVFB_TIMEOUT_INVALID: {timeout_seconds!r}")
    validate_gui_pytest_args(pytest_args)
    if any(node not in assigned for node in expected):
        raise ExecutionError(f"XVFB_EXPECTED_FAILURE_OUTSIDE_SHARD: {shard_id}")

    result_json.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    junit_xml = result_json.with_suffix(".xml")
    junit_xml.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *[str(arg) for arg in pytest_args],
        f"--basetemp={basetemp}",
        f"--junitxml={junit_xml}",
        *assigned,
    ]

    child_started_epoch = time.time()
    with managed_xvfb() as session:
        env = os.environ.copy()
        env["DISPLAY"] = session.display
        result = run_process_group(
            command,
            timeout_seconds=float(timeout_seconds),
            cwd=ROOT,
            env=env,
        )
        xvfb_display = session.display
        xvfb_pid = session.pid
    child_ended_epoch = time.time()
    log_path.write_text(result.stdout, encoding="utf-8")
    failed_nodes = _failed_nodes_from_output(result.stdout)

    if result.timed_out:
        child_rc: int | None = None
        classifier_started = False
        classifier_rc: int | None = None
        classifier_classification: str | None = None
    else:
        child_rc = int(result.returncode)
        classifier_started = True
        classifier_rc, classifier_classification = classify_xvfb_failed_nodes(
            child_rc=child_rc,
            failed_nodes=failed_nodes,
            expected_failed_nodes=expected,
        )

    classification = resolve_xvfb_terminal_state(
        child_rc=child_rc,
        timed_out=bool(result.timed_out),
        classifier_started=classifier_started,
        classifier_rc=classifier_rc,
        classifier_classification=classifier_classification,
    )
    execution_proof: dict[str, object] = {}
    proof_error = None
    if not result.timed_out:
        try:
            execution_proof = read_xvfb_junit(junit_xml, assigned)
            if sorted(execution_proof["failure_signatures"]) != failed_nodes:
                raise ExecutionError("XVFB_JUNIT_LOG_FAILURE_MISMATCH")
            if execution_proof["errors"]:
                raise ExecutionError("XVFB_SETUP_TEARDOWN_ERROR")
        except ExecutionError as exc:
            proof_error = str(exc)
            classification = "EXECUTION_PROOF_INVALID"
            classifier_rc = 1
    payload: dict[str, object] = {
        **execution_proof,
        "execution_proof_error": proof_error,
        "junit_xml": str(junit_xml),
        "lane": XVFB_LANE,
        "shard_id": shard_id,
        "assigned_nodes": assigned,
        "assigned_count": len(assigned),
        "expected_failed_nodes": expected,
        "failed_nodes": failed_nodes,
        "xvfb_display": xvfb_display,
        "xvfb_pid": xvfb_pid,
        "child_started_epoch": child_started_epoch,
        "child_ended_epoch": child_ended_epoch,
        "child_rc": child_rc,
        "timed_out": bool(result.timed_out),
        "execution_seconds": float(result.elapsed_seconds),
        "classifier_started": classifier_started,
        "classifier_rc": classifier_rc,
        "classifier_classification": classifier_classification,
        "classification": classification,
        "log_path": str(log_path),
        "result_json": str(result_json),
    }
    _write_json(result_json, payload)
    return payload


def _load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionError("MANIFEST_INVALID: root is not an object")
    _require_manifest(payload)
    return payload


def _load_expected_failures(path: Path, *, shard_id: str) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list) and all(isinstance(node, str) for node in payload):
        return sorted(payload)
    if isinstance(payload, dict):
        nodes = payload.get(shard_id, [])
        if isinstance(nodes, list) and all(isinstance(node, str) for node in nodes):
            return sorted(nodes)
    raise ExecutionError(f"XVFB_EXPECTED_FAILURES_INVALID: {path}")


def _cmd_matrix(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.manifest)
    budget = load_execution_config(args.execution_config)
    plan = build_xvfb_matrix(manifest, concurrency_budget=budget)
    matrix_json = json.dumps({"include": plan.matrix}, ensure_ascii=False, separators=(",", ":"))
    print(matrix_json)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"matrix={matrix_json}\n")
            stream.write(f"max_parallel={plan.max_parallel}\n")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    manifest_bytes = args.manifest.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = _load_manifest(args.manifest)
    source_sha = manifest.get("source_sha")
    if not isinstance(source_sha, str) or not source_sha:
        raise ExecutionError("XVFB_MANIFEST_SOURCE_SHA_MISSING")
    if args.expected_source_sha and source_sha != args.expected_source_sha:
        raise ExecutionError(
            f"XVFB_MANIFEST_SOURCE_SHA_MISMATCH: expected={args.expected_source_sha} actual={source_sha}"
        )
    if args.expected_manifest_sha256 and manifest_sha256 != args.expected_manifest_sha256:
        raise ExecutionError(
            "XVFB_MANIFEST_DIGEST_MISMATCH: "
            f"expected={args.expected_manifest_sha256} actual={manifest_sha256}"
        )
    nodes = select_shard_nodes(manifest, XVFB_LANE, args.shard, allow_xvfb=True)
    expected = _load_expected_failures(args.expected_failures, shard_id=args.shard)
    payload = execute_xvfb_shard(
        nodes=nodes,
        shard_id=args.shard,
        expected_failed_nodes=expected,
        result_json=args.result_json,
        log_path=args.log,
        basetemp=args.basetemp,
        timeout_seconds=args.timeout_seconds,
    )
    payload["source_sha"] = source_sha
    payload["manifest_sha256"] = manifest_sha256
    _write_json(args.result_json, payload)
    return 0 if payload["classification"] in XVFB_ACCEPTED_CLASSIFICATIONS else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute exact WHD Xvfb manifest shards")
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--manifest", type=Path, required=True)
    matrix.add_argument(
        "--execution-config",
        type=Path,
        default=ROOT / "config" / "ci_test_execution.json",
    )
    matrix.add_argument("--github-output", type=Path)
    matrix.set_defaults(handler=_cmd_matrix)

    run = subparsers.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--shard", required=True)
    run.add_argument("--expected-failures", type=Path, required=True)
    run.add_argument("--result-json", type=Path, required=True)
    run.add_argument("--log", type=Path, required=True)
    run.add_argument("--basetemp", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=float, default=900.0)
    run.add_argument("--expected-source-sha")
    run.add_argument("--expected-manifest-sha256")
    run.set_defaults(handler=_cmd_run)

    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (ExecutionError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
