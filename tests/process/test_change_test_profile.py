import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json"


def test_contract_is_current_and_workspace_first():
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["schema"] == "WHD_CHANGE_TEST_PROFILE_V1"
    assert payload["status"] == "CURRENT"
    assert payload["workspace"]["interactive_root"] == "/Google Drive/WHD"
    assert payload["workspace"]["interactive_work_prefix"] == "/Google Drive/WHD/work"
    assert payload["workspace"]["policy"] == "WORKSPACE_FIRST"


def test_bugfix_ui_combines_bugfix_and_ui_stages_then_full_regression():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="修正受電箱切換後 UI 錯誤",
        changed_files=["gui.py", "tests/test_receiving_cabinet_type.py"],
    )
    assert profile["change_type"] == "BUGFIX"
    assert profile["domains"] == ["UI"]
    assert "REPRODUCER_RED" in profile["required_stages"]
    assert "UI_CONTRACT_STATE" in profile["required_stages"]
    assert "TK_XVFB" in profile["required_stages"]
    assert profile["required_stages"][-1] == "PRODUCT_FULL_REGRESSION"


def test_feature_geometry_combines_feature_and_geometry_stages():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="新增後面板三件式功能",
        changed_files=["ae_engine/manufacturing_api.py", "tests/test_dxf_acceptance.py"],
    )
    assert profile["change_type"] == "FEATURE"
    assert profile["domains"] == ["GEOMETRY"]
    assert "FEATURE_ACCEPTANCE" in profile["required_stages"]
    assert "GEOMETRY_INVARIANTS" in profile["required_stages"]
    assert "DXF_ACCEPTANCE" in profile["required_stages"]
    assert profile["full_gate_kind"] == "PRODUCT_FULL_REGRESSION"


def test_update_gets_compatibility_and_migration_before_full_regression():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="更新 project config format",
        changed_files=["phase6_project_file.py", "tests/test_phase6_project_file.py"],
    )
    assert profile["change_type"] == "UPDATE"
    assert profile["required_stages"][:2] == ["COMPATIBILITY", "MIGRATION_CONFIG"]
    assert profile["required_stages"][-1] == "PRODUCT_FULL_REGRESSION"


def test_governance_only_uses_governance_full_suite_not_product_full():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="更新 Flow v2 治理",
        changed_files=[
            ".agents/skills/engineering/flow-v2-execution/SKILL.md",
            "tools/execution_scheduler_view.py",
            "tests/process/test_flow_v2_execution_scheduler_view.py",
        ],
        explicit_type="GOVERNANCE",
    )
    assert profile["domains"] == []
    assert "CONTROL_PLANE_REGRESSION" in profile["required_stages"]
    assert profile["full_gate_kind"] == "GOVERNANCE_FULL_SUITE"
    assert profile["required_stages"][-1] == "GOVERNANCE_FULL_SUITE"


def test_docs_metadata_only_may_skip_heavy_full_regression():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(task="更新說明文件", changed_files=["docs/operations.md", "README.md"])
    assert profile["change_type"] == "DOCS_METADATA"
    assert profile["full_gate_kind"] == "NONE"
    assert profile["full_gate_required"] is False
    assert profile["required_stages"] == ["SCHEMA_LINT_LINK"]


def test_ambiguous_change_type_fails_closed_until_explicit():
    from tools.change_test_profile import build_test_profile
    with pytest.raises(ValueError, match="ambiguous change type"):
        build_test_profile(
            task="新增並修正 receiving feature bug",
            changed_files=["phase6_box_body_structure.py"],
        )
    explicit = build_test_profile(
        task="新增並修正 receiving feature bug",
        changed_files=["phase6_box_body_structure.py"],
        explicit_type="BUGFIX",
    )
    assert explicit["change_type"] == "BUGFIX"


def test_targeted_stages_never_replace_final_full_gate_for_product_change():
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="重構 adapter",
        changed_files=["gui_modules/application/fold_designer_adapter.py"],
        explicit_type="REFACTOR",
    )
    assert "BEHAVIORAL_EQUIVALENCE" in profile["required_stages"]
    assert profile["required_stages"][-1] == "PRODUCT_FULL_REGRESSION"


def test_flow_v2_owns_profile_gate_and_requires_final_full_before_close():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "CHANGE_TEST_PROFILE_GATE_V1" in text
    assert "tools/change_test_profile.py" in text
    assert "targeted / focused 測試不得取代 final full gate" in text
    assert "ACCEPT / CLOSE" in text
