"""v1.5 core acceptance: feature-only versions and manual project persistence."""
import json
from copy import deepcopy

import pytest

from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def feature(offset=0):
    return CircleFeature(diameter=8, anchor=FeatureAnchor.PANEL_CENTER,
                         offset=Vec2(offset, 3), layer="CUTTING")


def legacy_snapshot():
    return {"model": "金庫型", "w": 400, "h": 600, "d": 250, "t": 2,
            "existing_parts": ["box_body", "head", "tail", "door"],
            "part_features": {"head": [feature(1)], "tail": [feature(2)],
                              "door": [feature(3)]}}


def test_legacy_project_becomes_one_version_without_losing_holes(tmp_path):
    path = tmp_path / "legacy.p6fold"
    from phase6_project_file import _encode
    path.write_text(json.dumps(_encode({"schema": PROJECT_SCHEMA,
                                       "snapshot": legacy_snapshot()})), encoding="utf-8")
    loaded = read_project(path)["snapshot"]
    assert loaded["active_mode"] == "quantity"
    quantity = loaded["quantity"]
    assert len(quantity["versions"]) == 1
    row = quantity["versions"][0]
    assert row["piece_count"] == 1
    assert row["head_features"] == [feature(1)]
    assert row["tail_features"] == [feature(2)]
    assert loaded["part_features"]["door"] == [feature(3)]
    assert loaded["w"] == 400


def test_insert_after_selection_deep_copy_and_delete_selection():
    from phase6_quantity_model import QuantityModel
    model = QuantityModel(head_features=[{"nested": [1]}])
    first = model.selected_version_id
    second = model.add_version()
    third = model.add_version()
    model.select(first)
    middle = model.add_version()
    assert [v["version_id"] for v in model.snapshot()["versions"]] == [
        first, middle, second, third]
    assert model.selected_version_id == middle
    assert model.total_piece_count == 4
    values = model.features_for("head")
    values[0]["nested"].append(2)
    model.set_features("head", values)
    model.select(first)
    assert model.features_for("head") == [{"nested": [1]}]
    model.select(middle)
    before = model.snapshot()
    assert model.delete_selected(confirmed=False) is False
    assert model.snapshot() == before
    assert model.delete_selected(confirmed=True) is True
    assert model.selected_version_id == second
    model.select(third)
    model.delete_selected(confirmed=True)
    assert model.selected_version_id == second
    restored = QuantityModel.from_payload(model.snapshot())
    restored.select(first)
    new_id = restored.add_version()
    assert new_id not in {first, middle, second, third}
    assert restored.selected_version_id == new_id


@pytest.mark.parametrize("value", [0, -1, 1.5, 1.0, True, False, "", "1.5", "0", None])
def test_invalid_count_does_not_change_state(value):
    from phase6_quantity_model import QuantityModel
    model = QuantityModel()
    before = model.snapshot()
    with pytest.raises(ValueError):
        model.set_piece_count(value)
    assert model.snapshot() == before


def test_counts_and_last_version_protection():
    from phase6_quantity_model import QuantityModel
    model = QuantityModel()
    first = model.selected_version_id
    model.set_piece_count(30)
    model.add_version()
    assert model.selected_piece_count == 1
    model.set_piece_count("20")
    assert model.version_count == 2
    assert model.total_piece_count == 50
    model.delete_selected(confirmed=True)
    assert model.selected_version_id == first
    before = model.snapshot()
    assert model.delete_selected(confirmed=True) is False
    assert model.snapshot() == before


def test_three_distinct_versions_save_reload_and_unsaved_count(tmp_path):
    ws = Phase6DesignerWorkspace.from_snapshot(legacy_snapshot())
    q = ws.quantity_model
    ids = []
    for index in range(3):
        if index:
            q.add_version()
        ids.append(q.selected_version_id)
        ws.stash_features("head", [feature(10 + index)])
        ws.stash_features("tail", [feature(20 + index)])
        q.set_piece_count(4 + index)
    snapshot = {**legacy_snapshot(), **ws.snapshot()}
    path = write_project(tmp_path / "versions", {"schema": PROJECT_SCHEMA, "snapshot": snapshot})
    saved_bytes = path.read_bytes()
    q.set_piece_count(7)
    assert q.selected_piece_count == 7
    assert path.read_bytes() == saved_bytes
    loaded = read_project(path)["snapshot"]
    restored = Phase6DesignerWorkspace.from_snapshot(loaded)
    assert restored.quantity_model.selected_piece_count == 6
    assert restored.quantity_model.total_piece_count == 15
    for index, version_id in enumerate(ids):
        restored.quantity_model.select(version_id)
        assert restored.features_for("head") == [feature(10 + index)]
        assert restored.features_for("tail") == [feature(20 + index)]
    assert restored.features_for("door") == [feature(3)]
    assert all("w" not in row for row in loaded["quantity"]["versions"])
    assert loaded["w"] == 400


