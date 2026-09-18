# -*- coding: utf-8 -*-
"""#342 T9 final acceptance manifest and authority guard."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "superpowers" / "checkpoints" / "issue342-t9-final-acceptance.json"
PRODUCTION_BASE = "6b04fb2bb72d9c251c979167530dee04ab4a372e"


def _manifest():
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_t9_final_acceptance_manifest_exists_and_is_complete():
    data = _manifest()
    assert data is not None, "#342 EXPECTED RED: final acceptance manifest is not created yet"
    assert data["production_base"] == PRODUCTION_BASE
    assert data["accepted_issues"] == [333, 334, 335, 336, 337, 338, 339, 340, 341]
    assert data["t8_final_run"] == 35348422624
    assert data["t8_visual_artifact_id"] == 10548370209
    assert data["t8_unresolved_visual_failures"] == 0
    assert data["full_headless_required"] is True
    assert data["full_xvfb_required"] is True
    assert data["protected_runtime_files"] == ["config.ini", "基準檔/**"]
    assert data["integration_mode"] == "non-force-fast-forward"


def test_t9_does_not_introduce_second_ui_state_or_action_authority():
    bridge = (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")
    # T3 content switch projects the existing display mode; no parallel content-mode owner.
    assert "content_mode_var" not in bridge

    # T7 shortcuts delegate to the already-authoritative actions.
    save_body = bridge[bridge.index("def _phase6_keyboard_save"):bridge.index("def _phase6_keyboard_open")]
    open_body = bridge[bridge.index("def _phase6_keyboard_open"):bridge.index("def _phase6_keyboard_fullscreen")]
    assert "self.save_project_file()" in save_body
    assert "self.load_project_file()" in open_body

    # Selector remains a projection of existing part_var/workspace ownership.
    assert "self.part_choice_button" in bridge
    assert "designer_workspace.active_part" in bridge
