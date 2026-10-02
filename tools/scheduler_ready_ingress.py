"""Deterministic scheduler-side discovery for explicit READY ingress.

Open Issues remain non-authoritative.  A scheduler may surface an Issue only
when the repository owner authored an exact machine-readable dispatch marker.
The resulting object is still only a plan for ``execution_dispatch_ingress``;
it does not mutate ``coord/execution-v2`` or grant a lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from tools.execution_dispatch_ingress import DispatchIngressRequest

MARKER = "WHD_SCHEDULER_DISPATCH_REQUEST_V1"
LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
_ALLOWED_LANES = {"ANY", "A", "B"}


class SchedulerIssueCandidateError(ValueError):
    """Raised when an Issue is not valid explicit scheduler-dispatch authority."""


@dataclass(frozen=True)
class SchedulerDispatchCandidate:
    issue: int
    lane: str
    authority_ref: str
    ingress_request: DispatchIngressRequest

    def matches_lane(self, lane_id: str) -> bool:
        if self.lane == "ANY":
            return lane_id in {LANE_A, LANE_B}
        if self.lane == "A":
            return lane_id == LANE_A
        if self.lane == "B":
            return lane_id == LANE_B
        return False


def _positive_issue(value: object) -> int:
    if isinstance(value, bool):
        raise SchedulerIssueCandidateError("issue_number must be a positive integer")
    try:
        issue = int(value)
    except (TypeError, ValueError) as exc:
        raise SchedulerIssueCandidateError("issue_number must be a positive integer") from exc
    if issue <= 0:
        raise SchedulerIssueCandidateError("issue_number must be a positive integer")
    return issue


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SchedulerIssueCandidateError(f"{field} must be nonblank")
    return text


def _parse_marker(body: str) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or lines[0] != MARKER:
        raise SchedulerIssueCandidateError("scheduler dispatch marker missing or not first nonblank line")
    lane_rows = [line.split("=", 1)[1].strip().upper() for line in lines[1:] if line.lower().startswith("lane=")]
    if len(lane_rows) > 1:
        raise SchedulerIssueCandidateError("scheduler dispatch marker contains duplicate lane")
    lane = lane_rows[0] if lane_rows else "ANY"
    if lane not in _ALLOWED_LANES:
        raise SchedulerIssueCandidateError("scheduler dispatch lane must be ANY, A, or B")
    return lane


def build_scheduler_dispatch_candidate(
    issue_snapshot: Mapping[str, object],
    *,
    repository_owner: str,
    source_branch: str,
    source_sha: str,
    target_branch: str,
    target_sha: str,
) -> SchedulerDispatchCandidate:
    """Validate one GitHub Issue as explicit scheduler dispatch authority.

    The marker is intentionally narrow: arbitrary open Issues, PRs, comments,
    labels, or dependency status do not become execution authority by inference.
    """

    if not isinstance(issue_snapshot, Mapping):
        raise SchedulerIssueCandidateError("issue_snapshot must be a mapping")
    if str(issue_snapshot.get("state") or "").lower() != "open":
        raise SchedulerIssueCandidateError("scheduler dispatch issue must be open")
    if issue_snapshot.get("pull_request") is not None:
        raise SchedulerIssueCandidateError("pull request is not a scheduler dispatch issue")

    user = issue_snapshot.get("user")
    author = str(user.get("login") or "").strip() if isinstance(user, Mapping) else ""
    owner = _required_text(repository_owner, "repository_owner")
    if author != owner:
        raise SchedulerIssueCandidateError("scheduler dispatch issue must be authored by repository owner")

    issue = _positive_issue(issue_snapshot.get("issue_number") or issue_snapshot.get("number"))
    lane = _parse_marker(str(issue_snapshot.get("body") or ""))
    authority_ref = f"github-issue:{issue}:{MARKER}"
    created_at = str(issue_snapshot.get("created_at") or "").strip() or None
    request = DispatchIngressRequest(
        issue=issue,
        execution_intent="SCHEDULER_LANE",
        authority_kind="USER_EXPLICIT",
        authority_ref=authority_ref,
        source_branch=_required_text(source_branch, "source_branch"),
        source_sha=_required_text(source_sha, "source_sha"),
        work_branch=f"scheduler/issue{issue}-auto-dispatch",
        target_branch=_required_text(target_branch, "target_branch"),
        target_sha=_required_text(target_sha, "target_sha"),
        parent_issue=None,
        slot_id=None,
        created_at=created_at,
    )
    return SchedulerDispatchCandidate(
        issue=issue,
        lane=lane,
        authority_ref=authority_ref,
        ingress_request=request,
    )
