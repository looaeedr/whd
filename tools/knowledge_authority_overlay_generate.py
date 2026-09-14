# -*- coding: utf-8 -*-
"""Generate #255 overlay with explicit, reviewed content-evidence exceptions.

This wrapper intentionally keeps exceptions visible and reviewable instead of
teaching the generic overlay resolver to guess contracts from filenames.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import knowledge_authority_overlay as base


EXPLICIT_SKILL_CONTRACTS: dict[str, tuple[str, str]] = {
    "執行開發任務": (
        "development-task-execution",
        "skill-content:依已核准規格或工單執行實作，負責實作者階段/TDD/targeted validation/durable checkpoint",
    ),
    "寫成規格書": (
        "grounded-spec-authoring",
        "skill-content:將已確認需求與current codebase/AI Library/spec/tests/certified data grounding整理成可施工規格，禁止test/probe反推產品真值",
    ),
    "拆解任務工單": (
        "requirement-red-ticket-decomposition",
        "skill-content:以approved requirement-level RED證明需求後，依root contract拆成可實作tickets並保留authority/AI Library/owning issue/closing ownership",
    ),
    "拷問邊建立文件": (
        "inquiry-driven-domain-documentation",
        "skill-content:source-first深度質詢design frontier，並在決策settle時同步維護CONTEXT/ADR durable domain docs",
    ),
    "程式碼庫設計": (
        "deep-module-codebase-design",
        "skill-content:定義deep module/interface/seam/adapter/leverage/locality vocabulary與testability設計原則",
    ),
    "領域建模": (
        "domain-modeling",
        "skill-content:建立與磨利domain model/canonical terminology，settle後同步CONTEXT glossary與符合gate的ADR",
    ),
    "深度質詢": (
        "deep-design-inquiry",
        "skill-content:source-first建立design tree並逐輪處理可決策frontier，facts由執行者查證、decisions由使用者定案",
    ),
}

_original_skill_resolution = base._skill_resolution


def _explicit_skill_resolution(root, rel, registry, catalog, authority):
    try:
        return _original_skill_resolution(root, rel, registry, catalog, authority)
    except base.AuthorityOverlayError as exc:
        name = base._frontmatter_name(root / rel)
        explicit = EXPLICIT_SKILL_CONTRACTS.get(name or "")
        if explicit is None:
            raise
        classification = base._catalog_classification(rel, catalog)
        role_by_class = {
            "canonical": "CURRENT",
            "reference": "REFERENCE",
            "upstream-beta": "REFERENCE",
            "tool-specific": "REFERENCE",
            "retired": "HISTORICAL",
        }
        role = role_by_class.get(str(classification))
        if role is None:
            raise base.AuthorityOverlayError(
                f"{rel}: explicit contract exists but catalog classification is unresolved"
            ) from exc
        contract, evidence = explicit
        return {
            "role": role,
            "contract": contract,
            "canonical": None,
            "evidence": [
                f"skill-catalog:{classification}",
                f"skill-frontmatter:name={name}",
                evidence,
                "issue255:reviewed-explicit-skill-contract",
            ],
        }


base._skill_resolution = _explicit_skill_resolution


if __name__ == "__main__":
    raise SystemExit(base.main())
