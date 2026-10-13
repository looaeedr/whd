"""User-controlled localX publication gate for production X."""

PRODUCTION_X = "cleanup/2d-3d-sync"
INTEGRATION_BRANCH = "localX"
PUBLISH_MARKER = "WHD_LOCALX_PUBLISH_AUTH_V1"
UAT_MARKER = "WHD_WINDOWS_LOCALX_UAT_V1"


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
    acceptance, publication = [], []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user") or {}
        comment_id = comment.get("id")
        if (user.get("login") != owner or user.get("type") != "User"
                or not isinstance(comment_id, int) or comment_id <= 0):
            continue
        body = str(comment.get("body") or "")
        manual_expected = dict(expected, test_site="WINDOWS",
                               windows_head=head_sha)
        if _exact_command(body, manual_expected,
                          command="/驗收通過", marker=UAT_MARKER):
            acceptance.append(comment_id)
        if _exact_command(body, expected):
            publication.append(comment_id)
    if not acceptance:
        raise LocalXPublishDenied("WINDOWS_LOCALX_MANUAL_UAT_REQUIRED")
    if not publication:
        raise LocalXPublishDenied("LOCALX_PUBLISH_REQUIRES_EXPLICIT_USER_SLASH_PUSH")
    if not any(a < p for a in acceptance for p in publication):
        raise LocalXPublishDenied("WINDOWS_UAT_MUST_PRECEDE_SLASH_PUSH")


class LocalXIntegrationDenied(ValueError):
    """A conversation BUG fix has not proved same-task localX integration authority."""


def require_conversational_bugfix_localx_integration(
    *, authorization: dict, delivery: dict,
) -> None:
    """Validate scoped continuation to DC LOCALX_INTEGRATION, never X publish.

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
        authorization.get("github_only") is True
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
