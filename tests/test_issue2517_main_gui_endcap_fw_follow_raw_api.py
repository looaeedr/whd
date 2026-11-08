"""#2517: main GUI EndCap Follow passes unparsed operator source to the Engine."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from gui import Phase6ApplicationHost
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def _state(model="金庫型"):
    return api.normalize_endcap_fw_state({"model": model, "fw": 25})


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _gui(state=None, *, box="25", head=False, tail=False):
    calls = []
    host = SimpleNamespace(
        endcap_fw_state=_state() if state is None else state,
        fw_z_var=_var(box),
        fw_head_follow_var=_var(head),
        fw_tail_follow_var=_var(tail),
        _sync_endcap_fw_controls=lambda: calls.append("sync"),
        _derived_cache_owner=SimpleNamespace(
            invalidate=lambda reason: calls.append(("invalidate", reason))
        ),
        _request_phase6_update=lambda reason: calls.append(("update", reason)),
    )
    return host, calls


def test_follow_api_is_single_public_engine_owner():
    assert ae_engine.operator_endcap_fw_follow is api.operator_endcap_fw_follow


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("part,raw", [
    ("head", "false"), ("head", "OFF"), ("tail", False),
    ("tail", 0), ("head", "true"), ("tail", True),
])
def test_main_gui_follows_raw_engine_transaction_and_keeps_source_detached(family, part, raw):
    old = _state(family)
    prior = deepcopy(old)
    host, calls = _gui(old, box="29.125", head=raw, tail=raw)
    expected = api.operator_endcap_fw_follow(
        {"fw": "29.125"}, {}, old, part, raw
    )
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, part)
    assert host.endcap_fw_state == expected
    assert old == prior
    assert host.endcap_fw_state is not old
    assert calls == ["sync", ("invalidate", "geometry"), ("update", "geometry")]
    assert host.endcap_fw_state[part]["follow_box"] is (
        str(raw).lower() in ("true", "1") if isinstance(raw, str) else bool(raw)
    )


@pytest.mark.parametrize("part,raw", [
    ("head", "invalid"), ("tail", "2"),
    ("head", None), ("tail", float("nan")),
])
def test_invalid_follow_never_mutates_project_or_invalidates_cache(part, raw):
    original = _state("受電箱")
    previous = deepcopy(original)
    host, calls = _gui(original, head=raw, tail=raw)
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, part)
    assert host.endcap_fw_state is original
    assert original == previous
    assert calls == ["sync"]


@pytest.mark.parametrize("bad_fw", ["NaN", float("inf"), "-4", "", True, None])
def test_invalid_box_source_fails_before_follow_commit(bad_fw):
    original = _state()
    previous = deepcopy(original)
    host, calls = _gui(original, box=bad_fw, head="false")
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, "head")
    assert original == previous and host.endcap_fw_state is original
    assert calls == ["sync"]


@pytest.mark.parametrize("bad", [[], None, 7, "damaged"])
def test_malformed_other_endcap_row_is_rejected_before_candidate_commit(bad):
    original = _state()
    original["tail"] = bad
    prior = deepcopy(original)
    host, calls = _gui(original, head="false")
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, "head")
    assert host.endcap_fw_state is original
    assert original == prior
    assert calls == ["sync"]


def test_wrong_part_identity_does_not_fall_back_to_tail():
    original = _state()
    prior = deepcopy(original)
    host, calls = _gui(original, tail=True)
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, "not-an-endcap")
    assert host.endcap_fw_state is original and original == prior
    assert calls == ["sync"]


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_real_save_reload_reopens_engine_follow_state_and_fold(family, tmp_path):
    host, calls = _gui(_state(family), box="29.75", head="false")
    Phase6ApplicationHost.on_endcap_fw_follow_changed(host, "head")
    snapshot = {
        "model": family, "w": 500, "h": 600, "d": 200,
        "t": 2, "fw": 29.75, "endcap_fw": host.endcap_fw_state,
    }
    filename = write_project(
        tmp_path / f"gui-follow-{family}", {"schema": PROJECT_SCHEMA, "snapshot": snapshot}
    )
    reopened = read_project(filename)["snapshot"]
    assert reopened["endcap_fw"]["head"]["follow_box"] is False
    assert api.resolve_endcap_fw(reopened, "head") == 29.75
    assert api.build_endcap_xy_fold_profiles(reopened, part_key="head")["Y"]
    assert calls.count(("update", "geometry")) == 1


def test_gui_callback_does_not_parse_or_mutate_physical_fw_locally():
    src = inspect.getsource(Phase6ApplicationHost.on_endcap_fw_follow_changed)
    assert "manufacturing_api.operator_endcap_fw_follow(" in src
    assert "float(" not in src
    assert "bool(" not in src
    assert "set_endcap_fw_follow(" not in src
