from __future__ import annotations

import inspect

from gui_modules.editors import hole_editor_view
from gui_modules.editors import hole_editor_controls
from gui_modules.editors import hole_editor_round_settings


def test_issue1366_controls_are_reexported_one_way():
    assert hole_editor_view.HoleEditorCatalogControls is hole_editor_controls.HoleEditorCatalogControls
    assert hole_editor_view.HoleEditorIndicatorGroupControls is hole_editor_controls.HoleEditorIndicatorGroupControls
    assert hole_editor_view.HoleEditorFormRowBuilders is hole_editor_controls.HoleEditorFormRowBuilders
    assert hole_editor_view.draw_hole_editor_hint is hole_editor_controls.draw_hole_editor_hint


def test_issue1366_round_settings_are_reexported_one_way():
    assert hole_editor_view.HoleEditorRoundSettingsLauncher is hole_editor_round_settings.HoleEditorRoundSettingsLauncher
    assert hole_editor_view.open_round_hole_settings is hole_editor_round_settings.open_round_hole_settings
    facade = inspect.getsource(hole_editor_view)
    assert len(facade.splitlines()) < 500
    for owner in (inspect.getsource(hole_editor_controls), inspect.getsource(hole_editor_round_settings)):
        assert "from .hole_editor_view import" not in owner
        assert "import gui_modules.editors.hole_editor_view" not in owner
