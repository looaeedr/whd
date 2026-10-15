"""User-controlled localX publication gate for production X."""

PRODUCTION_X = "cleanup/2d-3d-sync"
INTEGRATION_BRANCH = "localX"
PUBLISH_MARKER = "WHD_LOCALX_PUBLISH_AUTH_V1"
UAT_MARKER = "WHD_WINDOWS_LOCALX_UAT_V1"  # Historical/optional record, not a release prerequisite


class LocalXPublishDenied(ValueError):
    """Publication lacks explicit user authorization."""

def _exact_command(body: str, expected: dict[str, str], *, command="/推推", marker=PUBLISH_MARKER) -> bool:
    """Reject substring matches, duplicate fields, and replayed HEADs."""
    lines = body.strip().splitlines()
    if len(lines) != len(expected) + 2:
        return False
    if [part.strip() for part in lines[:2]] != [command, marker]:
        return False
    fields: dict[str, str] = {}
    for line in lines[2:]:
        if line.count("=") != 1:
            return False
        key, value = (piece.strip() for piece in line.split("=", 1))
        if not key or key in fields or not value:
            return False
        fields[key] = value
    return fields == expected


def require_publish_approval(
    *,
    repo: str,
    pr_number: int,
    pr: dict,
    head_sha: str,
    target_sha: str,
    comments: list,
) -> None:
    """Require exact owner-issued /推推 proof before any production X merge.

    This validates a GitHub-owned comment transport; it does not claim that
    an external ChatGPT user-turn signature is available.
    """
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    if (
        head.get("ref") != INTEGRATION_BRANCH
        or head.get("sha") != head_sha
        or base.get("ref") != PRODUCTION_X
        or base.get("sha") != target_sha
    ):
        raise LocalXPublishDenied("LOCALX_PUBLISH_REQUIRES_EXACT_LOCALX_PR")
    expected = {
        "repo": repo,
        "pr": str(pr_number),
        "source": INTEGRATION_BRANCH,
        "head": head_sha,
        "target": PRODUCTION_X,
        "base": target_sha,
    }
    owner = repo.split("/", 1)[0]
    publication = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user") or {}
        comment_id = comment.get("id")
        if (user.get("login") != owner or user.get("type") != "User"
                or not isinstance(comment_id, int) or comment_id <= 0):
            continue
        body = str(comment.get("body") or "")
        if _exact_command(body, expected):
            publication.append(comment_id)
    # User's exact /推推 is both acceptance of the release candidate
    # and the authorization to publish. Never claim a Windows test was run.
    if not publication:
        raise LocalXPublishDenied("LOCALX_PUBLISH_REQUIRES_EXPLICIT_USER_SLASH_PUSH")


class LocalXIntegrationDenied(ValueError):
    """A conversation BUG fix has not proved same-task localX integration authority."""


