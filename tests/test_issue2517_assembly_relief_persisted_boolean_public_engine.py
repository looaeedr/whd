"""#2517: persisted Assembly Relief physical CUTTING booleans use Engine contract."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import assembly_relief_state as persisted
from ae_engine import manufacturing_api as api
from ae_engine import operator_relief_replay as replay
from gui_modules.application import manufacturing_adapter as gui


def _unexpected(*_args, **_kwargs):
    raise AssertionError("disabled or invalid source must not enter manufacturing")


def _gui_host(state, *, controller=None):
    return SimpleNamespace(
        assembly_relief_state=state,
        workspace_controller=controller or SimpleNamespace(
            box_body_profile=_unexpected,
            box_body_structure_state=_unexpected,
        ),
    )


@pytest.mark.parametrize("raw", (False, 0, "false", "FALSE", "0", "off", "no", ""))
def test_disabled_saved_relief_never_reaches_box_body_or_cutting(monkeypatch, raw):
    monkeypatch.setattr(replay, "formed_box_body_fw_widths", _unexpected)
    source = {"enabled": raw}
    original = deepcopy(source)
    assert api.normalize_operator_settings_boolean(raw) is False
    assert gui._resolved_committed_assembly_relief_cuts(
        _gui_host(source), "head", {"t": 2}, {},
    ) == ()
    assert api.resolve_operator_committed_relief_cuts(
        "head", {"t": 2}, relief_state=source,
    ) == ()
    assert api.committed_relief_cuts(source, "head", {}) == ()
    assert source == original


def test_missing_legacy_flag_stays_disabled():
    assert gui._resolved_committed_assembly_relief_cuts(
        _gui_host({}), "tail", {"t": 2}, {},
    ) == ()
    assert api.resolve_operator_committed_relief_cuts(
        "tail", {"t": 2}, relief_state={},
    ) == ()
    assert api.committed_relief_cuts({}, "tail", {}) == ()


@pytest.mark.parametrize("bad", (None, "invalid", "2", 2, 1.5, [], {}))
def test_invalid_saved_enablement_fails_before_any_manufacturing(bad, monkeypatch):
    monkeypatch.setattr(replay, "formed_box_body_fw_widths", _unexpected)
    source = {"enabled": bad}
    original = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        gui._resolved_committed_assembly_relief_cuts(
            _gui_host(source), "head", {"t": 2}, {},
        )
    with pytest.raises(ValueError, match="布林值"):
        api.resolve_operator_committed_relief_cuts(
            "head", {"t": 2}, relief_state=source,
        )
    with pytest.raises(ValueError, match="布林值"):
        api.committed_relief_cuts(source, "head", {})
    assert source == original


@pytest.mark.parametrize("verified,accepted", (
    ("false", "false"), ("0", 0), ("off", False), (False, "no"),
))
def test_saved_part_with_both_certification_flags_false_cannot_release_cut(
    verified, accepted, monkeypatch,
):
    monkeypatch.setattr(persisted, "source_matches_current", _unexpected)
    source = {
        "enabled": "true",
        "parts": {"head": {
            "verified": verified, "canonical_accepted": accepted,
            "cuts": [[[0, 0], [1, 0], [0, 1]]],
        }},
    }
    assert persisted.committed_relief_cuts(source, "head", {}) == ()
    assert json.loads(json.dumps(source))["parts"]["head"]["verified"] == verified


@pytest.mark.parametrize("verified,accepted", (
    ("true", "false"), (True, 0), ("false", "on"),
))
def test_legitimate_saved_certification_still_returns_original_cut(
    verified, accepted, monkeypatch,
):
    monkeypatch.setattr(persisted, "source_matches_current", lambda *args, **kwargs: True)
    source = {
        "enabled": "true", "source": {},
        "parts": {"head": {
            "verified": verified, "canonical_accepted": accepted,
            "cuts": [[[0, 0], [2, 0], [0, 2]]],
        }},
    }
    original = deepcopy(source)
    assert persisted.committed_relief_cuts(source, "head", {}) == (
        ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),
    )
    assert persisted.committed_relief_cuts(
        json.loads(json.dumps(source)), "head", {},
    ) == (((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),)
    assert source == original


@pytest.mark.parametrize("field,bad", (
    ("verified", None), ("verified", "bogus"), ("verified", 2),
    ("canonical_accepted", None), ("canonical_accepted", "maybe"),
    ("canonical_accepted", 1.2),
))
def test_malformed_saved_part_provenance_fails_closed_before_cut(
    field, bad, monkeypatch,
):
    monkeypatch.setattr(persisted, "source_matches_current", _unexpected)
    source = {
        "enabled": True,
        "parts": {"tail": {
            "verified": False, "canonical_accepted": False,
            "cuts": [[[0, 0], [2, 0], [0, 2]]],
        }},
    }
    source["parts"]["tail"][field] = bad
    original = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        persisted.committed_relief_cuts(source, "tail", {})
    assert source == original


def test_gui_enabled_source_is_forwarded_unchanged_to_public_engine(monkeypatch):
    calls = []
    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return (("engine-cut",),)
    monkeypatch.setattr(api, "resolve_operator_committed_relief_cuts", capture)
    source = {"enabled": "true", "source": {"version": 1}}
    before = deepcopy(source)
    controller = SimpleNamespace(
        box_body_profile=lambda: (),
        box_body_structure_state=lambda: {},
    )
    host = _gui_host(source, controller=controller)
    host._baseline_source_model = lambda: "金庫型"
    host.assembly_joint_state = {}
    result = gui._resolved_committed_assembly_relief_cuts(
        host, "head", {"t": 2}, {},
    )
    assert result == (("engine-cut",),)
    assert len(calls) == 1 and calls[0][1]["relief_state"] == source
    assert source == before


def test_no_persisted_boolean_truthiness_in_gui_or_engine_replay():
    sources = (
        inspect.getsource(gui._resolved_committed_assembly_relief_cuts),
        inspect.getsource(replay.resolve_operator_committed_relief_cuts),
        inspect.getsource(persisted.committed_relief_cuts),
    )
    assert "manufacturing_api.normalize_operator_settings_boolean(" in sources[0]
    assert all("normalize_operator_settings_boolean(" in s for s in sources)
    assert all('bool(state.get("enabled"))' not in s for s in sources)
    assert 'bool(saved.get("enabled"))' not in sources[1]
    assert 'bool(part.get("verified"))' not in sources[2]
    assert 'bool(part.get("canonical_accepted"))' not in sources[2]
