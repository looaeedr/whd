"""#2517: saved Head/Tail relief switch must use public Engine Boolean source."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import fold_designer_manufacturing_projection as gui


@pytest.fixture
def seam(monkeypatch):
    calls = []
    def topology(_part, payload):
        return (payload, "head", 800.0, 1600.0, 350.0, 2.0, 25.0,
                "金庫型", False, {}, (), {}, None, None)

    monkeypatch.setattr(gui, "_payload_topology_context", topology)
    monkeypatch.setattr(gui, "_payload_policy", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manufacturing_api, "resolve_fold_designer_legacy_numeric_settings",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        manufacturing_api, "formed_box_body_fw_widths",
        lambda *args, **kwargs: (None, None),
    )
    spec = object()
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            box_body_profile=lambda: (), box_body_structure_state=lambda: {},
        ),
        _resolved_committed_assembly_relief_cuts=lambda *args: (
            calls.append(("resolve", args)), ("actual-cut",)
        )[1],
        _end_cap_part_spec_from_values=lambda *args, **kw: (
            calls.append(("spec", kw)), spec
        )[1],
    )
    return host, calls, spec


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("FALSE", False), ("0", False), ("off", False),
    ("no", False), ("", False), (0, False), (False, False),
    ("TRUE", True), ("yes", True), ("1", True), ("on", True),
    (1, True), (True, True),
])
def test_saved_head_relief_switch_matches_public_engine_and_never_fabricates_cut(
    seam, raw, expected,
):
    host, calls, spec = seam
    source = {"_use_committed_relief": raw, "fold_profiles": {"head": []}}
    before = deepcopy(source)
    result, context = gui._fold_designer_part_spec_from_payload(host, "head", source)
    assert result is spec
    assert manufacturing_api.normalize_operator_settings_boolean(raw) is expected
    assert [name for name, _ in calls].count("resolve") == int(expected)
    assert [name for name, _ in calls].count("spec") == 1
    assert calls[-1][1]["resolved_assembly_relief_cuts"] == (
        ("actual-cut",) if expected else ()
    )
    assert source == before


def test_absent_legacy_switch_means_no_physical_relief_cut(seam):
    host, calls, _ = seam
    gui._fold_designer_part_spec_from_payload(host, "head", {})
    assert [name for name, _ in calls] == ["spec"]
    assert calls[-1][1]["resolved_assembly_relief_cuts"] == ()


@pytest.mark.parametrize("invalid", [
    None, "invalid", "NaN", "2", 2, 1.5, float("inf"),
    float("nan"), (), {}, [],
])
def test_present_invalid_relief_source_rejects_before_cut_or_part_spec(seam, invalid):
    host, calls, _ = seam
    source = {"_use_committed_relief": invalid}
    before = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        gui._fold_designer_part_spec_from_payload(host, "head", source)
    assert calls == []
    assert source == before


def test_explicit_resolved_cut_does_not_reopen_unused_switch(seam):
    host, calls, _ = seam
    source = {"resolved_assembly_relief_cuts": ("direct-certified-cut",),
              "_use_committed_relief": "invalid-but-unused"}
    gui._fold_designer_part_spec_from_payload(host, "head", source)
    assert [name for name, _ in calls] == ["spec"]
    assert calls[-1][1]["resolved_assembly_relief_cuts"] == ("direct-certified-cut",)


def test_gui_does_not_decide_saved_cut_enablement_by_truthiness():
    source = inspect.getsource(gui._fold_designer_part_spec_from_payload)
    assert "manufacturing_api.normalize_operator_settings_boolean(" in source
    assert 'bool(data.get("_use_committed_relief"))' not in source
