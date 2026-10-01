# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.receiving_layout import (
    RECEIVING_LAYOUT_SCHEMA,
    derive_bay_lock_state,
    new_receiving_layout,
    normalize_receiving_layout,
)
from phase6_box_body_structure import BackPanelMode, back_panel_mode, set_side_back_back_panel_mode
import phase6_project_file as project


def _receiving_snapshot(*, w=800.0, h=1600.0, d=350.0, mode=BackPanelMode.FULL):
    snap = receiving.apply_family_defaults({"t": 2.0})
    snap.update({"w": float(w), "h": float(h), "d": float(d)})
    state = receiving.resolve_box_body_structure_state(None)
    state = set_side_back_back_panel_mode(state, mode)
    snap["workspace"] = {"box_body_structure": state}
    # Model normalizers may have created the initial layout before test values
    # were applied; a legacy payload intentionally omits it for migration.
    snap.pop("receiving_layout", None)
    return snap


def test_fresh_receiving_defaults_include_one_set_one_bay_authority():
    snap = receiving.apply_family_defaults({"t": 2.0})
    layout = normalize_receiving_layout(snap["receiving_layout"])
    assert layout["schema"] == RECEIVING_LAYOUT_SCHEMA
    assert len(layout["sets"]) == 1
    set1 = layout["sets"][0]
    assert set1["stable_id"] == "receiving:set:1"
    assert set1["joints"] == []
    assert len(set1["bays"]) == 1
    bay1 = set1["bays"][0]
    assert bay1 == {
        "stable_id": "receiving:set:1:bay:1",
        "width": pytest.approx(float(snap["w"])),
        "height": pytest.approx(float(snap["h"])),
        "depth": pytest.approx(float(snap["d"])),
        "back_panel_mode": "FULL",
    }
    assert derive_bay_lock_state(layout) == (False, False)


def test_v1_receiving_migrates_to_v2_and_persists_without_legacy_dimension_or_mode_aliases(tmp_path):
    snapshot = _receiving_snapshot(w=810, h=1700, d=420, mode=BackPanelMode.BACK_OPENING)
    payload = {"schema": project.PROJECT_SCHEMA_V1, "snapshot": snapshot, "final_geometry": {"stale": True}}

    path = project.write_project(tmp_path / "legacy-receiving.p6fold", payload)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["schema"] == project.PROJECT_SCHEMA_V2
    saved = persisted["snapshot"]
    assert all(key not in saved for key in ("w", "h", "d"))
    cfg = saved["workspace"]["box_body_structure"]["configs"]["three_piece_side_back_split"]
    assert "back_panel_mode" not in cfg
    bay1 = saved["receiving_layout"]["sets"][0]["bays"][0]
    assert bay1["width"] == pytest.approx(810)
    assert bay1["height"] == pytest.approx(1700)
    assert bay1["depth"] == pytest.approx(420)
    assert bay1["back_panel_mode"] == "BACK_OPENING"
    assert persisted["final_geometry"] == {}

    loaded = project.read_project(path)
    assert loaded["schema"] == project.PROJECT_SCHEMA_V2
    runtime = loaded["snapshot"]
    assert runtime["w"] == pytest.approx(810)
    assert runtime["h"] == pytest.approx(1700)
    assert runtime["d"] == pytest.approx(420)
    assert back_panel_mode(runtime["workspace"]["box_body_structure"]) is BackPanelMode.BACK_OPENING

    path2 = project.write_project(tmp_path / "resaved.p6fold", loaded)
    persisted2 = json.loads(path2.read_text(encoding="utf-8"))
    assert persisted2["schema"] == project.PROJECT_SCHEMA_V2
    assert all(key not in persisted2["snapshot"] for key in ("w", "h", "d"))
    cfg2 = persisted2["snapshot"]["workspace"]["box_body_structure"]["configs"]["three_piece_side_back_split"]
    assert "back_panel_mode" not in cfg2
    assert persisted2["snapshot"]["receiving_layout"] == saved["receiving_layout"]


def test_non_receiving_projects_remain_v1(tmp_path):
    payload = {
        "schema": project.PROJECT_SCHEMA_V1,
        "snapshot": {"model": "金庫型", "w": 400.0, "h": 600.0, "d": 250.0},
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "vault.p6fold", payload)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["schema"] == project.PROJECT_SCHEMA_V1
    assert persisted["snapshot"]["w"] == pytest.approx(400.0)


def test_v2_is_explicitly_distinct_from_legacy_v1_reader_contract(tmp_path):
    snapshot = _receiving_snapshot()
    path = project.write_project(
        tmp_path / "receiving-v2.p6fold",
        {"schema": project.PROJECT_SCHEMA_V1, "snapshot": snapshot, "final_geometry": {}},
    )
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert project.PROJECT_SCHEMA_V2 != project.PROJECT_SCHEMA_V1
    assert persisted["schema"] == project.PROJECT_SCHEMA_V2
    # The production reader before #1111 used exact equality with V1; the new
    # persisted marker therefore fails closed in that old reader instead of
    # being silently interpreted as one cabinet.
    assert persisted["schema"] != project.PROJECT_SCHEMA_V1


def _two_bay_layout():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    set1 = layout["sets"][0]
    set1["bays"].append(
        {
            "stable_id": "receiving:set:1:bay:2",
            "width": 800.0,
            "height": 1600.0,
            "depth": 350.0,
            "back_panel_mode": "FULL",
        }
    )
    set1["joints"] = [
        {
            "stable_id": "receiving:set:1:joint:1",
            "left_bay_id": "receiving:set:1:bay:1",
            "right_bay_id": "receiving:set:1:bay:2",
            "depth_alignment": "FRONT",
            "height_alignment": "BOTTOM",
        }
    ]
    return layout


@pytest.mark.parametrize(
    "mutator, match",
    [
        (lambda row: row["sets"][0].update(joints=[]), "joint_count"),
        (lambda row: row["sets"][0]["joints"][0].update(left_bay_id="missing"), "endpoints"),
        (lambda row: row["sets"][0]["joints"][0].update(right_bay_id="receiving:set:1:bay:1"), "endpoints"),
        (lambda row: row["sets"][0]["bays"][1].update(stable_id="receiving:set:1:bay:1"), "duplicate"),
    ],
)
def test_layout_adjacency_and_identity_invariants_fail_closed(mutator, match):
    layout = _two_bay_layout()
    mutator(layout)
    with pytest.raises(ValueError, match=match):
        normalize_receiving_layout(layout)


def test_cross_set_joint_endpoint_fails_closed():
    layout = _two_bay_layout()
    layout["sets"].append(
        {
            "stable_id": "receiving:set:2",
            "bays": [
                {
                    "stable_id": "receiving:set:2:bay:1",
                    "width": 800.0,
                    "height": 1600.0,
                    "depth": 350.0,
                    "back_panel_mode": "FULL",
                }
            ],
            "joints": [],
        }
    )
    layout["sets"][0]["joints"][0]["right_bay_id"] = "receiving:set:2:bay:1"
    with pytest.raises(ValueError, match="endpoints"):
        normalize_receiving_layout(layout)


def test_derived_layout_fields_never_survive_canonicalization():
    layout = _two_bay_layout()
    layout["sets"][0]["bays"][0]["left_locked"] = True
    layout["sets"][0]["joints"][0]["effective_D"] = 123
    normalized = normalize_receiving_layout(layout)
    assert "left_locked" not in normalized["sets"][0]["bays"][0]
    assert "effective_D" not in normalized["sets"][0]["joints"][0]
