from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/knowledge_governance.py"
INVENTORY = ROOT / "docs/superpowers/verification/knowledge_governance_inventory_v1.json"
CURRENT_API = ROOT / "docs/superpowers/CURRENT_API_INVENTORY_20260818.md"


def _load_governance():
    spec = importlib.util.spec_from_file_location("knowledge_governance_t6", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _governed_paths(governance) -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*.md"):
        rel = path.relative_to(ROOT).as_posix()
        if governance.is_governed_markdown(rel):
            paths.append(path)
    return sorted(paths)


def _doc(role: str, contract: str, canonical: str | None, body: str) -> str:
    canonical_value = "null" if canonical is None else canonical
    return (
        "---\n"
        f"whd_doc_role: {role}\n"
        f"whd_contract: {contract}\n"
        f"whd_canonical: {canonical_value}\n"
        "whd_schema: WHD_DOC_META_V1\n"
        "---\n"
        f"{body}"
    )


def test_issue1155_retired_execution_docs_are_deleted_and_live_handoff_keeps_metadata() -> None:
    retired = (
        "UPDATE/AGENTS.md",
        "docs/governance/whd_scheduler_takeover_usage.md",
        "docs/specs/WHD_排程_GuardTransaction_DelegatedHelper_StaleTakeover_硬閘門規格_2026-09-25.md",
    )
    for rel in retired:
        assert not (ROOT / rel).exists(), f"retired execution artifact regrew: {rel}"

    governance = _load_governance()
    rel = "handoff/00_AI_HANDOFF_README.md"
    path = ROOT / rel
    metadata = governance.parse_doc_metadata(path.read_text(encoding="utf-8"), path=rel)
    assert metadata.role in {"HISTORICAL", "MIRROR"}


def test_frozen_inventory_is_bootstrap_evidence_not_runtime_authority() -> None:
    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert payload["snapshot_role"] == "BOOTSTRAP_FREEZE_BASELINE"
    assert payload["runtime_authority"] is False
    assert payload["source_head"] != "3487d6392dc78f35aa1105d90e8ccc210272a2b0"


def test_strict_validator_still_fails_closed_on_missing_metadata(tmp_path: Path) -> None:
    governance = _load_governance()
    (tmp_path / "README.md").write_text("# missing metadata\n", encoding="utf-8")
    errors = governance.validate_strict(tmp_path)
    assert errors
    assert any("README.md" in error and "WHD_DOC_META_V1" in error for error in errors)


def test_strict_validator_accepts_pointer_and_flow_v2_bridge_mirrors(tmp_path: Path) -> None:
    governance = _load_governance()
    flow = tmp_path / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    flow.parent.mkdir(parents=True)
    flow.write_text(_doc("CURRENT", "flow-v2-execution", None, "# Flow v2\n"), encoding="utf-8")

    pointer = tmp_path / "README.md"
    pointer.write_text(
        _doc(
            "MIRROR",
            "flow-v2-execution",
            ".agents/skills/engineering/flow-v2-execution/SKILL.md",
            "# Mirror\nCanonical: `.agents/skills/engineering/flow-v2-execution/SKILL.md`\n"
            "本檔僅為相容入口。\n不得新增或複製 normative 規則。\n",
        ),
        encoding="utf-8",
    )

    bridge = tmp_path / ".agents/skills/engineering/bridge/SKILL.md"
    bridge.parent.mkdir(parents=True)
    bridge.write_text(
        _doc(
            "MIRROR",
            "flow-v2-execution",
            ".agents/skills/engineering/flow-v2-execution/SKILL.md",
            "# Bridge\n<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->\n"
            "canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md\n"
            "本 Skill 是入口 bridge，不擁有 execution state machine。\n",
        ),
        encoding="utf-8",
    )
    assert governance.validate_strict(tmp_path) == ()


def test_current_named_api_snapshot_is_structurally_historical() -> None:
    governance = _load_governance()
    text = CURRENT_API.read_text(encoding="utf-8")
    metadata = governance.parse_doc_metadata(text, path=CURRENT_API.relative_to(ROOT).as_posix())
    assert metadata.role == "HISTORICAL"
    assert metadata.contract == "api-inventory"
    assert "不參與 current routing" in text[:1600]
