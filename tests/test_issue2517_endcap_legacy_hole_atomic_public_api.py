"""#2517: canonical Head/Tail Feature readback is one public Engine candidate."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import (
    CircleFeature, RectFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_features import feature_to_legacy_hole
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import lifecycle as gui


class _Projected(Exception):
    """Stop the real project-restore flow after its legacy-cache readback."""


def _head():
    return CircleFeature(
        diameter=10.0, anchor=FeatureAnchor.TOP_LEFT,
        offset=Vec2(12.0, -8.0), source_type="圓形",
    )


def _tail():
    return RectFeature(
        width=24.0, height=12.0, anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(2.0, 4.0), source_type="方形",
    )


def _host():
    return SimpleNamespace(
        workspace_controller=SimpleNamespace(
            reset_receiving_mode_session=lambda: None,
        ),
        _reset_manual_corner_parameter_locks=lambda: None,
        baseline_var=SimpleNamespace(get=lambda: "金庫型"),
        _apply_original_fold_designer_snapshot=lambda _source: None,
        surface_features={},
        head_holes=[{"id": "old-head"}],
        tail_holes=[{"id": "old-tail"}],
        w_var=SimpleNamespace(get=lambda: "800"),
        d_var=SimpleNamespace(get=lambda: "350"),
        _apply_existing_parts_from_fold_workspace=lambda *_args, **_kw: (_ for _ in ()).throw(_Projected),
    )


def _snapshot(head=None, tail=None):
    return {
        "model": "金庫型", "w": 800.0, "h": 1200.0,
        "d": 350.0, "t": 2.0, "fw": 25.0,
        "part_features": {
            "head": [_head()] if head is None else head,
            "tail": [_tail()] if tail is None else tail,
        },
    }


def test_public_projection_root_and_facade_are_same_engine_callable():
    assert (
        ae_engine.project_operator_endcap_legacy_hole_rows
        is api.project_operator_endcap_legacy_hole_rows
    )


def test_head_tail_finished_face_projection_matches_original_owner_without_mutation():
    source = {"head": [_head()], "tail": [_tail()], "door": [_head()]}
    before = deepcopy(source)
    projected = api.project_operator_endcap_legacy_hole_rows(
        source, width="800", depth="350",
    )
    assert projected == {
        "head": [feature_to_legacy_hole(_head(), 800.0, 350.0)],
        "tail": [feature_to_legacy_hole(_tail(), 800.0, 350.0)],
    }
    assert projected["head"][0]["x"] == 12.0
    assert projected["head"][0]["y"] == 342.0
    assert projected["tail"][0]["x"] == 402.0
    assert projected["tail"][0]["y"] == 179.0
    assert source == before
    projected["head"][0]["params"]["diameter"] = 99.0
    assert source == before


@pytest.mark.parametrize(("source", "expected_keys"), (
    ({"head": [_head()]}, ("head",)),
    ({"tail": [_tail()]}, ("tail",)),
    ({"head": [], "tail": []}, ("head", "tail")),
    ({"door": [_head()]}, ()),
))
def test_only_supplied_endcap_roles_are_projected(source, expected_keys):
    original = deepcopy(source)
    rows = api.project_operator_endcap_legacy_hole_rows(
        source, width=800, depth=350,
    )
    assert tuple(rows) == expected_keys
    assert source == original


@pytest.mark.parametrize("width,depth", (
    (True, 350), (0, 350), (-1, 350), (float("nan"), 350),
    (float("inf"), 350), (800, None), (800, -2),
))
def test_invalid_physical_dimensions_fail_closed(width, depth):
    source = {"head": [_head()], "tail": [_tail()]}
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.project_operator_endcap_legacy_hole_rows(
            source, width=width, depth=depth,
        )
    assert source == before


def test_second_endcap_failure_does_not_publish_first_endcap_candidate():
    source = {"head": [_head()], "tail": [_tail(), object()]}
    head_before = deepcopy(source["head"])
    with pytest.raises(ValueError, match="tail physical Feature"):
        api.project_operator_endcap_legacy_hole_rows(
            source, width=800, depth=350,
        )
    assert source["head"] == head_before


def test_nonfinite_physical_feature_position_rejected_without_source_mutation():
    source = {
        "head": [_head()],
        "tail": [CircleFeature(
            diameter=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(float("inf"), 0),
        )],
    }
    before = deepcopy(source)
    with pytest.raises(ValueError, match="tail finished-face"):
        api.project_operator_endcap_legacy_hole_rows(
            source, width=800, depth=350,
        )
    assert source == before


def test_real_main_gui_project_restore_updates_both_legacy_2d_caches(monkeypatch):
    host = _host()
    snapshot = _snapshot()
    before = deepcopy(snapshot)
    called = []
    original = api.project_operator_endcap_legacy_hole_rows

    def spy(source, *, width, depth):
        called.append((deepcopy(source), width, depth))
        return original(source, width=width, depth=depth)

    monkeypatch.setattr(api, "project_operator_endcap_legacy_hole_rows", spy)
    with pytest.raises(_Projected):
        gui._apply_phase6_project_snapshot(host, snapshot)
    assert len(called) == 1
    assert called[0][0] == snapshot["part_features"]
    assert called[0][1:] == (800.0, 350.0)
    assert host.head_holes == [feature_to_legacy_hole(_head(), 800, 350)]
    assert host.tail_holes == [feature_to_legacy_hole(_tail(), 800, 350)]
    assert snapshot == before


def test_real_main_gui_restore_never_partially_commits_head_if_tail_invalid():
    host = _host()
    source = _snapshot(tail=[object()])
    original_head = deepcopy(host.head_holes)
    original_tail = deepcopy(host.tail_holes)
    with pytest.raises(_Projected):
        gui._apply_phase6_project_snapshot(host, source)
    assert host.head_holes == original_head
    assert host.tail_holes == original_tail


def test_real_quantity_version_switch_preserves_both_old_caches_on_invalid_tail(monkeypatch):
    import phase6_custom_parts
    import phase6_quantity_model
    import phase6_sync_envelope

    monkeypatch.setattr(phase6_custom_parts, "custom_part_only_change", lambda *_: False)
    monkeypatch.setattr(phase6_quantity_model, "quantity_only_change", lambda *_: True)
    monkeypatch.setattr(phase6_sync_envelope, "navigation_only_change", lambda *_: False)

    host = _host()
    source_features = {"head": [_head()], "tail": [object()]}
    calls = []
    owner = api.project_operator_endcap_legacy_hole_rows

    def delegated(features, *, width, depth):
        calls.append((features, width, depth))
        return owner(features, width=width, depth=depth)

    monkeypatch.setattr(api, "project_operator_endcap_legacy_hole_rows", delegated)
    host.workspace_controller = SimpleNamespace(
        commit_workspace=lambda *_: None,
        part_features_snapshot=lambda: source_features,
    )
    captures = []
    host.project_controller = SimpleNamespace(capture_committed=captures.append)
    host._compose_phase6_project_snapshot_from_main_gui = lambda: {"restored": True}
    host._fold_designer_live_sync_guard = False
    host._phase6_last_fold_designer_revision = 1
    host._phase6_last_fold_designer_fingerprint = "old"
    host._phase6_last_fold_designer_live_payload = None
    host._phase6_update_scheduler = None
    old_head, old_tail = deepcopy((host.head_holes, host.tail_holes))
    payload = {
        "origin": "fold_designer",
        "revision": 2,
        "fingerprint": "new",
        "workspace": {},
        "quantity": {"selected_version_id": "v2", "versions": []},
    }
    assert gui._apply_fold_designer_live_snapshot(host, payload) is True
    assert len(calls) == 1
    assert calls[0][0] == source_features
    assert (host.head_holes, host.tail_holes) == (old_head, old_tail)
    assert captures == [{"restored": True}]
    assert host._fold_designer_live_sync_guard is False


def test_actual_p6fold_save_reload_rehydrates_same_two_engine_endcap_2d_sources(tmp_path):
    import phase6_project_file as project

    snapshot = _snapshot()
    original = deepcopy(snapshot)
    target = project.write_project(
        tmp_path / "endcap-legacy-cache.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = project.read_project(target)["snapshot"]
    saved_sources = restored["part_features"]
    projected = api.project_operator_endcap_legacy_hole_rows(
        saved_sources, width=restored["w"], depth=restored["d"],
    )
    assert projected == {
        "head": [feature_to_legacy_hole(_head(), 800, 350)],
        "tail": [feature_to_legacy_hole(_tail(), 800, 350)],
    }
    assert snapshot == original


def test_all_three_main_gui_legacy_cache_writes_delegate_to_public_engine():
    module = inspect.getsource(gui)
    assert module.count("manufacturing_api.project_operator_endcap_legacy_hole_rows(") == 3
    assert "feature_to_legacy_hole(" not in module
    assert "    feature_to_legacy_hole," not in module
