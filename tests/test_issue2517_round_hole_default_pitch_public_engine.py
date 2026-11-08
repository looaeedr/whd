"""#2517: initial round-hole pitch must be Engine-owned, not GUI arithmetic."""
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.editors import hole_editor_round_settings as round_ui


@pytest.mark.parametrize(
    ("diameter", "expected"),
    [(10.0, 50.0), (25.0, 50.0), (30.0, 60.0), (42.5, 85.0)],
)
def test_public_engine_owns_existing_round_hole_initial_pitch(diameter, expected):
    assert manufacturing_api.operator_round_hole_default_center_distance(diameter) == expected


@pytest.mark.parametrize("invalid", [True, False, 0, -2, float("nan"), float("inf"), None, "invalid", []])
def test_public_engine_rejects_invalid_round_hole_initial_pitch_source(invalid):
    with pytest.raises(ValueError, match="圓孔"):
        manufacturing_api.operator_round_hole_default_center_distance(invalid)


@pytest.mark.parametrize("diameter", [12.0, 25.0, 31.5])
def test_round_hole_gui_uses_exact_public_engine_initial_pitch_without_tk(monkeypatch, diameter):
    class FakeTopLevel:
        def __init__(self, _editor):
            pass

        def title(self, *_args):
            pass

        def configure(self, **_kwargs):
            pass

        def transient(self, *_args):
            pass

        def grab_set(self):
            pass

        def resizable(self, *_args):
            pass

    class FakeVar:
        def __init__(self, *, value=""):
            self.value = value

        def get(self):
            return self.value

    monkeypatch.setattr(round_ui.tk, "Toplevel", FakeTopLevel)
    monkeypatch.setattr(round_ui.tk, "StringVar", FakeVar)

    source = SimpleNamespace(diameter=diameter)
    rows = [source]
    holder = [None]
    dialog = round_ui._RoundHoleSettingsDialog(
        editor=object(), theme={"bg": "#000"}, hole_session=None,
        feature_list=rows, surface=object(), width=200.0, height=180.0,
        round_window=holder, position_authority=[None],
        refresh_created=lambda: None, refresh_reference_fields=lambda: None,
        redraw=lambda: None, sync_all=lambda: None, selected_index=0,
    )
    monkeypatch.setattr(dialog, "_sync_from_center", lambda: None)
    monkeypatch.setattr(dialog, "_find_neighbor", lambda: None)
    monkeypatch.setattr(dialog, "_build_body", lambda: None)
    monkeypatch.setattr(dialog, "_bind_close_contract", lambda: None)

    dialog.open()

    expected = manufacturing_api.operator_round_hole_default_center_distance(diameter)
    assert dialog.round_center.get() == f"{expected:.2f}"
    assert rows == [source]
    assert source.diameter == diameter
    assert holder[0] is dialog.dialog
