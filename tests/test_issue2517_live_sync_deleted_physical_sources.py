"""#2517: an authored removal must not disappear from the live-sync delta.

The full Fold Designer payload carries the canonical state.  Delta is
transport evidence, not a second geometry/feature source of truth.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from gui_modules.application import fold_designer_composition_state as gui
from phase6_sync_envelope import (
    actual_delta, mapping_delta, materialize_sync_value,
    plan_live_sync_envelope, stable_fingerprint,
)


def _plan(before, after, *, host_relief_present=False, host_relief=None, force=False):
    return plan_live_sync_envelope(
        current_state=after,
        previous_state=before,
        previous_fingerprint=stable_fingerprint(before),
        current_revision=3,
        active_transaction_id="",
        host_relief_present=host_relief_present,
        host_relief={} if host_relief is None else host_relief,
        force=force,
    )


@pytest.mark.parametrize("before,after,expected", [
    (
        {"workspace": {"part_features": {
            "door": [{"type": "circle", "x": 12}],
        }}},
        {"workspace": {"part_features": {}}},
        {"workspace": {"part_features": {}}},
    ),
    (
        {"workspace": {"part_features": {
            "door": [{"type": "circle", "x": 12}],
            "head": [{"type": "circle", "x": 20}],
        }}},
        {"workspace": {"part_features": {
            "head": [{"type": "circle", "x": 20}],
        }}},
        {"workspace": {"part_features": {
            "head": [{"type": "circle", "x": 20}],
        }}},
    ),
    (
        {"assembly_relief": {"enabled": True, "parts": {"head": {"cut": True}}}},
        {"assembly_relief": {}},
        {"assembly_relief": {}},
    ),
    (
        {"settings": {"w": 800.5, "d": 350.25}},
        {"settings": {"w": 800.5}},
        {"settings": {"w": 800.5}},
    ),
])
def test_nested_removal_projects_authoritative_replacement_not_false_noop(
    before, after, expected,
):
    originals = deepcopy((before, after))
    assert mapping_delta(before, after) == expected
    plan = _plan(before, after)
    assert plan.should_publish is True
    assert plan.next_revision == 4
    assert materialize_sync_value(plan.delta) == expected
    assert materialize_sync_value(plan.payload)["revision"] == 4
    assert json.loads(json.dumps(materialize_sync_value(plan.payload)))["workspace" if "workspace" in after else next(iter(after))] == after[next(iter(after))]
    assert (before, after) == originals


def test_real_hole_feature_delete_publishes_one_complete_snapshot_then_no_echo():
    hole = {"type": "circle", "x": 40.125, "y": 20.5, "diameter": 12}
    before = {
        "model": "受電箱",
        "workspace": {"part_features": {"door": [hole]}},
        "settings": {"w": 820.25, "h": 1600.5, "d": 350.75},
    }
    after = {
        "model": "受電箱",
        "workspace": {"part_features": {}},
        "settings": {"w": 820.25, "h": 1600.5, "d": 350.75},
    }
    plan = _plan(before, after)
    assert plan.should_publish is True
    assert plan.delta == {"workspace": {"part_features": {}}}
    new_source = json.loads(json.dumps(materialize_sync_value(plan.payload)))
    assert new_source["workspace"]["part_features"] == {}
    assert new_source["settings"] == after["settings"]
    assert new_source["revision"] == 4
    again = plan_live_sync_envelope(
        current_state=after,
        previous_state=after,
        previous_fingerprint=stable_fingerprint(after),
        current_revision=4,
        active_transaction_id="",
        host_relief_present=False, host_relief={},
        force=False,
    )
    assert not again.should_publish
    assert again.next_revision == 4
    assert again.payload is None


def test_forced_host_relief_clear_is_not_lost_as_empty_mapping_delta():
    canonical = {
        "settings": {"w": 820.25},
        "assembly_relief": {},
    }
    saved_host_relief = {"enabled": True, "parts": {"head": {"stale": True}}}
    plan = _plan(
        canonical, canonical,
        host_relief_present=True, host_relief=saved_host_relief, force=True,
    )
    assert plan.should_publish is True
    assert plan.next_revision == 4
    assert plan.delta == {"assembly_relief": {}}
    assert plan.host_relief_repair == {}
    assert materialize_sync_value(plan.payload)["assembly_relief"] == {}


def test_real_fold_publisher_repairs_cleared_relief_and_preserves_one_revision():
    canonical = {"settings": {"w": 820.25}, "assembly_relief": {}}
    captured = []
    app = SimpleNamespace(
        _live_sync_callback=lambda payload: captured.append(deepcopy(payload)),
        _phase6_live_sync_guard=False,
        _phase6_initializing=False,
        _phase6_sync_ready=True,
        _phase6_sync_revision=3,
        _phase6_last_live_state=deepcopy(canonical),
        _phase6_last_live_fingerprint=stable_fingerprint(canonical),
        _phase6_input_snapshot={
            "assembly_relief": {"enabled": True, "parts": {"head": {"stale": True}}},
        },
        baseline_model_var=object(),
        designer_workspace=object(),
    )
    owner = SimpleNamespace(app=app, corner_transaction_payload=lambda _: deepcopy(canonical))
    assert gui.publish_live_state(owner, None, force=True) is True
    assert len(captured) == 1
    assert captured[0]["revision"] == 4
    assert captured[0]["delta"] == {"assembly_relief": {}}
    assert captured[0]["assembly_relief"] == {}
    assert app._phase6_input_snapshot["assembly_relief"] == {}
    assert app._phase6_sync_revision == 4
    assert app._phase6_live_sync_guard is False
    assert gui.publish_live_state(owner, None, force=True) is False
    assert len(captured) == 1


def test_root_level_removal_only_does_not_suppress_full_state_publication():
    before = {"workspace": {"part_features": {"door": [{"x": 20}]}}}
    after = {}
    plan = _plan(before, after)
    assert plan.should_publish is True
    assert plan.next_revision == 4
    assert plan.delta == {}
    published = materialize_sync_value(plan.payload)
    assert published["origin"] == "fold_designer"
    assert published["revision"] == 4
    unchanged = plan_live_sync_envelope(
        current_state=after,
        previous_state=after,
        previous_fingerprint=stable_fingerprint(after),
        current_revision=4, active_transaction_id="",
        host_relief_present=False, host_relief={},
        force=False,
    )
    assert unchanged.should_publish is False


def test_stale_fingerprint_alone_never_forges_a_physical_change():
    source = {"settings": {"w": 820.25}, "assembly_relief": {}}
    plan = plan_live_sync_envelope(
        current_state=source,
        previous_state=deepcopy(source),
        previous_fingerprint="stale metadata",
        current_revision=4,
        active_transaction_id="",
        host_relief_present=False, host_relief={},
        force=False,
    )
    assert plan.should_publish is False
    assert plan.next_revision == 4


def test_same_value_never_writes_new_snapshot_and_source_stays_pure():
    before = {"settings": {"w": 820.25}, "workspace": {"part_features": {}}}
    after = deepcopy(before)
    original = deepcopy((before, after))
    assert mapping_delta(before, after) == {}
    plan = _plan(before, after)
    assert plan.should_publish is False
    assert plan.next_revision == 3
    assert plan.delta == {}
    assert plan.payload is None
    assert (before, after) == original


def test_gui_transport_has_no_manufacturing_feature_reconstruction():
    source = inspect.getsource(actual_delta)
    assert "if any(key not in after for key in before):" in source
    assert "deepcopy(dict(after))" in source
    assert "feature_finished_point" not in source
    assert "ManufacturingContext" not in source
    assert "ezdxf" not in source
