"""#2517: GUI inner-door checkbox and mm edits are one atomic Engine transaction.

Read-only GUI state is never allowed to discard malformed saved physical rows
or invent a second Door cell/part identity during an edit.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.operator_receiving_inner_door_source import (
    apply_operator_receiving_inner_door_presence as presence_owner,
    apply_operator_receiving_inner_door_inward_offset as offset_owner,
)
from gui import Phase6ApplicationHost as GUI
import phase6_project_file as project


def _source():
    return [
        {"cell_key": "0:1", "stable_id": "lower",
         "inward_offset_mm": 64.25, "included_frame_sides": ["top", "left"],
         "nfb_draft_selection": {"version": "confirmed-source-only"}},
        {"cell_key": "0:0", "stable_id": "upper",
         "inward_offset_mm": 60.0, "included_frame_sides": ["top", "left", "right"]},
    ]


def _host(rows=None):
    return SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: "受電箱"),
        receiving_inner_doors=deepcopy(_source() if rows is None else rows),
    )


def test_public_facade_and_root_share_original_atomic_engine_owner():
    for name, owner in (
        ("apply_operator_receiving_inner_door_presence", presence_owner),
        ("apply_operator_receiving_inner_door_inward_offset", offset_owner),
    ):
        assert getattr(api, name) is owner
        assert getattr(ae_engine, name) is owner
        assert name in ae_engine.__all__


def test_enabled_toggle_preserves_real_saved_source_and_sorts_grid_without_mutation():
    source = _source()
    before = deepcopy(source)
    result = api.apply_operator_receiving_inner_door_presence(
        {"model": "受電箱"}, source, cell_key="0:1", enabled=True,
    )
    assert source == before
    assert [row["cell_key"] for row in result] == ["0:0", "0:1"]
    assert result[1]["stable_id"] == "lower"
    assert result[1]["inward_offset_mm"] == 64.25
    assert result[1]["nfb_draft_selection"] == {"version": "confirmed-source-only"}
    result[1]["nfb_draft_selection"]["version"] = "edited-copy"
    assert source == before


def test_enable_new_cell_uses_original_engine_physical_identity_and_family_default():
    source = _source()
    before = deepcopy(source)
    actual = api.apply_operator_receiving_inner_door_presence(
        {"model": "受電箱"}, source, cell_key="1:0", enabled=True,
    )
    new = actual[2]
    expected = api.project_operator_receiving_inner_door_enabled_source(
        {"model": "受電箱"}, "1:0",
    )
    assert new == expected
    assert new["stable_id"] == api.receiving_inner_door_stable_id_for_cell("1:0")
    assert source == before


def test_disable_existing_and_missing_cell_does_not_touch_other_physical_sources():
    source = _source()
    before = deepcopy(source)
    without = api.apply_operator_receiving_inner_door_presence(
        {"model": "受電箱"}, source, cell_key="0:1", enabled=False,
    )
    assert without == [before[1]]
    repeated = api.apply_operator_receiving_inner_door_presence(
        {"model": "受電箱"}, without, cell_key="0:1", enabled=False,
    )
    assert repeated == without
    assert source == before


@pytest.mark.parametrize("bad", (
    [{"cell_key": "0:0", "stable_id": "upper"},
     {"cell_key": "0:0", "stable_id": "dup"}],
    [{"cell_key": "0:0", "stable_id": "upper"},
     {"cell_key": "0:1", "stable_id": "upper"}],
    [{"cell_key": "0:0", "stable_id": "upper"}, "bad"],
    [{"cell_key": "0:0", "stable_id": True}],
    [{"cell_key": "bad-grid", "stable_id": "mystery"}],
))
def test_malformed_unrelated_saved_rows_cannot_be_silently_dropped(bad):
    original = deepcopy(bad)
    with pytest.raises(ValueError):
        api.apply_operator_receiving_inner_door_presence(
            {"model": "受電箱"}, bad, cell_key="1:0", enabled=True,
        )
    assert bad == original


@pytest.mark.parametrize("cell_key,enabled", (
    ("-1:0", True), ("x:0", False), ("0:0", 1),
    ("0:0", "True"), ("0:0", None),
))
def test_invalid_checkbox_or_grid_identity_rejected_without_commit(cell_key, enabled):
    source = _source()
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.apply_operator_receiving_inner_door_presence(
            {"model": "受電箱"}, source, cell_key=cell_key, enabled=enabled,
        )
    assert source == before


def test_inward_mm_transaction_changes_only_target_with_detached_saved_rows():
    source = _source()
    before = deepcopy(source)
    rows, value = api.apply_operator_receiving_inner_door_inward_offset(
        source, cell_key="0:0", inward_offset_mm="70.25",
    )
    assert value == 70.25
    assert rows[1]["inward_offset_mm"] == 70.25
    assert rows[0] == before[0]
    assert source == before
    rows[0]["nfb_draft_selection"]["version"] = "changed-copy"
    assert source == before


@pytest.mark.parametrize("invalid", (
    True, float("nan"), float("inf"), -1, "-0.125", None, "not-mm",
))
def test_invalid_offset_rejected_without_source_update(invalid):
    source = _source()
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.apply_operator_receiving_inner_door_inward_offset(
            source, cell_key="0:1", inward_offset_mm=invalid,
        )
    assert source == before


def test_missing_offset_target_cannot_create_new_physical_inner_door():
    source = _source()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="no enabled inner door"):
        api.apply_operator_receiving_inner_door_inward_offset(
            source, cell_key="1:2", inward_offset_mm="100",
        )
    assert source == before


def test_real_main_gui_checkbox_calls_public_atomic_engine_transaction(monkeypatch):
    host = _host()
    original = api.apply_operator_receiving_inner_door_presence
    calls = []

    def delegated(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(api, "apply_operator_receiving_inner_door_presence", delegated)
    before = deepcopy(host.receiving_inner_doors)
    assert GUI._set_receiving_inner_door_enabled(host, "1:0", True) is True
    assert len(calls) == 1
    assert calls[0][0][0] == {"model": "受電箱"}
    assert calls[0][0][1] == before
    assert calls[0][1] == {"cell_key": "1:0", "enabled": True}
    assert [x["cell_key"] for x in host.receiving_inner_doors] == [
        "0:0", "0:1", "1:0",
    ]


def test_real_main_gui_inward_offset_calls_public_transaction(monkeypatch):
    host = _host()
    original = api.apply_operator_receiving_inner_door_inward_offset
    observed = []

    def delegated(*args, **kwargs):
        observed.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(api, "apply_operator_receiving_inner_door_inward_offset", delegated)
    before = deepcopy(host.receiving_inner_doors)
    assert GUI._set_receiving_inner_door_inward_offset(host, "0:1", "88.5") == 88.5
    assert observed == [((before,), {"cell_key": "0:1", "inward_offset_mm": "88.5"})]
    assert host.receiving_inner_doors[0]["inward_offset_mm"] == 88.5
    assert before[0]["inward_offset_mm"] == 64.25


def test_gui_rejected_duplicate_does_not_modify_live_source():
    host = _host(_source() + [deepcopy(_source()[1])])
    before = deepcopy(host.receiving_inner_doors)
    with pytest.raises(ValueError, match="重複"):
        GUI._set_receiving_inner_door_enabled(host, "0:1", False)
    assert host.receiving_inner_doors == before


def test_real_project_save_reload_preserves_committed_operator_inner_door_source(tmp_path):
    source = {"model": "受電箱", "w": 800.0, "h": 1600.0,
              "d": 350.0, "t": 2.0, "fw": 25.0}
    rows = api.apply_operator_receiving_inner_door_presence(
        source, [], cell_key="0:0", enabled=True,
    )
    rows, _ = api.apply_operator_receiving_inner_door_inward_offset(
        rows, cell_key="0:0", inward_offset_mm=0.0,
    )
    source["inner_doors"] = rows
    original = deepcopy(source)
    target = project.write_project(tmp_path / "receiving-inner-door.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": source,
    })
    reloaded = project.read_project(target)["snapshot"]
    assert source == original
    assert reloaded["inner_doors"][0]["stable_id"] == rows[0]["stable_id"]
    assert reloaded["inner_doors"][0]["cell_key"] == "0:0"
    assert reloaded["inner_doors"][0]["inward_offset_mm"] == 0.0
    assert reloaded["inner_doors"][0]["included_frame_sides"] == rows[0]["included_frame_sides"]


def test_main_gui_does_not_filter_or_sort_manufacturing_source_locally():
    source = Path(__import__("gui").__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                and n.name == "Phase6ApplicationHost")
    targets = {
        "_set_receiving_inner_door_enabled",
        "_set_receiving_inner_door_inward_offset",
    }
    methods = {n.name: n for n in host.body if isinstance(n, ast.FunctionDef)
               and n.name in targets}
    assert set(methods) == targets
    for name, method in methods.items():
        calls = [
            n for n in ast.walk(method)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "manufacturing_api"
            and n.func.attr.startswith("apply_operator_receiving_inner_door_")
        ]
        assert len(calls) == 1, name
        assert not any(isinstance(n, (ast.For, ast.ListComp, ast.Lambda))
                       for n in ast.walk(method)), name
