from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "knowledge_governance.py"


def _load_governance():
    spec = importlib.util.spec_from_file_location("knowledge_governance", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    path: str,
    *,
    role: str = "UNKNOWN",
    contract: str | None = None,
    canonical_owner: str | None = None,
    incoming: list[str] | None = None,
    routing: list[str] | None = None,
) -> dict[str, object]:
    return {
        "path": path,
        "role": role,
        "contract": contract,
        "canonical_owner": canonical_owner,
        "incoming_references": incoming or [],
        "machine_routing": routing or [],
        "replacement": None,
        "action": "UPDATE",
        "metadata_status": "legacy-or-unclassified",
        "content_sha256": "0" * 64,
    }


def _inventory(*rows: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "WHD_KNOWLEDGE_INVENTORY_V1",
        "source_head": "fixture-head",
        "rows": list(rows),
    }


def _authority_map(root: Path, *rows: str) -> None:
    path = root / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"<!-- WHD_AUTHORITY_ROW {row} -->" for row in rows) + "\n", encoding="utf-8")


def test_classification_uses_explicit_authority_and_only_safe_path_policies(tmp_path: Path) -> None:
    governance = _load_governance()
    _authority_map(
        tmp_path,
        "contract=agent-startup-process role=CURRENT path=AGENTS.md",
    )
    inventory = _inventory(
        _row("AGENTS.md", role="CURRENT", contract="agent-startup-process", canonical_owner="AGENTS.md"),
        _row("docs/superpowers/plans/old-plan.md"),
        _row(".agents/skills/engineering/README.md"),
        _row("個人AI檔案庫/踩坑庫/old_incident.md"),
        _row(".agents/skills/engineering/demo/SKILL.md", routing=["demo-route"]),
        _row("個人AI檔案庫/第二層_專案與SOP/ambiguous.md", routing=["active-route"]),
    )

    matrix = governance.build_classification_matrix(tmp_path, inventory)
    rows = {row["path"]: row for row in matrix["rows"]}

    assert rows["AGENTS.md"]["target_role"] == "CURRENT"
    assert rows["docs/superpowers/plans/old-plan.md"]["target_role"] == "HISTORICAL"
    assert rows[".agents/skills/engineering/README.md"]["target_role"] == "REFERENCE"
    assert rows["個人AI檔案庫/踩坑庫/old_incident.md"]["target_role"] == "REFERENCE"
    assert rows[".agents/skills/engineering/demo/SKILL.md"]["target_role"] == "CURRENT"
    assert rows[".agents/skills/engineering/demo/SKILL.md"]["blocker"] == "MISSING_STABLE_CONTRACT"
    assert rows["個人AI檔案庫/第二層_專案與SOP/ambiguous.md"]["target_role"] == "UNRESOLVED"
    assert rows["個人AI檔案庫/第二層_專案與SOP/ambiguous.md"]["blocker"] == "ROLE_REQUIRES_AUTHORITY_REVIEW"


def test_conflict_matrix_enumerates_required_conflict_classes_with_exact_paths(tmp_path: Path) -> None:
    governance = _load_governance()
    inventory = _inventory(
        _row("docs/a.md", role="CURRENT", contract="sample-contract", canonical_owner="docs/a.md"),
        _row("docs/b.md", role="CURRENT", contract="sample-contract", canonical_owner="docs/a.md"),
        _row("docs/orphan.md", role="CURRENT", contract=None),
        _row("docs/superpowers/CURRENT_API_20200101.md", routing=["stale-route"]),
        _row("個人AI檔案庫/第二層_專案與SOP/unknown-active.md", routing=["active-route"]),
    )

    matrix = governance.build_classification_matrix(tmp_path, inventory)
    conflicts = matrix["conflicts"]
    codes = {conflict["code"] for conflict in conflicts}

    assert {"DUAL_CURRENT", "ORPHAN_CURRENT", "UNKNOWN_ACTIVE", "STALE_ROUTE", "MISLEADING_CURRENT_NAME"} <= codes
    dual = next(conflict for conflict in conflicts if conflict["code"] == "DUAL_CURRENT")
    assert dual["contract"] == "sample-contract"
    assert dual["paths"] == ["docs/a.md", "docs/b.md"]
    assert dual["proposed_current_owner"] == "docs/a.md"


def test_authority_map_can_propose_non_markdown_current_owner(tmp_path: Path) -> None:
    governance = _load_governance()
    _authority_map(
        tmp_path,
        "contract=continuous-execution-machine role=CURRENT path=tools/continuity_controller.py",
        "contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
    )
    inventory = _inventory(
        _row(
            "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
            role="REFERENCE",
            contract="pitfall-ledger",
        )
    )

    matrix = governance.build_classification_matrix(tmp_path, inventory)
    contracts = {row["contract"]: row for row in matrix["contracts"]}
    assert contracts["continuous-execution-machine"]["proposed_current_owner"] == "tools/continuity_controller.py"
    assert contracts["continuous-execution-machine"]["current_candidates"] == ["tools/continuity_controller.py"]


def test_every_row_has_resolved_target_role_or_explicit_blocker(tmp_path: Path) -> None:
    governance = _load_governance()
    inventory = _inventory(
        _row("README.md"),
        _row("個人AI檔案庫/第二層_專案與SOP/ambiguous.md"),
    )
    matrix = governance.build_classification_matrix(tmp_path, inventory)
    for row in matrix["rows"]:
        assert row["target_role"] in {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL", "UNRESOLVED"}
        if row["target_role"] == "UNRESOLVED":
            assert row["blocker"]


def test_classify_cli_writes_machine_readable_matrix(tmp_path: Path) -> None:
    governance = _load_governance()
    inventory_path = tmp_path / "inventory.json"
    output_path = tmp_path / "matrix.json"
    inventory_path.write_text(json.dumps(_inventory(_row("README.md"))), encoding="utf-8")

    rc = governance.main(
        [
            "classify",
            "--root",
            str(tmp_path),
            "--inventory",
            str(inventory_path),
            "--output",
            str(output_path),
        ]
    )

    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "WHD_KNOWLEDGE_CLASSIFICATION_V1"
    assert payload["source_head"] == "fixture-head"
