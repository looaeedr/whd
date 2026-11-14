"""#2517: Head/Tail FW widget sync consumes a read-only public Engine projection."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import endcap_factory_fold as owner
from ae_engine import manufacturing_api as api
from gui_modules.parts.panels.assembly_corner import sync_endcap_fw_controls
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


class Var:
    def __init__(self, value=None):
        self.value = value
        self.writes = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes.append(value)


def host(state, box_fw="25.25"):
    head, tail = Var("old-head"), Var("old-tail")
    hf, tf = Var(None), Var(None)
    client = SimpleNamespace(
        endcap_fw_state=state,
        fw_z_var=Var(box_fw),
        fw_head_var=head,
        fw_tail_var=tail,
        fw_head_follow_var=hf,
        fw_tail_follow_var=tf,
        _fold_designer_number_text=lambda value: str(value),
    )
    return client, (head, tail, hf, tf)


def test_projection_is_exact_original_public_engine_callable():
    assert api.project_operator_endcap_fw_controls is owner.project_operator_endcap_fw_controls
    assert ae_engine.project_operator_endcap_fw_controls is api.project_operator_endcap_fw_controls
    assert "project_operator_endcap_fw_controls" in ae_engine.__all__


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("mode", [
    "FOLLOW_BODY", "FOLLOW_HEAD", "FOLLOW_TAIL", "INDEPENDENT",
])
def test_fresh_ui_refresh_matches_valid_saved_four_state_without_mutation(family, mode):
    state = api.normalize_endcap_fw_state({"model": family, "fw": 25.25})
    if mode == "FOLLOW_HEAD":
        api.commit_endcap_fw(state, "head", 33.25, box_fw=25.25)
    elif mode == "FOLLOW_TAIL":
        api.commit_endcap_fw(state, "tail", 34.75, box_fw=25.25)
    elif mode == "INDEPENDENT":
        api.commit_endcap_fw(state, "head", 33.25, box_fw=25.25)
        api.commit_endcap_fw(state, "tail", 34.75, box_fw=25.25)
    before = deepcopy(state)
    ui, (head, tail, hf, tf) = host(state)
    sync_endcap_fw_controls(ui)
    assert state == before
    assert ui.endcap_fw_state is state
    expected = api.project_operator_endcap_fw_controls(state, "25.25")
    assert (head.get(), tail.get()) == (
        str(expected["head"]["display_fw"]), str(expected["tail"]["display_fw"])
    )
    assert (hf.get(), tf.get()) == (
        expected["head"]["follow_box"], expected["tail"]["follow_box"]
    )
    assert api.resolve_endcap_fw(
        {"fw": 25.25, "endcap_fw": state}, "head", state=state,
    ) == expected["head"]["display_fw"]


def test_legacy_missing_row_is_displayed_but_never_injected_into_source():
    state = {"mode": "INDEPENDENT", "head": {"follow_box": False, "value": 31}}
    original = deepcopy(state)
    ui, (head, tail, hf, tf) = host(state)
    sync_endcap_fw_controls(ui)
    sync_endcap_fw_controls(ui)
    assert state == original
    assert (head.get(), tail.get()) == ("31.0", "25.25")
    assert (hf.get(), tf.get()) == (False, True)


def test_serialized_false_is_not_truthy_and_source_is_untouched():
    state = {
        "head": {"follow_box": "false", "value": "33.125"},
        "tail": {"follow_box": "true", "value": "garbage-inactive"},
    }
    before = deepcopy(state)
    ui, (head, tail, hf, tf) = host(state)
    sync_endcap_fw_controls(ui)
    assert (head.get(), tail.get()) == ("33.125", "25.25")
    assert (hf.get(), tf.get()) == (False, True)
    assert state == before


@pytest.mark.parametrize("bad", [None, [], 9, "invalid"])
def test_corrupt_tail_rejected_before_any_widget_update(bad):
    state = {"head": {"follow_box": False, "value": 31}, "tail": bad}
    ui, rows = host(state)
    before = deepcopy(state)
    with pytest.raises(ValueError, match="ENDCAP_FW_SOURCE_ROW_INVALID"):
        sync_endcap_fw_controls(ui)
    assert state == before
    assert all(not row.writes for row in rows)


@pytest.mark.parametrize("bad", [True, None, "", "nan", 0, -1, float("inf")])
def test_bad_box_fw_rejected_without_source_or_widget_update(bad):
    state = api.normalize_endcap_fw_state({"fw": 25})
    ui, rows = host(state, box_fw=bad)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        sync_endcap_fw_controls(ui)
    assert state == before
    assert all(not row.writes for row in rows)


@pytest.mark.parametrize("field,value", [
    ("follow_box", "not-bool"), ("follow_box", None),
    ("value", float("nan")), ("value", -1),
])
def test_active_malformed_head_source_rejected_without_partial_ui(field, value):
    state = {"head": {"follow_box": False, "value": 31}, "tail": {"follow_box": True, "value": 25}}
    state["head"][field] = value
    ui, rows = host(state)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        sync_endcap_fw_controls(ui)
    assert state == before
    assert all(not row.writes for row in rows)


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_save_reload_preserves_display_from_canonical_fw_state(family, tmp_path):
    source = api.normalize_endcap_fw_state({"model": family, "fw": 25.25})
    api.commit_endcap_fw(source, "head", 33.125, box_fw=25.25)
    snapshot = {
        "model": family, "w": 500, "h": 600, "d": 200,
        "t": 2, "fw": 25.25, "endcap_fw": source,
    }
    filename = write_project(
        tmp_path / f"head-tail-readback-{family}",
        {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = read_project(filename)["snapshot"]
    original = json.dumps(restored["endcap_fw"], sort_keys=True)
    ui, _ = host(restored["endcap_fw"])
    sync_endcap_fw_controls(ui)
    assert json.dumps(restored["endcap_fw"], sort_keys=True) == original
    for part in ("head", "tail"):
        assert api.project_operator_endcap_fw_controls(
            restored["endcap_fw"], restored["fw"],
        )[part]["display_fw"] == api.resolve_endcap_fw(restored, part)
        assert api.build_endcap_xy_fold_profiles(restored, part_key=part)["Y"]


def test_gui_renderer_delegates_without_local_manufacturing_state_writes():
    source = inspect.getsource(sync_endcap_fw_controls)
    assert "manufacturing_api.project_operator_endcap_fw_controls(" in source
    assert "setdefault(" not in source
    assert "float(" not in source
    assert "bool(" not in source
