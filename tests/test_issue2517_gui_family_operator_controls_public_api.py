"""#2517: Family Registry alone owns Vault naming and Receiving Door-cell UI gates."""
from copy import deepcopy
import inspect
import os
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.panel_naming import operator_vault_panel_name_editor_allowed as original
from gui_modules.parts.panels import door
from phase6_settings_panel import Phase6SettingsPanel
from gui_modules.application import fold_designer_composition_receiving as composer


@pytest.mark.parametrize("model,allowed", [
    ("金庫型", True), ("VAULT", True), ("vault", True),
    ("受電箱", False), ("RECEIVING", False), ("ReCeIvInG", False),
    ("自訂", False), ("", False), (None, False),
])
def test_public_vault_panel_name_editability_uses_registered_engine_identity(model, allowed):
    assert original(model) is allowed
    assert api.operator_vault_panel_name_editor_allowed(model) is allowed
    assert ae_engine.operator_vault_panel_name_editor_allowed is original


@pytest.mark.parametrize("family,expected", [
    ("受電箱", True), ("RECEIVING", True), ("ReCeIvInG", True),
    ("金庫型", False), ("VAULT", False), ("自訂", False),
])
def test_receiving_inner_door_family_query_reuses_existing_engine_api(family, expected):
    assert api.receiving_family_supports_back_panel_mode({"model": family}) is expected


def test_original_panel_name_commit_remains_engine_source_only():
    source = {"model": "VAULT", "w": 500, "h": 600, "panel_name": "P1"}
    before = deepcopy(source)
    assert api.set_cabinet_panel_name(source, "盤名2")["panel_name"] == "盤名2"
    assert source == before
    with pytest.raises(ValueError):
        api.set_cabinet_panel_name({"model": "ReCeIvInG"}, "盤名2")


def test_gui_calls_public_family_eligibility_not_hardcoded_alias_tables():
    for method in (Phase6SettingsPanel.refresh_panel_name, Phase6SettingsPanel.commit_panel_name):
        source = inspect.getsource(method)
        assert "manufacturing_api.operator_vault_panel_name_editor_allowed(" in source
        assert '!= "金庫型"' not in source
    source = inspect.getsource(door.rebuild_door_layout_ui)
    assert "manufacturing_api.receiving_family_supports_back_panel_mode(" in source
    assert '{"受電箱", "RECEIVING"}' not in source
    source = inspect.getsource(composer)
    start = source.index("    def commit_vault_panel_name(")
    end = source.index("\n    panel = Phase6SettingsPanel(", start)
    scoped = source[start:end]
    assert "manufacturing_api.operator_vault_panel_name_editor_allowed(" in scoped
    assert '!= "金庫型"' not in scoped


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="actual Tk requires Windows desktop or Linux Xvfb",
)
def test_real_settings_panel_accepts_vault_alias_and_hides_receiving_alias():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    committed = []
    panel = Phase6SettingsPanel(
        values_snapshot=lambda: {"w": 500, "h": 600, "d": 200, "t": 2},
        stage_setting_update=lambda *_: None,
        flush_settings=lambda: None,
        save_defaults=lambda _: None,
        panel_name_getter=lambda: committed[-1] if committed else "",
        panel_name_changed=lambda name: committed.append(name),
    )
    try:
        panel.build_left_global_controls(
            root, baseline_models=("VAULT", "ReCeIvInG"), initial_model="VAULT",
        )
        assert panel.panel_name_frame.winfo_manager() == "grid"
        panel.panel_name_var.set("金庫01")
        panel.commit_panel_name()
        assert committed == ["金庫01"]
        panel.baseline_model_var.set("ReCeIvInG")
        assert panel.panel_name_frame.winfo_manager() == ""
        panel.panel_name_var.set("不可提交")
        panel.commit_panel_name()
        assert committed == ["金庫01"]
        panel.baseline_model_var.set("VAULT")
        assert panel.panel_name_frame.winfo_manager() == "grid"
    finally:
        root.destroy()


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="actual Tk requires Windows desktop or Linux Xvfb",
)
def test_real_door_grid_inner_door_controls_follow_receiving_registry_alias():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    host = SimpleNamespace(
        root=root,
        door_layout_columns_frame=tk.Frame(root),
        door_layout_columns=[{
            "width_var": tk.StringVar(root, "500"), "width_auto": False,
            "height_vars": [tk.StringVar(root, "800")], "height_auto": [False],
        }],
        baseline_var=tk.StringVar(root, "ReCeIvInG"),
        COLOR_PANEL="#222222", COLOR_BG="#111111", COLOR_TEXT="#ffffff",
        COLOR_TEXT_MUTED="#cccccc", COLOR_INPUT_BG="#333333", COLOR_ACCENT="#00ccff",
        _ensure_door_layout_default=lambda: None,
        _receiving_inner_door_enabled=lambda key: False,
        _receiving_inner_door_inward_offset=lambda key: 10,
        _fold_designer_number_text=lambda v: str(v),
        refresh_door_layout_status=lambda: None,
    )
    try:
        door.rebuild_door_layout_ui(host)
        assert "0:0" in host.door_layout_inner_door_vars
        assert host.door_layout_inner_door_vars["0:0"].get() is False
        host.baseline_var.set("VAULT")
        door.rebuild_door_layout_ui(host)
        assert host.door_layout_inner_door_vars == {}
    finally:
        root.destroy()
