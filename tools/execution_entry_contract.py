"""Canonical user-visible startup provenance/intent contract for WHD execution entries."""

from __future__ import annotations

DEFAULT_REPOSITORY = "looaeedr/whd"
SCHEMA = "WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1"


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
        )
    )


def prepend_startup_declaration(*, body: str, purpose: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """Prefix a nonblank execution body with the canonical startup declaration."""
    body = str(body).lstrip()
    if not body:
        raise ValueError("body must be nonblank")
    return f"{build_startup_declaration(purpose=purpose, repository=repository)}\n\n{body}"
