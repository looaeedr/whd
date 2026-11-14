"""#2517: both FW-to-EndCap GUI paths use one validated public Engine transaction."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import endcap_factory_fold as canonical
from phase6_settings_transaction_controller import Phase6SettingsTransactionController


def _state(family="金庫型"):
    return api.normalize_endcap_fw_state({"model": family, "fw": 25})


def test_public_root_facade_original_owner_identity():
    assert api.commit_operator_box_fw_takeover is canonical.commit_operator_box_fw_takeover
    assert ae_engine.commit_operator_box_fw_takeover is api.commit_operator_box_fw_takeover
    assert "commit_operator_box_fw_takeover" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("value", ("29.125", 40, 33.5))
def test_real_engine_fw_takeover_preserves_original_semantics_and_live_refs(family, value):
    original = _state(family)
    prior_head = original["head"]
    prior_tail = original["tail"]
    expected = deepcopy(original)
    assert canonical.commit_box_fw(expected, float(value)) is expected
    result = api.commit_operator_box_fw_takeover(original, value)
    assert result is original
    assert original == expected
    assert original["head"] is prior_head
    assert original["tail"] is prior_tail
    assert original["mode"] == api.FW_FOLLOW_BODY
    assert original["head"]["value"] == original["tail"]["value"] == float(value)
    for part in ("head", "tail"):
        assert api.resolve_endcap_fw(
            {"model": family, "fw": float(value)}, part, state=original,
        ) == float(value)


@pytest.mark.parametrize("bad", (
    True, False, None, "", "bad", "NaN", float("nan"),
    "inf", float("-inf"), 0, -1, "-0.001",
))
def test_invalid_operator_fw_fails_without_any_head_or_tail_source_write(bad):
    state = _state("受電箱")
    expected = deepcopy(state)
    refs = (state["head"], state["tail"])
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        api.commit_operator_box_fw_takeover(state, bad)
    assert state == expected
    assert state["head"] is refs[0]
    assert state["tail"] is refs[1]


@pytest.mark.parametrize("invalid_tail", (None, [], 37, "bad"))
def test_invalid_late_tail_does_not_leave_head_or_mode_partially_committed(invalid_tail):
    state = _state()
    state["mode"] = api.FW_FOLLOW_HEAD
    state["head"]["value"] = 37
    state["tail"] = invalid_tail
    before = deepcopy(state)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        api.commit_operator_box_fw_takeover(state, 40)
    assert state == before


def _controller(state, snapshot):
    return Phase6SettingsTransactionController(
        settings_values={"fw": 25.0},
        input_snapshot=snapshot,
        box_whd={"w": 500, "h": 600, "d": 200},
        endcap_fw_state=state,
    )


def test_settings_controller_routes_valid_editor_fw_to_public_engine():
    state = _state()
    refs = (state["head"], state["tail"])
    snapshot = {"model": "金庫型", "fw": 25, "endcap_fw": deepcopy(state)}
    controller = _controller(state, snapshot)
    output = controller.commit_editor_fw_takeover("32.25")
    assert output == state == snapshot["endcap_fw"]
    assert output["mode"] == api.FW_FOLLOW_BODY
    assert output["head"]["value"] == 32.25
    assert state["head"] is refs[0]
    assert state["tail"] is refs[1]


def test_settings_controller_invalid_editor_fw_never_rewrites_project_or_live_owner():
    state = _state()
    snapshot = {"model": "受電箱", "fw": 25, "endcap_fw": deepcopy(state)}
    controller = _controller(state, snapshot)
    before = deepcopy((state, snapshot))
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        controller.commit_editor_fw_takeover(float("nan"))
    assert (state, snapshot) == before


def test_both_real_gui_routes_use_public_transaction_without_float_shortcut():
    controller = Path("phase6_settings_transaction_controller.py").read_text(encoding="utf-8")
    shell = Path("gui_modules/application/fold_designer_composition_shell_settings.py").read_text(
        encoding="utf-8",
    )
    c = controller.split("    def commit_editor_fw_takeover(", 1)[1].split(
        "    def commit_bottom_wrap(", 1,
    )[0]
    ui = shell.split('        if "fw" in values:', 1)[1].split(
        "        defaults = dict(", 1,
    )[0]
    assert "manufacturing_api.commit_operator_box_fw_takeover(" in c
    assert "manufacturing_api.commit_operator_box_fw_takeover(" in ui
    assert "float(value)" not in c
    assert 'float(values["fw"])' not in ui
    assert '_commit_box_fw_semantics(' not in c
    assert 'required("commit_box_fw")' not in ui


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_project_save_reload_keeps_accepted_fw_and_original_engine_fold(family, tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
    state = _state(family)
    api.commit_operator_box_fw_takeover(state, "35.75")
    snapshot = {
        "model": family, "active_mode": "quantity" if family == "金庫型" else "set_bay",
        "w": 500, "h": 600, "d": 200, "t": 2, "fw": 35.75,
        "endcap_fw": deepcopy(state),
    }
    filename = write_project(
        tmp_path / f"box-fw-{family}", {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = read_project(filename)["snapshot"]
    for part in ("head", "tail"):
        assert api.resolve_endcap_fw(restored, part) == 35.75
        assert restored["endcap_fw"][part]["value"] == 35.75
        assert api.build_endcap_xy_fold_profiles(restored, part_key=part)["Y"]
