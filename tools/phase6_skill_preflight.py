"""main/default-branch fail-closed preflight tombstone.

CURRENT implementation lives on cleanup/2d-3d-sync.
"""
from __future__ import annotations

MARKER = "MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V2"
PRODUCTION_BRANCH = "cleanup/2d-3d-sync"


class MainDefaultBranchFailClosed(RuntimeError):
    pass


def _fail() -> None:
    raise MainDefaultBranchFailClosed(
        f"{MARKER}: bind Skill Preflight to live {PRODUCTION_BRANCH} explicitly"
    )


def required_skills_for(*args, **kwargs):
    _fail()


def main() -> int:
    _fail()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
