"""Regression for CURRENT WHD routing wording in product-classified docs.

The documentation files themselves are product-lane paths. This test
does not grant Git, local-device, or release permissions.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOP = ROOT / "個人AI檔案庫" / "第二層_專案與SOP"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_root_readme_and_handoff_use_explicit_x_authority():
    readme = read("README.md")
    handoff = read("handoff/00_AI_HANDOFF_README.md")
    for doc in (readme, handoff):
        assert "cleanup/2d-3d-sync" in doc
        assert "/派工" in doc
        assert "/接手" in doc
        assert "/推推" in doc
        assert "Preflight receipt 已退役" in doc
    assert "Agent 啟動、Preflight、派工與驗收流程入口" not in readme
    assert "Agent 啟動與 Preflight process" not in handoff


def test_fold_domain_rules_preserved_but_execution_route_corrected():
    fold = read("個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md")
    assert "## Integration / future change contract" in fold
    assert "single execution claim、non-force integration" not in fold
    assert "保留 non-force integration、exact CI 與 drift readback" in fold
    assert "/派工" in fold and "/接手" in fold and "/推推" in fold
    assert "不得用「bridge 太長」本身作 extraction authority" in fold


def test_corner_reference_separates_domain_grounding_from_old_preflight():
    corner = read("個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md")
    assert "whd_doc_role: REFERENCE" in corner
    assert "現行施工分流" in corner
    assert "ROOT_SOURCE_CURRENT → PATHS_RESERVED" in corner
    assert "不作為修改或交付前置" in corner
    assert "先跑 Phase6 preflight 並讀完 REQUIRED SKILLS" not in corner
    assert "DM7 相關回歸至少鎖定 explicit parent" in corner


def test_spec_reference_marks_old_flow_historical_and_preserves_grounding():
    spec = read("個人AI檔案庫/第二層_專案與SOP/12_WHD規格書Skill前置與Grounding規則.md")
    assert "whd_doc_role: REFERENCE" in spec
    assert "HISTORICAL / SUPERSEDED" in spec
    assert "現行規格遵守正式 X" in spec
    assert "CURRENT 指向" in spec
    assert "DOWNLOADABLE_MD_DELIVERY_GATE" in spec
    assert "KNOWING_IS_NOT_READING" in spec


def test_pitfall_ledger_retains_provenance_without_reactivating_old_transactions():
    pit = read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    assert "whd_doc_role: REFERENCE" in pit
    assert "HISTORICAL / SUPERSEDED（2026-10-11）" in pit
    assert "EXECUTION_HISTORY_SUPERSEDED_20261011" in pit
    assert "現行僅依正式 X" in pit
    # Old wording may appear in a clearly marked historical incident; reject only a live top-level directive.
    assert "\nCURRENT 永遠 WORKSPACE_DEFAULT；歷史 drift" not in pit
    assert "CURRENT 防錯規則**：owner-authored marker" not in pit
    assert "ISSUE1469_V15_INTEGRATION_PITFALL" in pit

def test_previous_audit_legacy_root_documents_have_reference_metadata():
    for path in ("GUI.MD", "說明.MD"):
        doc = read(path)
        assert doc.startswith("---\\nwhd_doc_role: REFERENCE\\n".replace("\\\\n", "\\n"))
        assert "whd_schema: WHD_DOC_META_V1" in doc
        assert "早期" in doc
    assert "FW可選" in read("GUI.MD")
    assert "def calculate_z_length" in read("說明.MD")


def test_previous_audit_reference_files_do_not_override_current():
    for path in ("CONTEXT.md", "DELIVERY_README.md",
                 "PHASE6_組合尺寸截角與JointGraph_整合最高優先規格_20260831.md"):
        content = read(path)
        assert "whd_doc_role: REFERENCE" in content
        assert "REFERENCE" in content.split("---", 2)[2][:700]
        assert "CURRENT" in content.split("---", 2)[2][:950]
    assert "Phase6 Preflight receipt 已退役" in read("DELIVERY_README.md")


def test_previous_audit_spec_status_and_checkpoint_provenance():
    assert "定稿當時" in read("docs/specs/WHD_Spec_v1_5.md")
    bridge = read("docs/specs/WHD_Fold_Designer_Bridge_Ownership_Phase6_Residual_Reduction_Spec_v1.4_2026-09-23.md")
    assert "whd_doc_role: REFERENCE" in bridge[:200]
    assert "USER_ACCEPTED_FOR_EXECUTION" in bridge
    assert "不是目前尚待核准" in bridge
    ci = read("docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md")
    assert "whd_doc_role: CURRENT" in ci[:150]
    assert "2026-10-11 實作回讀" in ci
    checkpoint = read("docs/superpowers/checkpoints/phase4-t7-composition-root.md")
    assert checkpoint.startswith("---\\nwhd_doc_role: HISTORICAL\\n".replace("\\\\n", "\\n"))
    assert "Final tested HEAD:" in checkpoint
