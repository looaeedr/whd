from __future__ import annotations

import inspect

import phase6_settings_panel
import phase6_settings_panel_primitives
import phase6_settings_panel_owned_render


def test_issue1370_primitives_are_reexported():
    assert phase6_settings_panel.SettingsPanelExtensionResult is phase6_settings_panel_primitives.SettingsPanelExtensionResult
    assert phase6_settings_panel.setting_number_text is phase6_settings_panel_primitives.setting_number_text
    assert phase6_settings_panel.build_choice_menubutton is phase6_settings_panel_primitives.build_choice_menubutton


def test_issue1370_owned_render_mixin_is_one_way():
    assert issubclass(
        phase6_settings_panel.Phase6SettingsPanel,
        phase6_settings_panel_owned_render.Phase6SettingsPanelOwnedRenderMixin,
    )
    facade = inspect.getsource(phase6_settings_panel)
    owner = inspect.getsource(phase6_settings_panel_owned_render)
    assert len(facade.splitlines()) < 800
    assert "from phase6_settings_panel import" not in owner
    assert "import phase6_settings_panel" not in owner
