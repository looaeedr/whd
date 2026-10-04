"""Deterministic scheduler-side discovery for explicit READY ingress.


Open Issues remain non-authoritative.  A scheduler may surface an Issue only
when the repository owner authored an exact machine-readable dispatch marker.
The resulting object is still only a plan for ``execution_dispatch_ingress``;
it does not mutate ``coord/execution-v2`` or grant a lease.
"""


from __future__ import annotations


from dataclasses import dataclass
from typing import Mapping


from tools.execution_action_contract import CONTROL_ONLY_COMPLETION_MODE
from tools.execution_dispatch_ingress import DispatchIngressRequest
from tools.execution_record import ActionSpec


MARKER = "WHD_SCHEDULER_DISPATCH_REQUEST_V1"
LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
_ALLOWED_LANES = {"ANY", "A", "B"}
_ALLOWED_COMPLETIONS = {CONTROL_ONLY_COMPLETION_MODE}




class SchedulerIssueCandidateError(ValueError):
    """Raised when an Issue is not valid explicit scheduler-dispatch authority."""




@dataclass(frozen=True)
class SchedulerDispatchCandidate:
    issue: int
    lane: str
    completion: str | None
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




def _parse_marker(body: str) -> tuple[str, str | None]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or lines[0] != MARKER:
        raise SchedulerIssueCandidateError("scheduler dispatch marker missing or not first nonblank line")
    lane_rows = [line.split("=", 1)[1].strip().upper() for line in lines[1:] if line.lower().startswith("lane=")]
    completion_rows = [
        line.split("=", 1)[1].strip().upper()
        for line in lines[1:]
        if line.lower().startswith("completion=")
    ]
    if len(lane_rows) > 1:
        raise SchedulerIssueCandidateError("scheduler dispatch marker contains duplicate lane")
    if len(completion_rows) > 1:
        raise SchedulerIssueCandidateError("scheduler dispatch marker contains duplicate completion")
    lane = lane_rows[0] if lane_rows else "ANY"
    if lane not in _ALLOWED_LANES:
        raise SchedulerIssueCandidateError("scheduler dispatch lane must be ANY, A, or B")
    completion = completion_rows[0] if completion_rows else None
    if completion is not None and completion not in _ALLOWED_COMPLETIONS:
        raise SchedulerIssueCandidateError(
            f"scheduler dispatch completion must be one of {sorted(_ALLOWED_COMPLETIONS)}"
        )
    return lane, completion




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
    lane, completion = _parse_marker(str(issue_snapshot.get("body") or ""))
    authority_ref = f"github-issue:{issue}:{MARKER}"
    created_at = str(issue_snapshot.get("created_at") or "").strip() or None
    source_branch_value = _required_text(source_branch, "source_branch")
    source_sha_value = _required_text(source_sha, "source_sha")
    target_branch_value = _required_text(target_branch, "target_branch")
    target_sha_value = _required_text(target_sha, "target_sha")
    post_acquire = None
    work_branch = f"scheduler/issue{issue}-auto-dispatch"
    if completion == CONTROL_ONLY_COMPLETION_MODE:
        if source_branch_value != target_branch_value or source_sha_value != target_sha_value:
            raise SchedulerIssueCandidateError(
                "CONTROL_ONLY scheduler dispatch requires identical source/target branch and SHA at ingress"
            )
        work_branch = source_branch_value
        post_acquire = ActionSpec(
            kind="FINALIZE",
            args={"completion_mode": CONTROL_ONLY_COMPLETION_MODE},
            display="Finalize control-only scheduler work",
        )
    request = DispatchIngressRequest(
        issue=issue,
        execution_intent="SCHEDULER_LANE",
        authority_kind="USER_EXPLICIT",
        authority_ref=authority_ref,
        source_branch=source_branch_value,
        source_sha=source_sha_value,
        work_branch=work_branch,
        target_branch=target_branch_value,
        target_sha=target_sha_value,
        post_acquire=post_acquire,
        parent_issue=None,
        slot_id=None,
        created_at=created_at,
    )
    return SchedulerDispatchCandidate(
        issue=issue,
        lane=lane,
        completion=completion,
        authority_ref=authority_ref,
        ingress_request=request,
    )