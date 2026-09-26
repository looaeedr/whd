import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DT = ROOT / "docs/superpowers/checkpoints/issue613-a1-dt-p7-g.json"
PANEL = ROOT / "phase6_settings_panel.py"

ALLOWED = {"DEEPEN_EXISTING_OWNER", "KEEP_CURRENT_BOUNDARY"}


def _artifact():
    return json.loads(DT.read_text(encoding="utf-8"))


def test_p7_g_dt0_preserves_single_settings_presentation_owner():
    source = PANEL.read_text(encoding="utf-8")
    assert "class Phase6SettingsPanel:" in source
    assert "Schema-driven Tk settings UI with callback-only state mutation." in source
    assert "self._stage_setting_update" in source
    assert "self._flush_settings" in source
    assert "self._save_defaults" in source


def test_p7_g_structure_corner_endcap_mutations_remain_callback_ports():
    source = PANEL.read_text(encoding="utf-8")
    for port in (
        "_endcap_fw_value_selected",
        "_box_structure_numeric_changed",
        "_box_back_panel_mode_changed",
        "_box_structure_toggle_advanced",
        "_bottom_wrap_commit",
        "_corner_pair_changed",
        "_corner_type_selected",
        "_corner_mode_selected",
        "_corner_target_changed",
    ):
        assert f"self.{port}" in source


def test_p7_g_decision_enum_is_canonical_and_singular():
    decision = _artifact()["dt_6_decision"]
    assert set(decision["allowed_decisions"]) == ALLOWED
    assert "DEEPEN_EXISTING_OWNERS" not in json.dumps(decision)


def test_p7_r_g_requires_terminal_deletion_test_decision():
    decision = _artifact()["dt_6_decision"]
    assert decision["status"] == "COMPLETE"
    assert decision["decision"] in ALLOWED