def require_conversational_bugfix_localx_integration(
    *, authorization: dict, delivery: dict,
) -> None:
    """Validate explicitly authorized DC continuation only, never X publish.

    The caller must source authorization from the authenticated user
    conversation and delivery from fresh GitHub PR/CI readback. Untrusted
    JSON cannot authenticate either source on its own. No DC call belongs
    before this verification. A discussion of a BUG is not execution intent.
    """
    import re

    if not isinstance(authorization, dict) or not isinstance(delivery, dict):
        raise LocalXIntegrationDenied("UNVERIFIED_CONVERSATION_OR_DELIVERY")
    if (
        authorization.get("source") != "AUTHENTICATED_USER_CONVERSATION"
        or authorization.get("intent") != "EXECUTE_BUGFIX"
        or not isinstance(authorization.get("instruction_id"), str)
        or not authorization["instruction_id"].strip()
        or not isinstance(authorization.get("scope"), str)
        or not authorization["scope"].strip()
        or authorization.get("repo") != "looaeedr/whd"
    ):
        raise LocalXIntegrationDenied("NO_EXPLICIT_CONVERSATION_BUGFIX_AUTH")
    if (
        authorization.get("dc_explicitly_authorized") is not True
        or authorization.get("github_only") is True
        or authorization.get("dc_forbidden") is True
        or authorization.get("revoked") is True
    ):
        raise LocalXIntegrationDenied("CONVERSATION_DC_SCOPE_EXCLUDED")
    if (
        delivery.get("repo") != authorization["repo"]
        or delivery.get("scope") != authorization["scope"]
        or delivery.get("stage") != "LOCALX_INTEGRATION"
        or delivery.get("pr_base") != INTEGRATION_BRANCH
        or delivery.get("ci_conclusion") != "SUCCESS"
        or delivery.get("required_tests_complete") is not True
    ):
        raise LocalXIntegrationDenied("LOCALX_SCOPE_OR_CI_NOT_VERIFIED")
    sha = delivery.get("head_sha")
    if (
        not isinstance(sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", sha)
        or delivery.get("ci_head_sha") != sha
        or not isinstance(delivery.get("work_branch"), str)
        or not delivery["work_branch"].strip()
        or delivery["work_branch"] in (INTEGRATION_BRANCH, PRODUCTION_X)
    ):
        raise LocalXIntegrationDenied("LOCALX_EXACT_HEAD_REQUIRED")


def require_github_localx_integration(*, authorization: dict, delivery: dict) -> None:
    """Validate authorized same-scope GitHub localX merge, never DC or X.

    Calling code must verify authentic conversation authority and exact GH
    PR/CI readback; supplying dicts does not authenticate the claimed source.
    """
    import re

    if not isinstance(authorization, dict) or not isinstance(delivery, dict):
        raise LocalXIntegrationDenied("UNVERIFIED_CONVERSATION_OR_DELIVERY")
    if (
        authorization.get("source") != "AUTHENTICATED_USER_CONVERSATION"
        or authorization.get("intent") not in ("EXECUTE_BUGFIX", "DISPATCH_ISSUE")
        or not isinstance(authorization.get("instruction_id"), str)
        or not authorization["instruction_id"].strip()
        or not isinstance(authorization.get("scope"), str)
        or not authorization["scope"].strip()
        or authorization.get("repo") != "looaeedr/whd"
        or authorization.get("revoked") is True
        or authorization.get("localx_merge_forbidden") is True
    ):
        raise LocalXIntegrationDenied("NO_SCOPED_GITHUB_LOCALX_AUTH")
    if (
        delivery.get("repo") != authorization["repo"]
        or delivery.get("scope") != authorization["scope"]
        or delivery.get("stage") != "LOCALX_INTEGRATION"
        or delivery.get("pr_base") != INTEGRATION_BRANCH
        or delivery.get("ci_conclusion") != "SUCCESS"
        or delivery.get("required_tests_complete") is not True
        or delivery.get("mergeable") is not True
        or delivery.get("base_change_impact_checked") is not True
    ):
        raise LocalXIntegrationDenied("GITHUB_LOCALX_SCOPE_OR_CI_NOT_VERIFIED")
    sha = delivery.get("head_sha")
    if (
        not isinstance(sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", sha)
        or delivery.get("ci_head_sha") != sha
        or not isinstance(delivery.get("work_branch"), str)
        or not delivery["work_branch"].strip()
        or delivery["work_branch"] in (INTEGRATION_BRANCH, PRODUCTION_X)
    ):
        raise LocalXIntegrationDenied("GITHUB_LOCALX_EXACT_HEAD_REQUIRED")


class OfficialReleaseDenied(ValueError):
    """GitHub Release is not the verified final /推推 delivery step."""


def official_release_tag(merge_sha: str, merged_at: str) -> str:
    """Stable, Taiwan-local release version bound to the exact X merge SHA.

    version.txt is intentionally ignored; do not commit, rewrite or use it.
    """
    import re
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if not isinstance(merge_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_INVALID_X_SHA")
    if not isinstance(merged_at, str):
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_MISSING_MERGE_TIME")
    try:
        instant = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("timestamp must have an offset")
        taipei = instant.astimezone(ZoneInfo("Asia/Taipei"))
    except (ValueError, TypeError, KeyError) as exc:
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_INVALID_MERGE_TIME") from exc
    return f"v{taipei:%Y.%m.%d}-x-{merge_sha[:12]}"


def require_official_release_proof(
    *, repo: str, pushed_sha: str, production_sha: str,
    pr: dict, merge_parents: list[str], comments: list,
) -> str:
    """Authorize a release *after* X equals GitHub localX.

    PR's mutable branch ref SHAs are not evidence after merge. The two
    immutable merge parents recover the exact source head and X base used
    by the original owner-issued /推推 approval.
    """
    import re

    if (repo != "looaeedr/whd"
            or not isinstance(pushed_sha, str)
            or not re.fullmatch(r"[0-9a-f]{40}", pushed_sha)
            or pushed_sha != production_sha):
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_REQUIRES_GITHUB_X_LOCALX_SYNC")
    if not isinstance(pr, dict) or pr.get("merged") is not True:
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_REQUIRES_MERGED_PR")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    if (pr.get("merge_commit_sha") != pushed_sha
            or head.get("ref") != INTEGRATION_BRANCH
            or base.get("ref") != PRODUCTION_X
            or (head.get("repo") or {}).get("full_name") != repo
            or (base.get("repo") or {}).get("full_name") != repo):
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_NOT_LOCALX_TO_X")
    if (not isinstance(merge_parents, list) or len(merge_parents) != 2
            or any(not isinstance(x, str)
                   or not re.fullmatch(r"[0-9a-f]{40}", x)
                   for x in merge_parents)):
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_REQUIRES_TWO_PARENT_MERGE")
    number = pr.get("number")
    if not isinstance(number, int) or number <= 0:
        raise OfficialReleaseDenied("OFFICIAL_RELEASE_INVALID_PR")
    before_x, before_localx = merge_parents
    require_publish_approval(
        repo=repo, pr_number=number,
        pr={"head": {"ref": INTEGRATION_BRANCH, "sha": before_localx},
            "base": {"ref": PRODUCTION_X, "sha": before_x}},
        head_sha=before_localx, target_sha=before_x, comments=comments,
    )
    return official_release_tag(pushed_sha, pr.get("merged_at"))
