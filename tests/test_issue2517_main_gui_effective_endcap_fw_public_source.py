"""#2517: main GUI EndCap Corner Policy reads only validated public FW source."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui import Phase6ApplicationHost
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def _state(family):
    return api.normalize_endcap_fw_state({"model": family, "fw": 25.125})


def _host(state, *, box="25.125"):
    return SimpleNamespace(
        endcap_fw_state=state,
        fw_z_var=SimpleNamespace(get=lambda: box),
    )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("mode", ("FOLLOW_BODY", "FOLLOW_HEAD", "FOLLOW_TAIL", "INDEPENDENT"))
@pytest.mark.parametrize("part", ("head", "tail"))
def test_effective_fw_equals_original_engine_without_changing_saved_state(family, mode, part):
    state = _state(family)
    if mode == "FOLLOW_HEAD":
        api.commit_endcap_fw(state, "head", 33.125, box_fw=25.125)
    elif mode == "FOLLOW_TAIL":
        api.commit_endcap_fw(state, "tail", 34.75, box_fw=25.125)
    elif mode == "INDEPENDENT":
        api.commit_endcap_fw(state, "head", 33.125, box_fw=25.125)
        api.commit_endcap_fw(state, "tail", 34.75, box_fw=25.125)
    before = deepcopy(state)
    got = Phase6ApplicationHost._effective_endcap_fw(_host(state), part)
    expected = api.resolve_endcap_fw(
        {"fw": 25.125, "endcap_fw": state}, part, state=state,
    )
    assert got == expected
    assert state == before


@pytest.mark.parametrize("bad", [None, True, False, "", "NaN", float("nan"), float("inf"), -5, 0])
def test_invalid_box_fw_never_reaches_policy_or_changes_endcap_source(bad):
    source = _state("受電箱")
    before = deepcopy(source)
    with pytest.raises(ValueError):
        Phase6ApplicationHost._effective_endcap_fw(_host(source, box=bad), "head")
    assert source == before


@pytest.mark.parametrize("malformed", [None, [], 8, "bad"])
def test_invalid_other_endcap_source_rejected_before_policy_resolution(malformed):
    source = _state("金庫型")
    source["tail"] = malformed
    before = deepcopy(source)
    with pytest.raises(ValueError, match="ENDCAP_FW_SOURCE_ROW_INVALID"):
        Phase6ApplicationHost._effective_endcap_fw(
            _host(source), "head", "25.125",
        )
    assert source == before


def test_legacy_caller_without_endcap_state_uses_validated_box_source():
    gui = SimpleNamespace()
    assert Phase6ApplicationHost._effective_endcap_fw(gui, "head", "32.125") == 32.125
    with pytest.raises(ValueError):
        Phase6ApplicationHost._effective_endcap_fw(gui, "tail", "invalid")


def test_missing_settings_fw_cannot_fabricate_default_25():
    gui = SimpleNamespace(settings_service=SimpleNamespace(snapshot=lambda: {}))
    with pytest.raises(ValueError):
        Phase6ApplicationHost._effective_endcap_fw(gui, "head")


def test_box_body_corner_policy_fallback_uses_engine_validated_physical_fw():
    gui = SimpleNamespace(_manual_corner_policy=lambda part, fw: (part, fw))
    result = Phase6ApplicationHost._box_body_corner_policies(gui, "32.125")
    assert result == (("head", 32.125), ("tail", 32.125))
    with pytest.raises(ValueError):
        Phase6ApplicationHost._box_body_corner_policies(gui, "NaN")


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_real_project_save_reload_preserves_fw_and_original_fold(family, tmp_path):
    state = _state(family)
    api.commit_endcap_fw(state, "head", 33.375, box_fw=25.125)
    snapshot = {
        "model": family, "w": 500, "h": 600, "d": 200, "t": 2,
        "fw": 25.125, "endcap_fw": state,
    }
    filename = write_project(
        tmp_path / f"effective-fw-{family}", {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )
    reloaded = read_project(filename)["snapshot"]
    prior = deepcopy(reloaded)
    for part in ("head", "tail"):
        assert Phase6ApplicationHost._effective_endcap_fw(
            _host(reloaded["endcap_fw"]), part, reloaded["fw"],
        ) == api.resolve_endcap_fw(reloaded, part)
        assert api.build_endcap_xy_fold_profiles(reloaded, part_key=part)["Y"]
    assert reloaded == prior


def test_main_gui_calls_headless_engine_for_all_physical_fw_decisions():
    for method in (Phase6ApplicationHost._effective_endcap_fw, Phase6ApplicationHost._box_body_corner_policies):
        src = inspect.getsource(method)
        assert "float(" not in src
    src = inspect.getsource(Phase6ApplicationHost._effective_endcap_fw)
    assert "manufacturing_api.normalize_operator_source_dimension(" in src
    assert "manufacturing_api.resolve_endcap_fw(" in src
    assert "manufacturing_api.project_operator_endcap_fw_controls(" in src
