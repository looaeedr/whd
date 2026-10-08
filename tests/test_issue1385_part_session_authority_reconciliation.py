from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "gui_modules" / "application" / "fold_designer_part_session.py"
OWNERSHIP = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "12_WHD_FoldDesignerBridgeOwnership規則.md"
AUTHORITY_MAP = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "09_WHD_Canonical_Authority_Map.md"
HISTORICAL = ROOT / "docs" / "superpowers" / "checkpoints" / "issue448-t6-part-editor-census.md"
PROSPECTIVE_DOMAIN_SESSION = ROOT / "phase6_part_editor_session.py"


def _top_functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_issue1385_current_docs_define_one_part_session_interpretation():
    ownership = OWNERSHIP.read_text(encoding="utf-8")
    authority = AUTHORITY_MAP.read_text(encoding="utf-8")
    historical = HISTORICAL.read_text(encoding="utf-8")

    assert "**CURRENT decision：APPLICATION_COMPATIBILITY_ORCHESTRATION_OWNER。**" in ownership
    assert "gui_modules/application/fold_designer_part_session.py::Phase6PartSessionOwner" in ownership
    assert "location lock 已由 #1321 supersede" in ownership
    assert "CURRENT application compatibility orchestration owner" in authority
    assert "Phase6PartSessionOwner" in authority
    assert "#1324 僅為未合併 governance residue" in authority
    assert "CURRENT LOCATION LOCK SUPERSEDED" in historical

    stale_current_wording = (
        "目前不建立 `phase6_part_editor_session.py`，也不把 "
        "`_fix11_activate_part` / save-load 路徑整塊 move-only 到新 class。"
    )
    assert stale_current_wording not in ownership


def test_issue1385_owner_is_orchestration_not_domain_authority():
    source = OWNER.read_text(encoding="utf-8")

    assert "Application compatibility orchestration for the Phase6 Part Session." in source
    assert "Manufacturing formula ownership remains" in source
    assert "project persistence" in source
    assert "update" in source
    assert "geometry and DXF truth stay outside this owner" in source
    assert "class Phase6PartSessionOwner" in source

    # The accepted owner is not a replacement Part Editor domain/session state machine.
    assert not PROSPECTIVE_DOMAIN_SESSION.exists()
    assert "class Phase6ProjectController" not in source
    assert "class _Phase6UpdateScheduler" not in source
    assert "class Phase6WorkspaceNavigationController" not in source


def test_issue1385_bridge_cannot_regrow_deep_part_session_bodies():
    functions = _top_functions(BRIDGE)
    save = functions["_fix11_save_current_part"]
    activate = functions["_fix11_activate_part"]

    assert save.end_lineno - save.lineno + 1 <= 4
    assert activate.end_lineno - activate.lineno + 1 <= 4

    save_body = ast.unparse(save)
    activate_body = ast.unparse(activate)
    assert "_phase6_part_session_owner" in save_body
    assert "_phase6_part_session_owner" in activate_body
