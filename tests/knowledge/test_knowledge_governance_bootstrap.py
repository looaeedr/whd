from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "knowledge_governance.py"
BOOTSTRAP_WORKFLOW = ROOT / ".github/workflows/knowledge-governance-bootstrap.yml"
INVENTORY = ROOT / "docs/superpowers/verification/knowledge_governance_inventory_v1.json"


def _load_governance():
    assert TOOL.is_file(), "T0 requires executable tools/knowledge_governance.py"
    spec = importlib.util.spec_from_file_location("knowledge_governance", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_doc(contract: str) -> str:
    return (
        "---\n"
        "whd_doc_role: CURRENT\n"
        f"whd_contract: {contract}\n"
        "whd_canonical: null\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        "# Current\n"
    )


def _reference_doc(contract: str) -> str:
    return (
        "---\n"
        "whd_doc_role: REFERENCE\n"
        f"whd_contract: {contract}\n"
        "whd_canonical: null\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        "# Reference\n"
    )


def test_metadata_parser_accepts_flat_whd_doc_meta_and_rejects_invalid_role() -> None:
    governance = _load_governance()
    metadata = governance.parse_doc_metadata(_current_doc("sample-contract"), path="docs/current.md")
    assert metadata.role == "CURRENT"
    assert metadata.contract == "sample-contract"
    assert metadata.canonical is None
    assert metadata.schema == "WHD_DOC_META_V1"

    invalid = _current_doc("sample-contract").replace("CURRENT", "UNKNOWN", 1)
    with pytest.raises(governance.GovernanceError, match="whd_doc_role"):
        governance.parse_doc_metadata(invalid, path="docs/invalid.md")


def test_metadata_parser_requires_kebab_contract_and_mirror_canonical() -> None:
    governance = _load_governance()
    bad_contract = _current_doc("T0_bad_contract")
    with pytest.raises(governance.GovernanceError, match="whd_contract"):
        governance.parse_doc_metadata(bad_contract, path="docs/bad.md")

    mirror = (
        "---\n"
        "whd_doc_role: MIRROR\n"
        "whd_contract: sample-contract\n"
        "whd_canonical: null\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        "# Mirror\n"
    )
    with pytest.raises(governance.GovernanceError, match="whd_canonical"):
        governance.parse_doc_metadata(mirror, path="docs/mirror.md")


def test_bootstrap_grandfathers_frozen_legacy_but_rejects_post_freeze_edits(tmp_path: Path) -> None:
    governance = _load_governance()
    legacy = tmp_path / "docs" / "legacy.md"
    legacy.parent.mkdir(parents=True)
    frozen_text = "# legacy without metadata\n"
    legacy.write_text(frozen_text, encoding="utf-8")
    inventory = {
        "schema": "WHD_KNOWLEDGE_INVENTORY_V1",
        "rows": [
            {
                "path": "docs/legacy.md",
                "role": "UNKNOWN",
                "contract": None,
                "canonical_owner": None,
                "incoming_references": [],
                "machine_routing": [],
                "replacement": None,
                "action": "UPDATE",
                "metadata_status": "legacy-or-unclassified",
                "content_sha256": _sha256(frozen_text),
            }
        ],
    }

    # A PR may have been opened from a base older than the T0 freeze. If the
    # current legacy content still matches the frozen inventory, bootstrap mode
    # must not misclassify it as new drift merely because PR-base diff lists it.
    assert governance.validate_bootstrap(
        tmp_path, inventory, changed_files=["docs/legacy.md"]
    ) == ()

    legacy.write_text(frozen_text + "post-freeze change\n", encoding="utf-8")
    errors = governance.validate_bootstrap(tmp_path, inventory, changed_files=["docs/legacy.md"])
    assert any("WHD_DOC_META_V1" in error for error in errors)


def test_bootstrap_rejects_new_second_current_but_allows_atomic_authority_transfer(tmp_path: Path) -> None:
    governance = _load_governance()
    docs = tmp_path / "docs"
    docs.mkdir()
    old_text = _current_doc("sample-contract")
    old_owner = docs / "old.md"
    new_owner = docs / "new.md"
    old_owner.write_text(old_text, encoding="utf-8")
    new_owner.write_text(_current_doc("sample-contract"), encoding="utf-8")
    inventory = {
        "schema": "WHD_KNOWLEDGE_INVENTORY_V1",
        "rows": [
            {
                "path": "docs/old.md",
                "role": "CURRENT",
                "contract": "sample-contract",
                "canonical_owner": "docs/old.md",
                "incoming_references": [],
                "machine_routing": [],
                "replacement": None,
                "action": "KEEP",
                "metadata_status": "v1",
                "content_sha256": _sha256(old_text),
            }
        ],
    }

    errors = governance.validate_bootstrap(tmp_path, inventory, changed_files=["docs/new.md"])
    assert any("multiple CURRENT" in error for error in errors)

    old_owner.write_text(_reference_doc("sample-contract"), encoding="utf-8")
    assert governance.validate_bootstrap(
        tmp_path,
        inventory,
        changed_files=["docs/old.md", "docs/new.md"],
    ) == ()


def test_bootstrap_rejects_mirror_with_missing_canonical_target(tmp_path: Path) -> None:
    governance = _load_governance()
    docs = tmp_path / "docs"
    docs.mkdir()
    mirror = docs / "mirror.md"
    mirror.write_text(
        "---\n"
        "whd_doc_role: MIRROR\n"
        "whd_contract: sample-contract\n"
        "whd_canonical: docs/missing.md\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        "# Mirror\n",
        encoding="utf-8",
    )
    inventory = {"schema": "WHD_KNOWLEDGE_INVENTORY_V1", "rows": []}
    errors = governance.validate_bootstrap(tmp_path, inventory, changed_files=["docs/mirror.md"])
    assert any("canonical target does not exist" in error for error in errors)


def test_inventory_covers_required_scopes_and_records_required_fields(tmp_path: Path) -> None:
    governance = _load_governance()
    files = {
        "AGENTS.md": _current_doc("agent-startup-process"),
        "README.md": _reference_doc("repo-overview"),
        "AI_HANDOFF.md": _reference_doc("handoff-ledger"),
        "個人AI檔案庫/README.md": _reference_doc("ai-library-navigation"),
        ".agents/skills/engineering/demo/SKILL.md": _current_doc("demo-skill"),
        "docs/superpowers/specs/demo.md": _reference_doc("demo-spec"),
        "handoff/demo.md": _reference_doc("demo-handoff"),
    }
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (tmp_path / ".agents/skills/skill_registry.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agents/skills/skill_registry.json").write_text(
        '{"schema_version": 1, "routes": []}', encoding="utf-8"
    )

    inventory = governance.build_inventory(tmp_path, source_head="fixture-head")
    rows = {row["path"]: row for row in inventory["rows"]}
    assert set(files) <= set(rows)
    required = {
        "path",
        "role",
        "contract",
        "canonical_owner",
        "incoming_references",
        "machine_routing",
        "replacement",
        "action",
        "content_sha256",
    }
    assert all(required <= set(row) for row in rows.values())
    assert inventory["source_head"] == "fixture-head"


def test_permanent_bootstrap_workflow_invokes_governance_against_pr_base() -> None:
    assert BOOTSTRAP_WORKFLOW.is_file(), "T0 requires permanent knowledge-governance-bootstrap.yml"
    text = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "cleanup/2d-3d-sync" in text
    assert "tools/knowledge_governance.py bootstrap" in text
    assert "docs/superpowers/verification/knowledge_governance_inventory_v1.json" in text
    assert "github.event.pull_request.base.sha" in text
    assert "fetch-depth: 0" in text


def test_frozen_inventory_file_exists_and_names_its_source_head() -> None:
    assert INVENTORY.is_file(), "T0 requires a committed frozen governance inventory"
    text = INVENTORY.read_text(encoding="utf-8")
    assert '"schema": "WHD_KNOWLEDGE_INVENTORY_V1"' in text
    assert '"source_head":' in text
    assert '"content_sha256":' in text
