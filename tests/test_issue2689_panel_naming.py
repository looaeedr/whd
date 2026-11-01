# -*- coding: utf-8 -*-
"""#2689: canonical panel naming is persistent input, not manufacturing identity."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_layout, resize_receiving_bays,
    resize_receiving_sets, update_receiving_bay,
)
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def layout():
    return new_receiving_layout(width=800, height=1600, depth=350)


def names(value):
    return [bay["panel_name"] for group in value["sets"] for bay in group["bays"]]


def test_initial_names_follow_all_sets_and_do_not_copy_prior_label():
    start = layout()
    assert names(start) == ["P1"]
    assert start["next_panel_number"] == 2
    changed = resize_receiving_bays(start, set_index=0, bay_count=3)
    changed = resize_receiving_sets(changed, set_count=2)
    assert names(changed) == ["P1", "P2", "P3", "P4"]
    assert changed["next_panel_number"] == 5
    assert changed["sets"][0]["bays"][0]["stable_id"] != changed["sets"][1]["bays"][0]["stable_id"]


def test_deleted_bay_and_set_numbers_never_recycle_even_when_stable_id_does():
    current = resize_receiving_bays(layout(), set_index=0, bay_count=3)
    current = resize_receiving_bays(current, set_index=0, bay_count=2)
    assert names(current) == ["P1", "P2"]
    current = resize_receiving_bays(current, set_index=0, bay_count=3)
    assert names(current) == ["P1", "P2", "P4"]
    current = resize_receiving_sets(current, set_count=2)
    assert names(current) == ["P1", "P2", "P4", "P5"]
    current = resize_receiving_sets(current, set_count=1)
    current = resize_receiving_sets(current, set_count=2)
    assert names(current) == ["P1", "P2", "P4", "P6"]
    assert current["next_panel_number"] == 7


def test_custom_names_and_reserved_p_numbers():
    current = resize_receiving_bays(layout(), set_index=0, bay_count=2)
    before = deepcopy(current)
    current = api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name=" CONTROL-2 ")
    assert names(current) == ["P1", "CONTROL-2"]
    assert names(before) == ["P1", "P2"]
    assert current["next_panel_number"] == 3
    with pytest.raises(ValueError, match="不可重新使用"):
        api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="P2")
    with pytest.raises(ValueError, match="不得重複"):
        api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="p1")
    current = api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="P10")
    assert current["next_panel_number"] == 11
    current = resize_receiving_bays(current, set_index=0, bay_count=3)
    assert names(current) == ["P1", "P10", "P11"]


@pytest.mark.parametrize("name", ["", " ", "C/01", "CON", "nul.txt", "A?", "AA\\BB", "X:", "x\x00y", "Z"*121])
def test_receiving_invalid_names_are_rejected_atomically(name):
    current = layout()
    with pytest.raises(ValueError):
        api.rename_receiving_panel(current, set_index=0, bay_index=0, panel_name=name)
    assert names(current) == ["P1"]


def test_existing_names_must_be_unique_without_aliasing_case_or_stable_id():
    current = resize_receiving_bays(layout(), set_index=0, bay_count=2)
    with pytest.raises(ValueError, match="不得重複"):
        api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="p1")
    unchanged_ids = [row["stable_id"] for row in current["sets"][0]["bays"]]
    changed = api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="A02")
    assert [row["stable_id"] for row in changed["sets"][0]["bays"]] == unchanged_ids
    assert [row["width"] for row in changed["sets"][0]["bays"]] == [800.0, 800.0]


def test_legacy_layout_migrates_without_guessing_from_reused_stable_id():
    current = resize_receiving_bays(layout(), set_index=0, bay_count=2)
    current = resize_receiving_sets(current, set_count=2)
    old = deepcopy(current)
    old.pop("next_panel_number")
    for group in old["sets"]:
        for bay in group["bays"]:
            bay.pop("panel_name")
    migrated = normalize_receiving_layout(old)
    assert names(migrated) == ["P1", "P2", "P3"]
    assert migrated["next_panel_number"] == 4
    assert normalize_receiving_layout(migrated) == migrated


@pytest.mark.parametrize("counter", [True, 0, -1, 1.0, "4", None])
def test_counter_type_must_be_valid_when_explicit(counter):
    current = layout()
    current["next_panel_number"] = counter
    if counter is None:
        assert normalize_receiving_layout(current)["next_panel_number"] == 2
    else:
        with pytest.raises(ValueError):
            normalize_receiving_layout(current)


def test_counter_cannot_regress_below_explicit_p_names():
    current = resize_receiving_bays(layout(), set_index=0, bay_count=2)
    current["next_panel_number"] = 2
    with pytest.raises(ValueError, match="不能重用"):
        normalize_receiving_layout(current)


def test_receiving_save_reload_preserves_counter_and_all_names(tmp_path):
    current = resize_receiving_bays(layout(), set_index=0, bay_count=3)
    current = api.rename_receiving_panel(current, set_index=0, bay_index=1, panel_name="中間")
    current = resize_receiving_bays(current, set_index=0, bay_count=2)
    path = write_project(tmp_path/"receiving.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": {
            "model": "受電箱", "active_mode": "set_bay",
            "receiving_layout": current,
        }, "final_geometry": {},
    })
    saved = read_project(path)["snapshot"]["receiving_layout"]
    assert names(saved) == ["P1", "中間"]
    assert saved["next_panel_number"] == 4
    expanded = resize_receiving_bays(saved, set_index=0, bay_count=3)
    assert names(expanded) == ["P1", "中間", "P4"]


def test_vault_default_blank_custom_name_and_project_roundtrip(tmp_path):
    raw = {"model": "金庫型"}
    updated = api.set_cabinet_panel_name(raw, " A01 ")
    assert updated["panel_name"] == "A01"
    assert "panel_name" not in raw
    for name in ("", "A01"):
        snapshot = api.set_cabinet_panel_name(raw, name)
        path = write_project(tmp_path/f"vault-{name or 'blank'}.p6fold", {
            "schema": PROJECT_SCHEMA, "snapshot": snapshot, "final_geometry": {},
        })
        assert read_project(path)["snapshot"]["panel_name"] == name
    original = write_project(tmp_path/"old-vault.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": raw, "final_geometry": {},
    })
    assert read_project(original)["snapshot"]["panel_name"] == ""
    with pytest.raises(ValueError, match="指定 Set"):
        api.set_cabinet_panel_name({"model": "受電箱"}, "P9")


def test_public_ae_engine_exports_are_stable():
    from ae_engine import normalize_panel_name, rename_receiving_panel, set_cabinet_panel_name
    assert normalize_panel_name is api.normalize_panel_name
    assert rename_receiving_panel is api.rename_receiving_panel
    assert set_cabinet_panel_name is api.set_cabinet_panel_name
