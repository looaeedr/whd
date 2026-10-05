# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import knowledge_authority_overlay_generate  # noqa: F401; installs reviewed explicit overrides
import knowledge_authority_overlay as base
from knowledge_governance import parse_doc_metadata, GovernanceError


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
            # Current declared metadata is not re-derived from ambiguous aliases.
            # Accept it only when catalog role and an exact primary registry
            # contract independently agree; never rewrite frozen T1 authority.
            try:
                metadata = parse_doc_metadata(path.read_text(encoding="utf-8"), path=rel)
                name = base._frontmatter_name(path)
                expected_role = {"canonical": "CURRENT", "reference": "REFERENCE",
                                 "upstream-beta": "REFERENCE", "tool-specific": "REFERENCE",
                                 "retired": "HISTORICAL"}.get(base._catalog_classification(rel, catalog))
                agrees = any(route.get("id") == metadata.contract and
                             route.get("required_skills", [None])[0:1] == [name]
                             for route in registry.get("routes", []))
                if metadata.role != expected_role or not agrees:
                    raise base.AuthorityOverlayError(str(exc))
            except (GovernanceError, base.AuthorityOverlayError) as metadata_exc:
                gaps.append((rel, str(metadata_exc)))
            else:
                resolved += 1
                print(f"SKILL_AUTHORITY_OK {rel} role={metadata.role} contract={metadata.contract}")
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
