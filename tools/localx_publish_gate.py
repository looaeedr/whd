"""User-controlled localX publication gate for production X."""

PRODUCTION_X = "cleanup/2d-3d-sync"
INTEGRATION_BRANCH = "localX"
PUBLISH_MARKER = "WHD_LOCALX_PUBLISH_AUTH_V1"


class LocalXPublishDenied(ValueError):
    """Publication lacks explicit user authorization."""

def _exact_command(body: str, expected: dict[str, str]) -> bool:
    """Reject substring matches, duplicate fields, and replayed HEADs."""
    lines = body.strip().splitlines()
    if len(lines) != len(expected) + 2:
        return False
    if [part.strip() for part in lines[:2]] != ["/推推", PUBLISH_MARKER]:
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
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user") or {}
        if (
            user.get("login") == owner
            and user.get("type") == "User"
            and _exact_command(str(comment.get("body") or ""), expected)
        ):
            return
    raise LocalXPublishDenied("LOCALX_PUBLISH_REQUIRES_EXPLICIT_USER_SLASH_PUSH")
