# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import knowledge_authority_overlay_generate  # noqa: F401; installs reviewed explicit overrides
import knowledge_authority_overlay as base


def main() -> int:
    root = TOOLS.parent.resolve()
    registry = base._registry(root)
    catalog = base._catalog(root)
    authority = base._authority_by_path(root)
    gaps: list[tuple[str, str]] = []
    resolved = 0
    for path in sorted((root / ".agents/skills").rglob("SKILL.md")):
        rel = path.relative_to(root).as_posix()
        try:
            result = base._skill_resolution(root, rel, registry, catalog, authority)
        except base.AuthorityOverlayError as exc:
            gaps.append((rel, str(exc)))
        else:
            resolved += 1
            print(f"SKILL_AUTHORITY_OK {rel} role={result['role']} contract={result['contract']}")
    print(f"SKILL_AUTHORITY_RESOLVED {resolved}")
    print(f"SKILL_AUTHORITY_GAPS {len(gaps)}")
    for rel, reason in gaps:
        print(f"SKILL_AUTHORITY_GAP {rel} :: {reason}")
    return 2 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
