# -*- coding: utf-8 -*-
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"
SKILL = SKILLS / "engineering" / "phase6-corner-3d-model-integrity" / "SKILL.md"


def test_project_skills_live_only_under_agents_skills():
    assert SKILLS.is_dir()
    assert not (ROOT / "skills").exists()


def test_corner_or_3d_change_requires_full_3d_model_integrity_regression():
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "截角", "3D", "真實板厚", "合法接觸", "非法穿透",
        "求解前", "求解後", "零非法穿透", "Head / Tail",
        "INSERT / OVERLAY / INSERT_OVERLAY / WRAP", "2D / 單板 3D / 組合 3D",
        "Save / Reload", "piece-level", "config.ini", "禁止交付",
        "registry", "新增任何 Assembly Intent",
    ]
    missing = [item for item in required if item not in text]
    assert not missing, missing


def test_corner_3d_integrity_skill_is_mandatory_release_artifact():
    policy = json.loads((ROOT / "release_required_artifacts.json").read_text(encoding="utf-8"))
    assert ".agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md" in policy["mandatory_update_files"]
