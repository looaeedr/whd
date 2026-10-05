"""Canonical startup provenance/intent and communication contract for WHD execution entries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping
import re

from tools.work_root_gate import validate_work_root_gate_evidence


DEFAULT_REPOSITORY = "looaeedr/whd"
SCHEMA = "WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1"
EVIDENCE_SCHEMA = "WHD_EXECUTION_ENTRY_EVIDENCE_V1"
PREFLIGHT_EVIDENCE_SCHEMA = "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1"
REMOTE_PHASE6_RESULT_SCHEMA = "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1"
SCHEDULER_PREFLIGHT_REBIND_SCHEMA = "WHD_SCHEDULER_PHASE6_PREFLIGHT_REBIND_V1"
TRANSITION_SCHEMA = "WHD_EXECUTION_STARTUP_TRANSITION_V1"
STARTUP_COMMUNICATION_SCHEMA = "WHD_EXECUTION_STARTUP_COMMUNICATION_V1"
INTERACTIVE_CHAT_SURFACES = frozenset({"CHATGPT", "CHAT", "INTERACTIVE_CHAT"})
HEADLESS_EXECUTION_SURFACES = frozenset({"CODEX", "CODEX_CLI", "HEADLESS", "CI", "SCHEDULER"})
HEADLESS_COMMUNICATION_CHANNELS = frozenset({"STDOUT", "TASK_EVENT", "LOG"})
EVIDENCE_MAX_AGE_SECONDS = 300
SCHEDULER_PREFLIGHT_RECEIPT_MAX_AGE_SECONDS = 2400
_FUTURE_SKEW_SECONDS = 30



def build_startup_communication_evidence(
    *,
    runtime_surface: str,
    channel: str,
    declaration: str,
    skills: Iterable[str] = (),
) -> dict[str, object]:
    """Record startup/Skill communication without requiring a chat UI on headless runtimes.

    Interactive ChatGPT/chat surfaces must use USER_VISIBLE_CHAT. Codex/CLI/headless
    executors may use STDOUT, TASK_EVENT, or LOG before substantive mutation.
    """
    surface = re.sub(r"[^A-Z0-9]+", "_", str(runtime_surface or "").strip().upper()).strip("_")
    normalized_channel = re.sub(r"[^A-Z0-9]+", "_", str(channel or "").strip().upper()).strip("_")
    if not surface:
        raise ValueError("runtime_surface must be nonblank")
    if not normalized_channel:
        raise ValueError("startup communication channel must be nonblank")
    declaration_text = str(declaration or "").strip()
    if not declaration_text.startswith(SCHEMA):
        raise ValueError("startup communication requires canonical declaration")

    if surface in INTERACTIVE_CHAT_SURFACES:
        if normalized_channel != "USER_VISIBLE_CHAT":
            raise ValueError("interactive chat startup communication must be user-visible")
    elif surface in HEADLESS_EXECUTION_SURFACES:
        if normalized_channel not in HEADLESS_COMMUNICATION_CHANNELS:
            raise ValueError("headless startup communication must use STDOUT/TASK_EVENT/LOG")
    else:
        raise ValueError(f"unsupported runtime_surface: {surface}")

    skill_names = tuple(dict.fromkeys(str(item).strip() for item in skills if str(item).strip()))
    return {
        "schema": STARTUP_COMMUNICATION_SCHEMA,
        "runtime_surface": surface,
        "channel": normalized_channel,
        "user_visible": normalized_channel == "USER_VISIBLE_CHAT",
        "machine_visible": True,
        "declaration_recorded": True,
        "skills": list(skill_names),
    }


def build_startup_declaration(*, purpose: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """Render the mandatory declaration that must precede substantive execution."""
    purpose = str(purpose).strip()
    repository = str(repository).strip()
    if not purpose:
        raise ValueError("purpose must be nonblank")
    if not repository:
        raise ValueError("repository must be nonblank")
    return "\n".join(
        (
            SCHEMA,
            f"授權：此工作由使用者明確授權，針對使用者管理的 {repository} 執行。",
            f"目的：{purpose}",
            "範圍：此聲明只記錄 startup provenance/intent；不新增 repository authority，"
            "不取代 claim / Guard / Preflight，也不擴張工具權限或未被使用者要求的工作。",
            "工作根目錄閘門：WHD_WORK_ROOT_HARD_GATE_V2；repository-content 預設使用 executor-local repo workspace + cleanup/2d-3d-sync baseline；shared .unpushed 只在 fresh drift 時 fallback。",
        )
    )


def prepend_startup_declaration(*, body: str, purpose: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """Prefix a nonblank execution body with the canonical startup declaration."""
    body = str(body).lstrip()
    if not body:
        raise ValueError("body must be nonblank")
    return f"{build_startup_declaration(purpose=purpose, repository=repository)}\n\n{body}"


def _timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid startup evidence {label}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"startup evidence {label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_startup_evidence(
    *,
    purpose: str,
    invocation_identity: str,
    work_root_gate_evidence: Mapping[str, object] | object,
    execution_mode: str = "INTERACTIVE",
    repository: str = DEFAULT_REPOSITORY,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    """Build fresh machine evidence bound to one runtime invocation.

    This evidence does not prove that the host rendered the declaration visibly;
    it makes mutation ingress fail closed unless the current invocation carries
    the canonical declaration and a fresh timestamp.
    """
    invocation_identity = str(invocation_identity).strip()
    if not invocation_identity:
        raise ValueError("invocation_identity must be nonblank")
    execution_mode = str(execution_mode).strip() or "INTERACTIVE"
    root_gate = validate_work_root_gate_evidence(
        work_root_gate_evidence,
        execution_mode=execution_mode,
    )
    now = issued_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("issued_at must be timezone-aware")
    now = now.astimezone(timezone.utc)
    purpose = str(purpose).strip()
    repository = str(repository).strip()
    declaration = build_startup_declaration(purpose=purpose, repository=repository)
    return {
        "schema": EVIDENCE_SCHEMA,
        "repository": repository,
        "invocation_identity": invocation_identity,
        "execution_mode": execution_mode,
        "work_root_gate": root_gate,
        "purpose": purpose,
        "issued_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS)),
        "declaration": declaration,
    }


def validate_startup_evidence(
    evidence: Mapping[str, object] | object,
    *,
    invocation_identity: str,
    execution_mode: str | None = None,
    repository: str = DEFAULT_REPOSITORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate canonical per-invocation startup evidence for mutation ingress."""
    if not isinstance(evidence, Mapping):
        raise ValueError("startup evidence is required")
    required = {
        "schema",
        "repository",
        "invocation_identity",
        "execution_mode",
        "work_root_gate",
        "purpose",
        "issued_at",
        "expires_at",
        "declaration",
    }
    missing = sorted(required - set(evidence))
    if missing:
        raise ValueError(f"startup evidence missing fields: {missing}")
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError("unexpected startup evidence schema")

    observed_repo = str(evidence.get("repository") or "").strip()
    expected_repo = str(repository).strip()
    if observed_repo != expected_repo:
        raise ValueError("startup evidence repository mismatch")

    observed_invocation = str(evidence.get("invocation_identity") or "").strip()
    expected_invocation = str(invocation_identity).strip()
    if not expected_invocation or observed_invocation != expected_invocation:
        raise ValueError("startup evidence invocation mismatch")

    observed_execution_mode = str(evidence.get("execution_mode") or "").strip()
    if not observed_execution_mode:
        raise ValueError("startup evidence execution_mode must be nonblank")
    if execution_mode is not None:
        expected_execution_mode = str(execution_mode).strip()
        if not expected_execution_mode or observed_execution_mode != expected_execution_mode:
            raise ValueError("startup evidence execution_mode mismatch")
    validate_work_root_gate_evidence(
        evidence.get("work_root_gate"),
        execution_mode=observed_execution_mode,
    )

    purpose = str(evidence.get("purpose") or "").strip()
    if not purpose:
        raise ValueError("startup evidence purpose must be nonblank")
    expected_declaration = build_startup_declaration(
        purpose=purpose,
        repository=expected_repo,
    )
    if str(evidence.get("declaration") or "") != expected_declaration:
        raise ValueError("startup evidence declaration mismatch")

    issued_at = _timestamp(evidence.get("issued_at"), "issued_at")
    expires_at = _timestamp(evidence.get("expires_at"), "expires_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("startup evidence validation clock must be timezone-aware")
    current = current.astimezone(timezone.utc)

    if issued_at > current + timedelta(seconds=_FUTURE_SKEW_SECONDS):
        raise ValueError("startup evidence issued_at is in the future")
    if expires_at <= issued_at:
        raise ValueError("startup evidence expiry is invalid")
    if (expires_at - issued_at).total_seconds() > EVIDENCE_MAX_AGE_SECONDS:
        raise ValueError("startup evidence TTL exceeds canonical maximum")
    if current > expires_at:
        raise ValueError("startup evidence expired")

    return {str(k): v for k, v in evidence.items()}



def _positive_issue(value: object, label: str = "issue") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if number <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return number


def _sha(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a 40-character git SHA")
    return text


def _strings(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be an array")
    result: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{label} contains blank entry")
        if text not in result:
            result.append(text)
    return tuple(result)


def build_phase6_preflight_evidence(
    *,
    issue: int,
    invocation_identity: str,
    branch: str,
    head_sha: str,
    required_skills: Iterable[str],
    completed_skills: Iterable[str],
    required_references: Iterable[str],
    completed_references: Iterable[str],
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Build exact-identity Phase6 preflight evidence for one startup transition."""
    current = observed_at or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("preflight observed_at must be timezone-aware")
    required_skill_set = tuple(dict.fromkeys(str(x).strip() for x in required_skills if str(x).strip()))
    completed_skill_set = tuple(dict.fromkeys(str(x).strip() for x in completed_skills if str(x).strip()))
    required_ref_set = tuple(dict.fromkeys(str(x).strip() for x in required_references if str(x).strip()))
    completed_ref_set = tuple(dict.fromkeys(str(x).strip() for x in completed_references if str(x).strip()))
    missing_skills = sorted(set(required_skill_set) - set(completed_skill_set))
    missing_refs = sorted(set(required_ref_set) - set(completed_ref_set))
    if missing_skills or missing_refs:
        raise ValueError(f"Phase6 preflight incomplete skills={missing_skills} references={missing_refs}")
    invocation = str(invocation_identity or "").strip()
    if not invocation:
        raise ValueError("preflight invocation_identity must be nonblank")
    branch_text = str(branch or "").strip()
    if not branch_text:
        raise ValueError("preflight branch must be nonblank")
    return {
        "schema": PREFLIGHT_EVIDENCE_SCHEMA,
        "status": "GREEN",
        "issue": _positive_issue(issue),
        "invocation_identity": invocation,
        "branch": branch_text,
        "head_sha": _sha(head_sha, "preflight head_sha"),
        "required_skills": list(required_skill_set),
        "completed_skills": list(completed_skill_set),
        "required_references": list(required_ref_set),
        "completed_references": list(completed_ref_set),
        "observed_at": _iso(current.astimezone(timezone.utc)),
    }


def validate_phase6_preflight_evidence(
    evidence: Mapping[str, object] | object,
    *,
    issue: int,
    invocation_identity: str,
    now: datetime | None = None,
    max_age_seconds: int = EVIDENCE_MAX_AGE_SECONDS,
) -> dict[str, object]:
    """Validate GREEN Phase6 preflight bound to one exact Issue/branch/HEAD."""
    if not isinstance(evidence, Mapping):
        raise ValueError("Phase6 preflight evidence is required")
    if evidence.get("schema") != PREFLIGHT_EVIDENCE_SCHEMA or evidence.get("status") != "GREEN":
        raise ValueError("Phase6 preflight evidence is not canonical GREEN")
    if _positive_issue(evidence.get("issue"), "preflight issue") != _positive_issue(issue):
        raise ValueError("Phase6 preflight issue mismatch")
    expected_invocation = str(invocation_identity or "").strip()
    if not expected_invocation or str(evidence.get("invocation_identity") or "").strip() != expected_invocation:
        raise ValueError("Phase6 preflight invocation mismatch")
    branch = str(evidence.get("branch") or "").strip()
    if not branch:
        raise ValueError("Phase6 preflight branch must be nonblank")
    _sha(evidence.get("head_sha"), "Phase6 preflight head_sha")
    required_skills = _strings(evidence.get("required_skills"), "required_skills")
    completed_skills = _strings(evidence.get("completed_skills"), "completed_skills")
    required_refs = _strings(evidence.get("required_references"), "required_references")
    completed_refs = _strings(evidence.get("completed_references"), "completed_references")
    missing_skills = sorted(set(required_skills) - set(completed_skills))
    missing_refs = sorted(set(required_refs) - set(completed_refs))
    if missing_skills or missing_refs:
        raise ValueError(f"Phase6 preflight incomplete skills={missing_skills} references={missing_refs}")
    observed = _timestamp(evidence.get("observed_at"), "preflight observed_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("preflight validation clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if observed > current + timedelta(seconds=_FUTURE_SKEW_SECONDS):
        raise ValueError("Phase6 preflight observed_at is in the future")
    if isinstance(max_age_seconds, bool) or int(max_age_seconds) <= 0:
        raise ValueError("Phase6 preflight max_age_seconds must be positive")
    if current - observed > timedelta(seconds=int(max_age_seconds)):
        raise ValueError("Phase6 preflight evidence expired")
    return {str(k): v for k, v in evidence.items()}


def rebind_scheduler_phase6_preflight_receipt(
    receipt: Mapping[str, object] | object,
    *,
    issue: int,
    lane_id: str,
    invocation_identity: str,
    branch: str,
    head_sha: str,
    request_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Rebind one trusted scheduler push-Preflight GREEN to a later same-lane invocation.

    The caller must already have established that the receipt came from the trusted
    GitHub Actions comment transport. This function validates the receipt payload
    itself and never accepts interactive/comment-origin receipts.
    """
    if not isinstance(receipt, Mapping):
        raise ValueError("scheduler Phase6 receipt must be an object")
    if receipt.get("schema") != REMOTE_PHASE6_RESULT_SCHEMA or receipt.get("result") != "GREEN":
        raise ValueError("scheduler Phase6 receipt is not canonical GREEN")
    if receipt.get("request_source") != "push":
        raise ValueError("scheduler Phase6 receipt must come from push transport")
    if receipt.get("executor_source") != "scheduler":
        raise ValueError("scheduler Phase6 receipt executor_source mismatch")

    expected_lane = str(lane_id or "").strip()
    if not expected_lane.startswith("scheduler."):
        raise ValueError("scheduler Phase6 receipt requires scheduler lane")
    observed_lane = str(receipt.get("lane_id") or "").strip()
    observed_worker = str(receipt.get("worker") or "").strip()
    if observed_lane != expected_lane or observed_worker != expected_lane:
        raise ValueError("scheduler Phase6 receipt lane/worker mismatch")

    expected_request = str(request_id or "").strip()
    if not expected_request or str(receipt.get("request_id") or "").strip() != expected_request:
        raise ValueError("scheduler Phase6 receipt request_id mismatch")
    if _positive_issue(receipt.get("issue"), "scheduler receipt issue") != _positive_issue(issue):
        raise ValueError("scheduler Phase6 receipt issue mismatch")

    expected_branch = str(branch or "").strip()
    if not expected_branch or str(receipt.get("branch") or "").strip() != expected_branch:
        raise ValueError("scheduler Phase6 receipt branch mismatch")
    expected_head = _sha(head_sha, "scheduler receipt expected head_sha")
    if _sha(receipt.get("head_sha"), "scheduler receipt head_sha") != expected_head:
        raise ValueError("scheduler Phase6 receipt head mismatch")

    source_invocation = str(receipt.get("invocation_identity") or "").strip()
    if not source_invocation:
        raise ValueError("scheduler Phase6 receipt source invocation missing")
    source_evidence = receipt.get("preflight_evidence")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("scheduler Phase6 rebind clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    validated = validate_phase6_preflight_evidence(
        source_evidence,
        issue=int(issue),
        invocation_identity=source_invocation,
        now=current,
        max_age_seconds=SCHEDULER_PREFLIGHT_RECEIPT_MAX_AGE_SECONDS,
    )
    if str(validated.get("branch") or "").strip() != expected_branch:
        raise ValueError("scheduler Phase6 nested evidence branch mismatch")
    if str(validated.get("head_sha") or "").strip().lower() != expected_head:
        raise ValueError("scheduler Phase6 nested evidence head mismatch")

    current_invocation = str(invocation_identity or "").strip()
    if not current_invocation:
        raise ValueError("scheduler Phase6 current invocation must be nonblank")
    rebound = build_phase6_preflight_evidence(
        issue=int(issue),
        invocation_identity=current_invocation,
        branch=expected_branch,
        head_sha=expected_head,
        required_skills=_strings(validated.get("required_skills"), "required_skills"),
        completed_skills=_strings(validated.get("completed_skills"), "completed_skills"),
        required_references=_strings(validated.get("required_references"), "required_references"),
        completed_references=_strings(validated.get("completed_references"), "completed_references"),
        observed_at=current,
    )
    rebound["scheduler_rebind"] = {
        "schema": SCHEDULER_PREFLIGHT_REBIND_SCHEMA,
        "lane_id": expected_lane,
        "request_id": expected_request,
        "source_invocation_identity": source_invocation,
        "source_run_id": receipt.get("run_id"),
        "source_observed_at": validated.get("observed_at"),
        "max_age_seconds": SCHEDULER_PREFLIGHT_RECEIPT_MAX_AGE_SECONDS,
    }
    return rebound


def build_startup_transition(
    *,
    startup_evidence: Mapping[str, object] | object,
    preflight_evidence: Mapping[str, object] | object,
    invocation_identity: str,
    issue: int,
    execution_mode: str,
    repository: str = DEFAULT_REPOSITORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Collapse startup + exact Phase6 preflight freshness into one admission receipt."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("startup transition clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    startup = validate_startup_evidence(
        startup_evidence,
        invocation_identity=invocation_identity,
        execution_mode=execution_mode,
        repository=repository,
        now=current,
    )
    preflight = validate_phase6_preflight_evidence(
        preflight_evidence, issue=issue, invocation_identity=invocation_identity, now=current
    )
    startup_issued = _timestamp(startup["issued_at"], "issued_at")
    preflight_at = _timestamp(preflight["observed_at"], "preflight observed_at")
    startup_expires = _timestamp(startup["expires_at"], "expires_at")
    preflight_expires = preflight_at + timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS)
    expires = min(startup_expires, preflight_expires)
    if current > expires:
        raise ValueError("startup transition expired")
    return {
        "schema": TRANSITION_SCHEMA,
        "status": "READY_FOR_EXECUTION",
        "repository": str(repository).strip(),
        "invocation_identity": str(invocation_identity).strip(),
        "execution_mode": str(execution_mode).strip(),
        "issue": _positive_issue(issue),
        "branch": str(preflight["branch"]),
        "head_sha": str(preflight["head_sha"]),
        "startup_issued_at": str(startup["issued_at"]),
        "preflight_observed_at": str(preflight["observed_at"]),
        "issued_at": _iso(current),
        "expires_at": _iso(expires),
    }


def validate_startup_transition(
    transition: Mapping[str, object] | object,
    *,
    invocation_identity: str,
    issue: int,
    execution_mode: str,
    repository: str = DEFAULT_REPOSITORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate the unified transition receipt before reading/mutating execution state."""
    if not isinstance(transition, Mapping):
        raise ValueError("startup transition is required")
    if transition.get("schema") != TRANSITION_SCHEMA or transition.get("status") != "READY_FOR_EXECUTION":
        raise ValueError("startup transition is not READY_FOR_EXECUTION")
    if str(transition.get("repository") or "").strip() != str(repository).strip():
        raise ValueError("startup transition repository mismatch")
    if str(transition.get("invocation_identity") or "").strip() != str(invocation_identity).strip():
        raise ValueError("startup transition invocation mismatch")
    if str(transition.get("execution_mode") or "").strip() != str(execution_mode).strip():
        raise ValueError("startup transition execution_mode mismatch")
    if _positive_issue(transition.get("issue"), "startup transition issue") != _positive_issue(issue):
        raise ValueError("startup transition issue mismatch")
    if not str(transition.get("branch") or "").strip():
        raise ValueError("startup transition branch must be nonblank")
    _sha(transition.get("head_sha"), "startup transition head_sha")
    issued = _timestamp(transition.get("issued_at"), "transition issued_at")
    expires = _timestamp(transition.get("expires_at"), "transition expires_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("startup transition validation clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if issued > current + timedelta(seconds=_FUTURE_SKEW_SECONDS):
        raise ValueError("startup transition issued_at is in the future")
    if expires <= issued or expires - issued > timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS):
        raise ValueError("startup transition expiry is invalid")
    if current > expires:
        raise ValueError("startup transition expired")
    return {str(k): v for k, v in transition.items()}


def assert_startup_transition_matches_record(
    transition: Mapping[str, object] | object,
    *,
    issue: int,
    source_branch: str,
    source_sha: str,
    work_branch: str,
    head_sha: str,
    target_branch: str,
    target_sha: str,
) -> bool:
    """Fail closed unless preflight's exact branch/HEAD is still one live record identity."""
    if not isinstance(transition, Mapping):
        raise ValueError("startup transition is required")
    if _positive_issue(transition.get("issue"), "startup transition issue") != _positive_issue(issue):
        raise ValueError("startup transition record issue mismatch")
    observed = (str(transition.get("branch") or "").strip(), _sha(transition.get("head_sha"), "startup transition head_sha"))
    allowed = {
        (str(source_branch or "").strip(), _sha(source_sha, "record source_sha")),
        (str(work_branch or "").strip(), _sha(head_sha, "record head_sha")),
        (str(target_branch or "").strip(), _sha(target_sha, "record target_sha")),
    }
    if observed not in allowed:
        raise ValueError(
            "STARTUP_TRANSITION_STALE_IDENTITY "
            f"observed_branch={observed[0]} observed_head={observed[1]}"
        )
    return True
