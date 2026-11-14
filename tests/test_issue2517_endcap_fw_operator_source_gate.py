"""#2517: EndCap FW follow/override are strict Engine operator transactions."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import endcap_factory_fold as owner
from gui_modules.application import fold_designer_composition_registry_edges as gui
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def _source(model="金庫型"):
    snapshot = {
        "model": model, "fw": 29.0, "w": 500, "h": 600,
        "d": 200, "t": 2,
    }
    settings = {"fw": 29.0}
    state = api.normalize_endcap_fw_state(snapshot)
    return snapshot, settings, state


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
@pytest.mark.parametrize("part", ["head", "tail"])
def test_override_matches_original_four_state_engine_and_does_not_mutate(model, part):
    source, settings, state = _source(model)
    originals = deepcopy((source, settings, state))
    expected = deepcopy(state)
    owner.commit_endcap_fw(expected, part, 37.25, box_fw=29.0)
    committed = api.operator_endcap_fw_override(
        source, settings, state, part, "37.25",
    )
    assert committed == expected
    assert (source, settings, state) == originals

    saved = {**source, **settings, "endcap_fw": committed}
    for endcap in ("head", "tail"):
        assert api.resolve_endcap_fw(saved, endcap) == 37.25
        assert api.build_endcap_xy_fold_profiles(saved, part_key=endcap)["Y"]


@pytest.mark.parametrize("value", [
    None, "", "bad", 0, -3, True, False, "nan",
    float("nan"), float("inf"), "-inf",
])
def test_invalid_override_rejected_without_changing_any_source(value):
    source, settings, state = _source("受電箱")
    originals = deepcopy((source, settings, state))
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        api.operator_endcap_fw_override(source, settings, state, "head", value)
    assert (source, settings, state) == originals


@pytest.mark.parametrize("raw,follow", [
    (True, True), (False, False), ("TRUE", True), ("false", False),
    ("off", False), ("1", True), (0, False),
])
def test_follow_gate_decodes_serialized_boolean_like_canonical_engine(raw, follow):
    source, settings, state = _source()
    before = deepcopy((source, settings, state))
    expected = deepcopy(state)
    owner.set_endcap_fw_follow(expected, "head", follow, box_fw=29)
    result = api.operator_endcap_fw_follow(source, settings, state, "head", raw)
    assert result == expected
    assert (source, settings, state) == before
    assert result["head"]["follow_box"] is follow


@pytest.mark.parametrize("raw", ["nonsense", "2", 2, -1, 1.25, None, float("nan")])
def test_bad_follow_flag_is_not_silently_truthy(raw):
    source, settings, state = _source()
    before = deepcopy((source, settings, state))
    with pytest.raises(ValueError, match="布林值"):
        api.operator_endcap_fw_follow(source, settings, state, "head", raw)
    assert (source, settings, state) == before


@pytest.mark.parametrize("path", ["override", "follow"])
@pytest.mark.parametrize("invalid_box_fw", [
    None, "", True, -1, 0, float("nan"), float("inf"), "garbled",
])
def test_bad_actual_box_fw_is_not_replaced_with_legacy_default(path, invalid_box_fw):
    source, settings, state = _source("受電箱")
    settings["fw"] = invalid_box_fw
    before = deepcopy((source, settings, state))
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        if path == "override":
            api.operator_endcap_fw_override(source, settings, state, "tail", 40)
        else:
            api.operator_endcap_fw_follow(source, settings, state, "tail", True)
    assert (source, settings, state) == before


@pytest.mark.parametrize("path", ["override", "follow"])
def test_missing_real_box_fw_fails_closed_even_if_old_default_was_25(path):
    source, settings, state = _source()
    source.pop("fw")
    settings.pop("fw")
    previous = deepcopy((source, settings, state))
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        if path == "override":
            api.operator_endcap_fw_override(source, settings, state, "head", 33)
        else:
            api.operator_endcap_fw_follow(source, settings, state, "head", False)
    assert (source, settings, state) == previous


def test_legacy_missing_mode_still_uses_original_engine_migration():
    source, settings, state = _source()
    legacy = {"head": deepcopy(state["head"]), "tail": deepcopy(state["tail"])}
    before = deepcopy(legacy)
    expected = deepcopy(legacy)
    owner.commit_endcap_fw(expected, "head", 36, box_fw=29)
    assert api.operator_endcap_fw_override(
        source, settings, legacy, "head", 36,
    ) == expected
    assert legacy == before


def _controller(model="受電箱"):
    source, settings, state = _source(model)
    source["endcap_fw"] = deepcopy(state)
    controller = Phase6SettingsTransactionController(
        settings_values=settings, input_snapshot=source,
        box_whd={"w": 500, "h": 600, "d": 200},
        endcap_fw_state=state,
    )
    return controller, source, state


def test_controller_rejected_fw_does_not_touch_persisted_input_or_live_state():
    controller, source, state = _controller()
    before = deepcopy((source, state))
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        controller.commit_endcap_fw_override("head", "NaN")
    assert (source, state) == before
    with pytest.raises(ValueError, match="布林值"):
        controller.commit_endcap_fw_follow("tail", "not-bool")
    assert (source, state) == before


def test_gui_editor_event_passes_raw_string_and_does_not_redraw_invalid_value():
    observed = []
    def apply(_namespace, key, value):
        observed.append((key, value))
        source, settings, state = _source()
        api.operator_endcap_fw_override(source, settings, state, key, value)
        return "committed"
    host = SimpleNamespace(set_endcap_fw_override=apply)
    bad = SimpleNamespace(get=lambda: "NaN")
    assert gui.on_endcap_fw_value_selected(host, {}, "head", bad) is None
    assert observed == [("head", "NaN")]
    good = SimpleNamespace(get=lambda: "37.25")
    assert gui.on_endcap_fw_value_selected(host, {}, "tail", good) == "committed"


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_real_project_file_save_reload_has_same_head_tail_resolved_fw(model, tmp_path):
    source, settings, state = _source(model)
    first = api.operator_endcap_fw_override(source, settings, state, "head", "33.5")
    split = api.operator_endcap_fw_override(source, settings, first, "tail", "36.25")
    snapshot = {**source, **settings, "endcap_fw": split}
    filename = write_project(
        tmp_path / ("endcap-fw-" + model),
        {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )
    reopened = read_project(filename)["snapshot"]
    assert reopened["endcap_fw"]["mode"] == api.FW_INDEPENDENT
    assert api.resolve_endcap_fw(reopened, "head") == 33.5
    assert api.resolve_endcap_fw(reopened, "tail") == 36.25
    for part in ("head", "tail"):
        assert api.build_endcap_xy_fold_profiles(reopened, part_key=part)["Y"]
