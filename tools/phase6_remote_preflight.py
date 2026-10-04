# -*- coding: utf-8 -*-
"""Canonical remote Phase6 Preflight runner shared by comment and push transports."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from tools.execution_entry_contract import build_phase6_preflight_evidence
from tools.phase6_skill_preflight import required_references_for, required_skills_for

ROOT = Path(__file__).resolve().parents[1]
REMOTE_RESULT_SCHEMA = "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1"


class RemotePhase6PreflightError(ValueError):
    pass


def _declared_skill_name(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for raw in lines[1:]:
        if raw.strip() == "---":
            break
        if raw.startswith("name:"):
            return raw.split(":", 1)[1].strip().strip("'\"")
    return None


def _request(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise RemotePhase6PreflightError("remote preflight request must be an object")
    request = {str(k): v for k, v in payload.items()}
    for key in ("issue", "worker", "executor_source", "branch", "head_sha", "task"):
        if key not in request:
            raise RemotePhase6PreflightError(f"remote preflight request missing {key}")
    changed = request.get("changed_files", [])
    if not isinstance(changed, list) or not all(isinstance(x, str) for x in changed):
        raise RemotePhase6PreflightError("remote preflight changed_files must be strings")
    return request


def run_remote_preflight(
    request_payload: object,
    *,
    run_id: int,
    root: Path = ROOT,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    request = _request(request_payload)
    task = str(request["task"])
    changed_files = [str(x) for x in request.get("changed_files", [])]

    skills = required_skills_for(task=task, changed_files=changed_files)
    references = required_references_for(task=task, changed_files=changed_files)

    all_skill_paths = list((root / ".agents/skills").glob("**/SKILL.md"))
    skill_paths: list[dict[str, str]] = []
    evidence_lines: list[str] = []
    for skill in skills:
        matches = [p for p in all_skill_paths if _declared_skill_name(p) == skill]
        if len(matches) != 1:
            raise RemotePhase6PreflightError(
                f"required skill unavailable or ambiguous: {skill}: {matches}"
            )
        rel = matches[0].relative_to(root).as_posix()
        matches[0].read_text(encoding="utf-8")
        skill_paths.append({"name": skill, "path": rel})
        evidence_lines.append(f"READ_SKILL: {skill} path={rel}")

    for reference in references:
        path = root / reference
        if not path.is_file():
            raise RemotePhase6PreflightError(f"required reference missing: {reference}")
        path.read_text(encoding="utf-8")
        evidence_lines.append(f"READ_REFERENCE: {reference}")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise RemotePhase6PreflightError("observed_at must be timezone-aware")

    receipt: dict[str, object] = {
        "schema": REMOTE_RESULT_SCHEMA,
        "issue": int(request["issue"]),
        "worker": str(request["worker"]),
        "executor_source": str(request["executor_source"]),
        "branch": str(request["branch"]),
        "head_sha": str(request["head_sha"]).lower(),
        "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
        "changed_files": changed_files,
        "required_skills": skill_paths,
        "required_references": list(references),
        "evidence_sha256": hashlib.sha256(
            ("\n".join(evidence_lines) + "\n").encode("utf-8")
        ).hexdigest(),
        "result": "GREEN",
        "reason": "PHASE6_PREFLIGHT_EXECUTED_AND_REQUIREMENTS_RESOLVED",
        "run_id": int(run_id),
    }
    for key in ("request_comment_id", "request_id", "request_source", "lane_id"):
        if key in request:
            receipt[key] = request[key]

    invocation = str(request.get("invocation_identity") or "").strip()
    if invocation:
        receipt["invocation_identity"] = invocation
    if invocation:
        receipt["preflight_evidence"] = build_phase6_preflight_evidence(
            issue=int(request["issue"]),
            invocation_identity=invocation,
            branch=str(request["branch"]),
            head_sha=str(request["head_sha"]),
            required_skills=skills,
            completed_skills=skills,
            required_references=references,
            completed_references=references,
            observed_at=now,
        )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run canonical remote Phase6 Preflight")
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    request = json.loads(args.request_file.read_text(encoding="utf-8"))
    receipt = run_remote_preflight(request, run_id=args.run_id)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
