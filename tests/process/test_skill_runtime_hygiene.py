from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents/skills"


def test_skill_tree_has_no_leading_or_trailing_whitespace_components() -> None:
    from tools.skill_runtime_hygiene import trailing_whitespace_paths

    assert trailing_whitespace_paths(SKILLS) == ()


def test_context_loader_rejects_zip_and_non_text_extensions(tmp_path: Path) -> None:
    from tools.skill_runtime_hygiene import read_context_text

    archive = tmp_path / "skills.zip"
    archive.write_bytes(b"PK\\x03\\x04binary")
    with pytest.raises(ValueError, match=r"only accepts \\.md/\\.json"):
        read_context_text(archive)

    disguised = tmp_path / "skills.md"
    disguised.write_bytes(b"PK\\x03\\x04binary")
    with pytest.raises(ValueError, match="binary content"):
        read_context_text(disguised)


def test_registry_targets_active_canonical_skills_only() -> None:
    from tools.skill_runtime_hygiene import validate_registry_targets

    validate_registry_targets(repo_root=ROOT)

    registry = json.loads((SKILLS / "skill_registry.json").read_text(encoding="utf-8"))
    text = json.dumps(registry, ensure_ascii=False)
    assert ".agents/skills/in-progress/" not in text
    assert ".agents/skills/deprecated/" not in text


def test_preflight_rejects_binary_evidence_before_context_pollution(tmp_path: Path) -> None:
    from tools.phase6_skill_preflight import completed_skills_from_evidence

    archive = tmp_path / "evidence.zip"
    archive.write_bytes(b"PK\\x03\\x04binary")
    with pytest.raises(ValueError, match=r"only accepts \\.md/\\.json"):
        completed_skills_from_evidence([str(archive)])


def test_root_entry_bootstrap_requires_explicit_canonical_root_and_order() -> None:
    from tools.root_entry_bootstrap import CANONICAL_WORKING_ROOT, validate_entry_order

    work_root = json.loads((ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(encoding="utf-8"))
    root_local = json.loads((ROOT / ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json").read_text(encoding="utf-8"))

    evidence = validate_entry_order(
        working_root=CANONICAL_WORKING_ROOT,
        work_root_gate=work_root,
        root_local_gate=root_local,
    )
    assert evidence["sequence"] == [
        "WHD_WORK_ROOT_HARD_GATE_V1",
        "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1",
        "REQUESTED_OPERATION",
    ]

    with pytest.raises(ValueError, match="working root must be explicitly bound"):
        validate_entry_order(
            working_root="/mnt/data",
            work_root_gate=work_root,
            root_local_gate=root_local,
        )
