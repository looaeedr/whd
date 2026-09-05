# -*- coding: utf-8 -*-
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "phase6-assembly-view-boundaries" / "SKILL.md"


def test_assembly_view_boundary_skill_captures_operator_vs_debug_contract():
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "正式組合圖是操作員製造視圖",
        "Joint 診斷預設不進 operator assembly scene",
        "不要用「刪 UI」代替「隔離診斷層」",
        "不要夾帶無關修正",
        "Legacy / migrated Joint",
        "USER_ADDED Joint 仍保留完整求解能力",
        "修改前必做 Inventory",
        "使用者實際 `.p6fold`",
    ]
    missing = [item for item in required if item not in text]
    assert not missing, missing


def test_assembly_view_boundary_skill_is_mandatory_in_update_policy():
    policy = json.loads((ROOT / "release_required_artifacts.json").read_text(encoding="utf-8"))
    assert ".agents/skills/engineering/phase6-assembly-view-boundaries/SKILL.md" in policy["mandatory_update_files"]
