"""#2517: Fold Designer Settings FW readback is a pure public Engine projection."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_composition_settings as gui


class FakeVar:
    def __init__(self, value=None):
        self.value = value
        self.writes = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes.append(value)


def _app(state, *, fw="25.125", family="受電箱"):
    return SimpleNamespace(
        _phase6_input_snapshot={
            "model": family, "w": 800, "h": 1600, "d": 350,
            "t": 2, "fw": fw,
        },
        _settings_values={},
        _phase6_endcap_fw_state=state,
    )


def _composer(app):
    names = {
        "ENDCAP_FW_PARTS": ("head", "tail"),
        "_setting_number_text": str,
        "original": SimpleNamespace(
            tk=SimpleNamespace(StringVar=lambda value: FakeVar(value))
        ),
        "GLOBAL_CONTEXT": "global",
        "CrossCornerMode": object(),
        "_FIXED_CORNER_SUMMARIES": {"head": "fixed", "tail": "fixed"},
        "_phase6_corner_type_editable": lambda *_: False,
        "_phase6_corner_parameters_unlocked": lambda *_: False,
        "_phase6_corner_parameters_editable": lambda *_: False,
    }
    return SimpleNamespace(
        app=app, _required=lambda _namespace, name: names[name],
    )


def _sync_fw_controls(app, part):
    """Execute the real GUI Settings FW entrypoint, not a private projection."""
    follow, value = FakeVar(), FakeVar()
    gui.sync_settings_panel_extension(
        _composer(app), None,
        {"endcap_fw_follow_var": follow, "endcap_fw_value_var": value},
        part,
    )
    return {"follow_box": follow.get(), "display_fw": float(value.get())}


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("mode", api.ENDCAP_FW_MODES)
def test_settings_readback_matches_public_engine_four_state_and_keeps_source(family, mode):
    state = api.normalize_endcap_fw_state({"model": family, "fw": 25.125})
    if mode == api.FW_FOLLOW_HEAD:
        api.commit_endcap_fw(state, "head", 31.375, box_fw=25.125)
    elif mode == api.FW_FOLLOW_TAIL:
        api.commit_endcap_fw(state, "tail", 32.625, box_fw=25.125)
    elif mode == api.FW_INDEPENDENT:
        api.commit_endcap_fw(state, "head", 31.375, box_fw=25.125)
        api.commit_endcap_fw(state, "tail", 32.625, box_fw=25.125)
    app = _app(state, family=family)
    before = deepcopy(state)
    expected = api.project_operator_endcap_fw_controls(state, "25.125")
    for part in ("head", "tail"):
        assert _sync_fw_controls(app, part) == expected[part]
        assert expected[part]["display_fw"] == api.resolve_endcap_fw(
            {**app._phase6_input_snapshot, "endcap_fw": state}, part, state=state
        )
    assert state == before


def test_legacy_missing_tail_is_read_only_and_serialized_false_is_not_true():
    state = {"mode": "INDEPENDENT", "head": {
        "follow_box": "false", "value": "32.125",
    }}
    app = _app(state)
    before = deepcopy(state)
    for _ in range(2):
        assert _sync_fw_controls(app, "head") == {
            "follow_box": False, "display_fw": 32.125,
        }
        assert _sync_fw_controls(app, "tail") == {
            "follow_box": True, "display_fw": 25.125,
        }
    assert state == before and "tail" not in state


def test_settings_sync_updates_widgets_from_engine_without_writing_source():
    state = {"head": {"follow_box": "false", "value": "32.125"}}
    app = _app(state)
    composer = _composer(app)
    follow, value = FakeVar("old-follow"), FakeVar("old-value")
    before = deepcopy(state)
    gui.sync_settings_panel_extension(
        composer, None, {
            "endcap_fw_follow_var": follow,
            "endcap_fw_value_var": value,
        }, "head",
    )
    assert (follow.get(), value.get()) == (False, "32.125")
    assert state == before and "tail" not in state


@pytest.mark.parametrize("bad_tail", [None, [], "corrupt", {
    "follow_box": False, "value": "nan",
}])
def test_corrupt_opposite_part_fails_before_any_fw_widget_update(bad_tail):
    state = {
        "head": {"follow_box": False, "value": 31.0},
        "tail": bad_tail,
    }
    app = _app(state)
    composer = _composer(app)
    follow, value = FakeVar("old-follow"), FakeVar("old-value")
    before = deepcopy(state)
    with pytest.raises(ValueError):
        gui.sync_settings_panel_extension(
            composer, None, {
                "endcap_fw_follow_var": follow,
                "endcap_fw_value_var": value,
            }, "head",
        )
    assert not follow.writes and not value.writes
    assert state == before


def test_settings_context_extension_uses_same_engine_projection(monkeypatch):
    state = {"head": {"follow_box": "false", "value": 32.5}}
    app = _app(state, family="金庫型")
    composer = _composer(app)
    before = deepcopy(state)
    monkeypatch.setattr(
        gui.manufacturing_api, "project_operator_receiving_base_plate_settings",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        gui.manufacturing_api, "operator_supports_bottom_wrap_controls",
        lambda *args, **kwargs: False,
    )
    result = gui.settings_context_extension_projection(composer, None, "head")
    assert result["endcap_fw"] == {"follow": False, "effective": 32.5}
    assert state == before and "tail" not in state


def test_both_settings_entrypoints_have_no_mutating_fw_or_gui_boolean_formula():
    for fn in (
        gui.settings_context_extension_projection,
        gui.sync_settings_panel_extension,
    ):
        source = inspect.getsource(fn)
        assert "manufacturing_api.project_operator_endcap_fw_controls(" in source
        assert "setdefault(" not in source
        assert "bool(state.get" not in source
        assert "float(state.get" not in source