def test_corrupt_versions_fail_before_overwriting_saved_project(tmp_path):
    from phase6_quantity_model import QuantityModel
    q = QuantityModel().snapshot()
    path = write_project(tmp_path / "safe", {"schema": PROJECT_SCHEMA, "snapshot": legacy_snapshot()})
    previous = path.read_bytes()
    for mutation in ("count", "duplicate", "shape", "empty", "selection", "counter"):
        bad = deepcopy(q)
        if mutation == "count":
            bad["versions"][0]["piece_count"] = 0
        elif mutation == "duplicate":
            bad["versions"].append(deepcopy(bad["versions"][0]))
        elif mutation == "shape":
            bad["versions"][0]["w"] = 700
        elif mutation == "empty":
            bad["versions"] = []
        elif mutation == "selection":
            bad["selected_version_id"] = "missing"
        else:
            bad["next_version_number"] = 1
        with pytest.raises(ValueError):
            write_project(path, {"schema": PROJECT_SCHEMA,
                                 "snapshot": {**legacy_snapshot(), "quantity": bad}})
        assert path.read_bytes() == previous


def test_project_persists_active_quantity_only(tmp_path):
    from phase6_quantity_model import QuantityModel
    snapshot = {**legacy_snapshot(), "active_mode": "quantity",
                "quantity": QuantityModel().snapshot(),
                "_mode_buffers": {"set_bay": {"secret": "not saved"}}}
    path = write_project(tmp_path / "active", {"schema": PROJECT_SCHEMA, "snapshot": snapshot})
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "_mode_buffers" not in raw["snapshot"]
    assert "quantity" in raw["snapshot"]
    assert "head" not in raw["snapshot"]["part_features"]
    loaded = read_project(path)["snapshot"]
    assert loaded["part_features"]["head"] == []


def test_receiving_legacy_keeps_set_bay_mode():
    from phase6_quantity_model import normalize_quantity_snapshot
    snapshot = {"model": "受電箱", "w": 900, "h": 1700, "d": 400}
    normalized = normalize_quantity_snapshot(snapshot)
    assert normalized["active_mode"] == "set_bay"
    assert "quantity" not in normalized
    assert normalized["w"] == 900


def test_workspace_model_is_dirty_on_committed_edit_and_snapshot_is_isolated():
    ws = Phase6DesignerWorkspace.from_snapshot(legacy_snapshot())
    assert ws.dirty is False
    q = ws.quantity_model
    q.set_piece_count(7)
    assert ws.dirty is True
    dumped = ws.snapshot()
    dumped["quantity"]["versions"][0]["piece_count"] = 99
    assert q.selected_piece_count == 7
    ws.mark_clean()
    before = ws.snapshot()
    with pytest.raises(ValueError):
        q.select("unknown")
    assert ws.snapshot() == before
    assert ws.dirty is False


def test_main_workspace_commit_preserves_all_versions_and_clear_drops_old_project():
    from phase6_workspace_controller import Phase6WorkspaceController
    ws = Phase6DesignerWorkspace.from_snapshot(legacy_snapshot())
    ws.quantity_model.set_piece_count(30)
    ws.quantity_model.add_version()
    ws.quantity_model.set_piece_count(20)
    committed = Phase6WorkspaceController()
    committed.commit_workspace(ws.snapshot())
    assert committed.quantity_model.total_piece_count == 50
    cloned = committed.workspace_snapshot()
    cloned["quantity"]["versions"][0]["piece_count"] = 500
    assert committed.quantity_model.total_piece_count == 50
    committed.replace_part_features({"head": [feature(9)], "door": [feature(3)]})
    assert committed.quantity_model.features_for("head") == [feature(9)]
    first = committed.quantity_model.snapshot()["versions"][0]["version_id"]
    committed.quantity_model.select(first)
    assert committed.part_features_snapshot()["head"] == [feature(1)]
    committed.clear_authoritative_workspace()
    assert committed.quantity_model is None
    assert "quantity" not in committed.workspace_snapshot()


def test_real_main_gui_load_then_save_preserves_three_versions(tmp_path):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        base = app._make_original_fold_designer_snapshot()
        ws = Phase6DesignerWorkspace.from_snapshot(base)
        q = ws.quantity_model
        for index in range(3):
            if index:
                q.add_version()
            ws.stash_features("head", [feature(index)])
            ws.stash_features("tail", [feature(index + 1)])
            q.set_piece_count(index + 4)
        source = write_project(tmp_path / "three", {
            "schema": PROJECT_SCHEMA, "snapshot": {**base, **ws.snapshot()}})
        loaded = read_project(source)["snapshot"]
        app._apply_phase6_project_snapshot(loaded)
        current = app._compose_phase6_project_snapshot_from_main_gui()
        assert current["quantity"] == loaded["quantity"]
        assert len(current["quantity"]["versions"]) == 3
        saved = write_project(tmp_path / "resaved", {"schema": PROJECT_SCHEMA, "snapshot": current})
        assert read_project(saved)["snapshot"]["quantity"] == loaded["quantity"]
    finally:
        root.destroy()
