# -*- coding: utf-8 -*-
"""#2517: both Receiving Quantity inner-Door GUI entries share one Engine commit.

True original CSV source and selected version identity are checked before any
live source write. No false physical X, alternate GUI writer or preview grant.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel, SCHEMA_V2
from ae_engine.sheetmetal_geometry import Vec2
from phase6_receiving_modes import fresh_receiving_mode
from tests.test_issue1503_csv_committed_config import PART, _feature, _config


def _project():
    snapshot = fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350, "t": 2},
    )
    model = QuantityModel.from_payload(snapshot["quantity"])
    return snapshot, model


def test_public_root_and_facade_share_exact_transaction_owner():
    assert ae_engine.commit_receiving_quantity_inner_door_confirm is (
        api.commit_receiving_quantity_inner_door_confirm
    )
    assert "commit_receiving_quantity_inner_door_confirm" in ae_engine.__all__


def test_real_original_csv_2d_source_atomically_commits_selected_quantity_version():
    source, model = _project()
    first = model.selected_version_id
    second = model.add_version()
    source["quantity"] = model.snapshot()
    before = deepcopy(source)
    before_model = deepcopy(model.snapshot())
    original_config = _config()
    features = [_feature(0), _feature(1)]
    detached, typed = api.preview_quantity_inner_door_confirm(
        source, model, PART, features, original_config,
    )
    assert source == before and model.snapshot() == before_model

    committed, accepted = api.commit_receiving_quantity_inner_door_confirm(
        source, model, PART, features, original_config,
    )
    assert accepted == typed and committed == detached == source
    assert committed is not source
    assert model.snapshot() == source["quantity"] == detached["quantity"]
    assert source["quantity"]["schema"] == SCHEMA_V2
    rows = {item["version_id"]: item for item in model.snapshot()["versions"]}
    assert rows[first]["nfb_config_submitted"] is False
    assert rows[second]["nfb_config_submitted"] is True
    assert len(rows[second]["nfb_config"]["holes"]) == 2
    assert all(hole["manual_x_state"] == "UNVERIFIED_BASIS"
               and hole["manual_x_mm"] is None
               for hole in rows[second]["nfb_config"]["holes"])
    assert "receiving_layout" in source
    assert "_receiving_runtime_selection" not in source


def test_original_native_only_confirm_updates_common_box_without_fabricating_nfb():
    source, model = _project()
    before = model.snapshot()
    committed, typed = api.commit_receiving_quantity_inner_door_confirm(
        source, model, PART, [], _config(),
    )
    assert typed is None
    assert source == committed
    assert source["receiving_quantity_box"]["inner_door_layers"] == 2
    assert source["quantity"] == model.snapshot() == before
    assert all("nfb_config_submitted" not in row
               for row in model.snapshot()["versions"])


@pytest.mark.parametrize("fault", ("invalid-box", "wrong-family", "bad-hole", "bad-mode"))
def test_bad_physical_family_or_original_csv_fails_before_both_source_writes(fault):
    source, model = _project()
    feature = _feature(0)
    config = _config()
    features = [feature, _feature(1)]
    if fault == "invalid-box":
        source["receiving_quantity_box"]["w"] = float("nan")
    elif fault == "wrong-family":
        source["model"] = "金庫型"
    elif fault == "bad-hole":
        features[0] = replace(feature, points=(
            Vec2(feature.points[0].x + 4.0, feature.points[0].y),
        ) + feature.points[1:])
    else:
        source["active_mode"] = "set_bay"
    old_snapshot, old_model, old_config = (
        deepcopy(source), deepcopy(model.snapshot()), deepcopy(config))
    with pytest.raises((ValueError, TypeError)):
        api.commit_receiving_quantity_inner_door_confirm(
            source, model, PART, features, config,
        )
    assert source == old_snapshot
    assert model.snapshot() == old_model
    assert config == old_config


def test_original_detached_preview_refuses_wrong_family_before_source_save():
    source, model = _project()
    source["model"] = "金庫型"
    old = deepcopy(source)
    with pytest.raises(ValueError, match="RECEIVING_QUANTITY_INNER_DOOR_FAMILY_REQUIRED"):
        api.preview_quantity_inner_door_confirm(
            source, model, PART, [_feature(0), _feature(1)], _config(),
        )
    assert source == old
    assert model.snapshot() == old["quantity"]


def test_quantity_change_notification_failure_restores_both_state_sources():
    source, _ = _project()
    original_snapshot = deepcopy(source)
    calls = []

    def notify():
        # The callback sees the complete new project and Quantity owner,
        # not an old half-committed synthetic Bay or stale version source.
        calls.append(source["quantity"]["schema"])
        assert source["quantity"] == model.snapshot()
        raise RuntimeError("view refresh failed")

    model = QuantityModel.from_payload(source["quantity"], on_change=notify)
    with pytest.raises(RuntimeError, match="view refresh failed"):
        api.commit_receiving_quantity_inner_door_confirm(
            source, model, PART, [_feature(0), _feature(1)], _config(),
        )
    assert calls == [SCHEMA_V2]
    assert source == original_snapshot
    assert model.snapshot() == original_snapshot["quantity"]
    # Rollback must not invoke the failed notification a second time.
    assert len(calls) == 1


def test_projected_quantity_drift_is_refused_without_mutation(monkeypatch):
    from ae_engine import receiving_nfb_csv_committed_config as owner

    source, model = _project()
    untouched_source = deepcopy(source)
    untouched_quantity = deepcopy(model.snapshot())
    original = owner.preview_quantity_inner_door_confirm

    def forged(*args, **kwargs):
        projected, typed = original(*args, **kwargs)
        projected["quantity"]["selected_version_id"] = "quantity-v777"
        return projected, typed

    monkeypatch.setattr(owner, "preview_quantity_inner_door_confirm", forged)
    with pytest.raises(ValueError, match="PROJECTED_VERSION_DRIFT"):
        api.commit_receiving_quantity_inner_door_confirm(
            source, model, PART, [_feature(0), _feature(1)], _config(),
        )
    assert source == untouched_source
    assert model.snapshot() == untouched_quantity


def test_both_real_gui_entries_contain_no_live_quantity_or_snapshot_nfb_writer():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gui_modules/application/fold_designer_composition_receiving.py").read_text(
        encoding="utf-8",
    )
    branch = source.split("def confirmed(actual_part, features, staged_config):", 1)[1]
    branch = branch.split('if mode == "single":', 1)[0]
    direct = (root / "gui_modules/application/receiving_inner_door_hole_editor.py").read_text(
        encoding="utf-8",
    )
    direct = direct.split('elif mode == "quantity":', 1)[1].split(
        'else:', 1,
    )[0]
    for code in (branch, direct):
        assert "manufacturing_api.commit_receiving_quantity_inner_door_confirm(" in code
        assert "quantity.set_version_nfb_config(" not in code
        assert "current.clear()" not in code
        assert "current.update(projected)" not in code
        assert "_phase6_input_snapshot.clear()" not in code
        assert "_phase6_input_snapshot.update(" not in code
