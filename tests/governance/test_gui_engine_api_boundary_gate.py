"""Regression proofs for GUI input-only / engine manufacturing API ownership."""
from pathlib import Path

import pytest

from tools.gui_engine_api_boundary_gate import (
    BoundaryGateError, added_violations, evaluate_pr, is_gui_path,
    violations,
)


def test_gui_can_collect_inputs_into_part_spec_and_call_public_api():
    source = (
        "from ae_engine import manufacturing_api, ManufacturingContext\n"
        "from ae_engine.contracts import DoorPartSpec\n"
        "def export_clicked(path, data):\n"
        "    spec = DoorPartSpec(**data)\n"
        "    return manufacturing_api.generate_part(spec, path, ManufacturingContext())\n"
    )
    assert violations(source, "gui_modules/project/export_actions.py") == {}


@pytest.mark.parametrize("source,code", [
    ("from ae_engine.ae import export_door_dxf\n", "GUI_ENGINE_INTERNAL_IMPORT"),
    ("from ae_engine import ae\n", "GUI_ENGINE_INTERNAL_IMPORT"),
    ("import ae_engine.sheetmetal_geometry\n", "GUI_ENGINE_INTERNAL_IMPORT"),
    ("import ezdxf\n", "GUI_LOW_LEVEL_DXF_IMPORT"),
    ("def compute_unfold_length(x):\n    return x\n", "GUI_MANUFACTURING_FORMULA_OWNER"),
    ("def on_click():\n    ae.export_door_dxf('x')\n", "GUI_DIRECT_LOW_LEVEL_EXPORT"),
    ("def on_click(bend_allowance, length):\n    return bend_allowance + length\n", "GUI_DERIVES_MANUFACTURING_VALUE"),
    ("def on_click():\n    manufacturing_api._door_export()\n", "GUI_PRIVATE_API_CALL"),
    ("from ae_engine.manufacturing_api import _door_export\n", "GUI_PRIVATE_API_IMPORT"),
])
def test_new_gui_ownership_violations_blocked(source, code):
    found = added_violations("", source, "gui_modules/project/export_actions.py")
    assert any(code in value for value in found)


@pytest.mark.parametrize("import_stmt", [
    "import tkinter\n",
    "from gui_modules.project import export_actions\n",
    "import fold_designer_bridge\n",
])
def test_engine_cannot_depend_on_gui_or_tk(import_stmt):
    assert any(
        "ENGINE_REVERSE_IMPORT" in v
        for v in added_violations("", import_stmt, "ae_engine/manufacturing_api.py")
    )


def test_preexisting_gui_violations_not_claimed_fixed_or_allowed_to_grow():
    before = "from ae_engine import ae\n"
    assert added_violations(before, before, "gui.py") == []
    after = before + "import ae_engine.sheetmetal_geometry\n"
    assert len(added_violations(before, after, "gui.py")) == 1


def test_gui_appearance_code_is_allowed():
    assert violations(
        "def update_preview_label(label, result):\n    label.set(result.name)\n",
        "phase6_preview_panel.py",
    ) == {}
    assert is_gui_path("fold_designer_bridge.py")


def test_invalid_python_or_unknown_sha_fails_closed(tmp_path: Path):
    with pytest.raises(BoundaryGateError, match="invalid Python"):
        violations("def nope(:\n", "gui.py")
    with pytest.raises(BoundaryGateError, match="exact 40"):
        evaluate_pr(tmp_path, "localX", "HEAD")


def test_ci_and_current_authorities_reference_guard():
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "AGENTS.md",
        root / "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md",
    ]
    for file in files:
        assert "GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1" in file.read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/whd-gui-engine-api-boundary.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request:" in workflow and "localX" in workflow
    assert "git show" in workflow
    assert "tools/gui_engine_api_boundary_gate.py" in workflow
    assert "tests/governance/test_gui_engine_api_boundary_gate.py" in workflow


def test_current_cadsplit_wire_is_source_only_not_external_manufacturing() -> None:
    root = Path(__file__).resolve().parents[2]
    ai_04 = (root / "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md").read_text(
        encoding="utf-8"
    )
    current = ai_04.split("## [HISTORICAL/SUPERSEDED] Legacy ae_engine notes")[0]
    assert "外部 CADSplit 的 seam 是已授權" not in current
    for phrase in (
        "外部 CADSplit 目前沒有可用的已驗證製造 API seam",
        "source-only JSON/CLI 通訊相容介面",
        "WHD_OPERATION_NOT_IMPLEMENTED",
        "manufacturing_verified=false",
        "不具有獨立製造權威",
    ):
        assert phrase in current, f"CURRENT 04 CADSplit API boundary mismatch: {phrase}"

    wire = (root / "docs/integrations/CADSplit_WHD_Contract.md").read_text(encoding="utf-8")
    assert "zero enabled capabilities" in wire
    assert "WHD_OPERATION_NOT_IMPLEMENTED" in wire
    assert "not\nevidence of an installed Worker" in wire

def test_cadsplit_api_reference_is_discoverable_before_manufacturing_work() -> None:
    """Existing API gate must retain the complete reading path, not a second CURRENT."""
    root = Path(__file__).resolve().parents[2]
    owner = "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md"
    reference = "docs/integrations/WHD_CADSplit_API_架構與權威整合_REFERENCE_v5.1.md"
    gate = "CADSPLIT_WHD_API_REFERENCE_READ_GATE_V1"

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    current = (root / owner).read_text(encoding="utf-8")
    authority_map = (root / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(
        encoding="utf-8"
    )
    reference_text = (root / reference).read_text(encoding="utf-8")

    assert gate in agents and gate in current
    assert reference in agents and reference in current
    assert "先" in agents and "全文" in agents
    assert (
        f"<!-- WHD_AUTHORITY contract=manufacturing-architecture role=CURRENT path={owner} -->"
        in authority_map
    )
    assert (
        f"<!-- WHD_AUTHORITY contract=manufacturing-architecture role=REFERENCE "
        f"path={reference} canonical={owner} -->"
        in authority_map
    )
    assert authority_map.count(
        "<!-- WHD_AUTHORITY contract=manufacturing-architecture role=CURRENT "
    ) == 1
    assert reference_text.startswith(
        "---\n"
        "whd_doc_role: REFERENCE\n"
        "whd_contract: manufacturing-architecture\n"
        f"whd_canonical: {owner}\n"
    )
    for key in ("CADSplit", "Set/Bay", "全自動", "Save→Reload"):
        assert key in reference_text
