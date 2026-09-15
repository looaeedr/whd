from __future__ import annotations

import json
from pathlib import Path

from tools.permanent_knowledge_governance import validate_permanent_governance


def _doc(role: str, contract: str, body: str, canonical: str | None = None, *, name: str | None = None) -> str:
    canonical_text = "null" if canonical is None else canonical
    name_line = f"name: {name}\n" if name is not None else ""
    return (
        "---\n"
        f"{name_line}"
        f"whd_doc_role: {role}\n"
        f"whd_contract: {contract}\n"
        f"whd_canonical: {canonical_text}\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        f"{body}\n"
    )


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_repo(tmp_path: Path) -> Path:
    root = tmp_path
    _write(root, "AGENTS.md", _doc("CURRENT", "knowledge-preflight", "startup authority"))
    _write(root, "README.md", _doc("REFERENCE", "repo-navigation", "navigation only"))
    _write(
        root,
        "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md",
        _doc(
            "CURRENT",
            "pitfall-ledger",
            "<!-- WHD_AUTHORITY contract=continuous-execution-machine role=CURRENT path=tools/continuity_controller.py -->\n"
            "<!-- WHD_AUTHORITY contract=skill-routing role=CURRENT path=.agents/skills/skill_registry.json -->",
        ),
    )
    _write(root, ".agents/skills/engineering/executable-continuity-controller/SKILL.md", _doc("CURRENT", "continuous-execution-operations", "controller operations", name="executable-continuity-controller"))
    _write(root, ".agents/skills/engineering/example/SKILL.md", _doc("CURRENT", "example-skill", "example", name="example"))
    _write(root, ".agents/skills/engineering/README.md", _doc("REFERENCE", "skill-navigation", "example"))
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "tools/continuity_controller.py").write_text("def main(): return 0\n", encoding="utf-8")
    registry = {
        "routes": [{"id": "example", "required_skills": ["example"], "required_references": []}],
        "skills": [{"name": "example", "path": ".agents/skills/engineering/example/SKILL.md"}],
    }
    catalog = {"skills": [{"name": "example", "path": ".agents/skills/engineering/example/SKILL.md"}]}
    (root / ".agents/skills").mkdir(parents=True, exist_ok=True)
    (root / ".agents/skills/skill_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (root / ".agents/skills/skill_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    return root


def test_r4_readme_navigation_cannot_be_current_domain_owner(tmp_path: Path) -> None:
    root = _base_repo(tmp_path)
    _write(root, "README.md", _doc("CURRENT", "phase6-dimension-semantics", "wrong owner"))
    errors = validate_permanent_governance(root)
    assert any("README/navigation cannot own domain CURRENT" in error for error in errors)


def test_r5_continuous_execution_requires_executable_machine_owner(tmp_path: Path) -> None:
    root = _base_repo(tmp_path)
    (root / "tools/continuity_controller.py").unlink()
    errors = validate_permanent_governance(root)
    assert any("continuous-execution-machine" in error and "executable" in error for error in errors)


def test_r6_registry_catalog_filesystem_must_be_coherent(tmp_path: Path) -> None:
    root = _base_repo(tmp_path)
    catalog = {"skills": [{"name": "missing", "path": ".agents/skills/engineering/missing/SKILL.md"}]}
    (root / ".agents/skills/skill_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    errors = validate_permanent_governance(root)
    assert any("registry/catalog/filesystem coherence" in error for error in errors)


def test_r7_obsolete_wording_rejected_only_in_current_normative_docs(tmp_path: Path) -> None:
    root = _base_repo(tmp_path)
    _write(root, "docs/current.md", _doc("CURRENT", "current-contract", "Use BACKUP/ as authority."))
    _write(root, "docs/history.md", _doc("HISTORICAL", "history-contract", "Old BACKUP/ practice was removed."))
    errors = validate_permanent_governance(root)
    assert any("obsolete wording" in error and "docs/current.md" in error for error in errors)
    assert not any("obsolete wording" in error and "docs/history.md" in error for error in errors)


def test_permanent_guard_accepts_structurally_coherent_repo(tmp_path: Path) -> None:
    root = _base_repo(tmp_path)
    assert validate_permanent_governance(root) == ()
