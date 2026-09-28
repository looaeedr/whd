"""Canonical scheduler startup bundle for WHD Flow v2.

The bundle is a read-only bootstrap artifact.  It never grants mutation
authority.  Its purpose is to collapse repeated scheduler startup reads and to
make the no-work path provable without running remote Phase6 Preflight.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import re
from typing import Iterable

from tools.execution_ready_index import ExecutionReadyIndex
from tools.execution_record import ExecutionRecord
from tools.execution_scheduler_view import SchedulerView, build_scheduler_view
from tools.work_root_gate import validate_work_root_gate_evidence

SCHEMA = "WHD_SCHEDULER_STARTUP_BUNDLE_V1"
_NO_WORK = "NO_EXECUTABLE_WORK"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SchedulerStartupBundleError(ValueError):
    """Raised when a startup bundle cannot be built safely."""


def _coord_head(value: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise SchedulerStartupBundleError("coord_head must be a 40-character lowercase SHA")
    return text


def _projection_payload(view: SchedulerView) -> dict[str, object]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in asdict(view).items()
    }


def _fingerprint(*, coord_head: str, projection: dict[str, object]) -> str:
    payload = {
        "coord_head": coord_head,
        "projection": projection,
    }
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def build_scheduler_startup_bundle(
    records: Iterable[ExecutionRecord],
    *,
    lane_id: str,
    invocation_identity: str,
    now: str,
    coord_head: str,
    work_root_gate_evidence: dict[str, object],
    ready_index: ExecutionReadyIndex | None = None,
) -> dict[str, object]:
    """Build one read-only startup projection for a scheduler invocation."""
    validate_work_root_gate_evidence(
        work_root_gate_evidence,
        execution_mode="SCHEDULER_LANE",
    )
    head = _coord_head(coord_head)
    view = build_scheduler_view(
        records,
        lane_id=lane_id,
        invocation_identity=invocation_identity,
        now=now,
        ready_index=ready_index,
    )
    projection = _projection_payload(view)
    no_work = view.decision == _NO_WORK
    if no_work and (
        view.current_issue is not None
        or view.selected_issue is not None
        or view.ready_issues
        or view.requires_transaction is not None
    ):
        raise SchedulerStartupBundleError("NO_EXECUTABLE_WORK projection contains actionable state")

    return {
        "schema": SCHEMA,
        "coord_head": head,
        "lane_id": view.lane_id,
        "invocation_identity": view.invocation_identity,
        "projection": projection,
        "projection_fingerprint": _fingerprint(coord_head=head, projection=projection),
        "no_work_observed": no_work,
        "requires_project_startup": True,
        "requires_phase6_preflight": True,
        "can_reuse_projection_after_preflight": True,
        "work_root_gate": dict(work_root_gate_evidence),
    }


def validate_scheduler_startup_bundle(
    bundle: dict[str, object],
    *,
    lane_id: str,
    invocation_identity: str,
) -> dict[str, object]:
    if not isinstance(bundle, dict):
        raise SchedulerStartupBundleError("startup bundle must be an object")
    if bundle.get("schema") != SCHEMA:
        raise SchedulerStartupBundleError("unexpected startup bundle schema")
    if bundle.get("lane_id") != lane_id:
        raise SchedulerStartupBundleError("startup bundle lane mismatch")
    if bundle.get("invocation_identity") != invocation_identity:
        raise SchedulerStartupBundleError("startup bundle invocation mismatch")
    validate_work_root_gate_evidence(
        bundle.get("work_root_gate"),
        execution_mode="SCHEDULER_LANE",
    )
    projection = bundle.get("projection")
    if not isinstance(projection, dict):
        raise SchedulerStartupBundleError("startup bundle projection must be an object")
    head = _coord_head(str(bundle.get("coord_head") or ""))
    expected = _fingerprint(coord_head=head, projection=projection)
    if bundle.get("projection_fingerprint") != expected:
        raise SchedulerStartupBundleError("startup bundle fingerprint mismatch")

    no_work = projection.get("decision") == _NO_WORK
    if bool(bundle.get("no_work_observed")) != no_work:
        raise SchedulerStartupBundleError("startup bundle no-work classification mismatch")
    if bundle.get("requires_project_startup") is not True:
        raise SchedulerStartupBundleError("startup bundle must preserve project startup gate")
    if bundle.get("requires_phase6_preflight") is not True:
        raise SchedulerStartupBundleError("startup bundle must preserve Phase6 Preflight")
    if bundle.get("can_reuse_projection_after_preflight") is not True:
        raise SchedulerStartupBundleError("startup bundle reuse policy mismatch")
    return dict(bundle)


def bundle_matches_coord_head(bundle: dict[str, object], observed_coord_head: str) -> bool:
    """Return True only when the bootstrap projection is still on the same coord head."""
    return str(bundle.get("coord_head") or "") == _coord_head(observed_coord_head)
