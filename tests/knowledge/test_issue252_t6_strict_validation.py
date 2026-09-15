from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = ROOT / "tools/knowledge_governance.py"
MATRIX = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"
OVERLAY = ROOT / "docs/superpowers/verification/knowledge_authority_resolution_overlay_v1.json"


def _load_governance():
    spec = importlib.util.spec_from_file_location("knowledge_governance_issue252", GOVERNANCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc(role: str, contract: str, canonical: str | None, body: str, **extra: str) -> str:
    canonical_value = "null" if canonical is None else canonical
    extra_lines = "".join(f"{key}: {value}\n" for key, value in extra.items())
    return (
        "---\n"
        f"whd_doc_role: {role}\n"
        f"whd_contract: {contract}\n"
        f"whd_canonical: {canonical_value}\n"
        "whd_schema: WHD_DOC_META_V1\n"
        f"{extra_lines}"
        "---\n"
        f"{body}"
    )


def test_exact_governed_set_matches_effective_authority_and_strict_validation() -> None:
    governance = _load_governance()
    from tools.knowledge_authority_overlay import governed_paths, merge_effective_authority

    governed = set(governed_paths(ROOT))
    effective = tuple(merge_effective_authority(MATRIX, OVERLAY))
    effective_paths = {str(row["path"]) for row in effective}

    # T6's reviewed authority remains a frozen 398-path migration snapshot. Later
    # governed documents are valid only if current strict governance accepts them;
    # they must not be retroactively inserted into the frozen matrix/overlay.
    assert len(effective_paths) == 398
    assert effective_paths <= governed
    post_t6_paths = governed - effective_paths
    assert "個人AI檔案庫/踩坑庫/execution_claim_hard_gate_pitfall.md" in post_t6_paths
    assert hasattr(governance, "validate_strict")
    assert governance.validate_strict(ROOT) == ()


def test_strict_rejects_non_pointer_only_mirror(tmp_path: Path) -> None:
    governance = _load_governance()
    (tmp_path / "canonical.txt").write_text("canonical\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        _doc(
            "MIRROR",
            "mirror-test",
            "canonical.txt",
            "# Mirror\n\nCanonical: `canonical.txt`\n\n"
            "本檔僅為相容入口。\n"
            "不得新增或複製 normative 規則。\n"
            "extra normative-looking copied line\n"
            "another copied line\n",
        ),
        encoding="utf-8",
    )

    errors = governance.validate_strict(tmp_path)
    assert any("README.md" in error and "pointer-only" in error for error in errors)


def test_strict_rejects_historical_document_in_machine_routing(tmp_path: Path) -> None:
    governance = _load_governance()
    skill = tmp_path / ".agents/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        _doc(
            "HISTORICAL",
            "historical-example",
            None,
            "# Old Skill\n",
            name="example-skill",
        ),
        encoding="utf-8",
    )
    registry = tmp_path / ".agents/skills/skill_registry.json"
    registry.write_text(
        json.dumps(
            {
                "routes": [
                    {
                        "id": "example-route",
                        "required_skills": ["example-skill"],
                        "required_references": [],
                        "file_globs": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    errors = governance.validate_strict(tmp_path)
    assert any("SKILL.md" in error and "HISTORICAL" in error and "routing" in error for error in errors)


def test_strict_rejects_dual_current_owner(tmp_path: Path) -> None:
    governance = _load_governance()
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text(
        _doc("CURRENT", "same-contract", None, "# Root\n"), encoding="utf-8"
    )
    (docs / "owner.md").write_text(
        _doc("CURRENT", "same-contract", None, "# Other\n"), encoding="utf-8"
    )

    errors = governance.validate_strict(tmp_path)
    assert any("same-contract" in error and "multiple CURRENT" in error for error in errors)
