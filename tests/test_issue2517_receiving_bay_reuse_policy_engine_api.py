"""#2517: Receiving preview source reuse is decided by the Engine API."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_bay_preview_source import (
    ReceivingBayPreviewReusePolicy, plan_receiving_bay_preview_reuse_policy,
)
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays


def _snapshot(model="受電箱", mode="set_bay"):
    return {
        "model": model, "active_mode": mode,
        "receiving_layout": resize_receiving_bays(
            new_receiving_layout(width=800, height=1600, depth=350),
            set_index=0, bay_count=4,
        ),
    }


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_committed_receiving_bay_policy_is_engine_owned(family):
    snapshot = _snapshot(family)
    before = deepcopy(snapshot)
    result = api.plan_receiving_bay_preview_reuse_policy(
        snapshot, bay_index=2, available_parts=("box_body", "head"),
    )
    assert isinstance(result, ReceivingBayPreviewReusePolicy)
    assert result == plan_receiving_bay_preview_reuse_policy(
        snapshot, bay_index=2, available_parts=("box_body", "head"),
    )
    assert result.receiving_set_bay
    assert result.allow_upstream_translation
    assert result.allow_suffix_topology_reuse
    assert not result.requires_live_custom_catalog
    assert snapshot == before


@pytest.mark.parametrize("family,mode", [
    ("金庫型", "set_bay"), ("unsupported", "set_bay"),
    ("受電箱", "quantity"), ("RECEIVING", "quantity"),
])
def test_other_family_or_quantity_never_reuse_receiving_bay_source(family, mode):
    policy = api.plan_receiving_bay_preview_reuse_policy(
        _snapshot(family, mode), bay_index=3,
    )
    assert not policy.receiving_set_bay
    assert not policy.allow_upstream_translation
    assert not policy.allow_suffix_topology_reuse


@pytest.mark.parametrize("index,candidate", [
    (0, False), (1, False), (2, True), (3, True), (True, False),
])
def test_candidate_and_near_bays_must_retain_source_dependencies(index, candidate):
    result = api.plan_receiving_bay_preview_reuse_policy(
        _snapshot(), bay_index=index, candidate=candidate,
    )
    assert not result.allow_upstream_translation
    assert result.allow_suffix_topology_reuse is (not candidate)


@pytest.mark.parametrize("source", [
    {"assembly_joints": [{"source": "USER_ADDED"}]},
    {"custom_parts": {"items": {"custom:1": {}}}},
    {"joint_relief_state": {"head": ["interference"]}},
])
def test_cross_part_dependencies_disallow_world_rebase(source):
    result = api.plan_receiving_bay_preview_reuse_policy(
        {**_snapshot(), **source}, bay_index=3,
    )
    assert not result.allow_upstream_translation


def test_live_custom_sheets_need_real_catalog_even_with_stale_saved_source():
    snapshot = _snapshot()
    result = api.plan_receiving_bay_preview_reuse_policy(
        snapshot, bay_index=3, available_parts=("box_body", "custom:9"),
    )
    assert result.requires_live_custom_catalog
    assert not result.allow_upstream_translation
    assert "custom_parts" not in snapshot


def test_gui_only_consumes_engine_physical_policy_and_raw_part_kind():
    source = (Path(__file__).resolve().parents[1] /
        "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    relevant = source.split("def receiving_bay_preview_request(", 1)[1].split(
        "def receiving_layer_preview_payload(", 1,
    )[0]
    assert "manufacturing_api.plan_receiving_bay_preview_reuse_policy(" in relevant
    assert "manufacturing_api.receiving_raw_source_cache_kind(" in relevant
    assert 'str(key).startswith("box_body:divider:")' not in relevant
    assert 'str(key).startswith("inner_door:")' not in relevant
    assert 'str(key).startswith("custom:")' not in relevant
    assert "allow_rebase = reuse_policy.allow_upstream_translation" in relevant
    assert "allow_suffix_topology_reuse=reuse_policy.allow_suffix_topology_reuse" in relevant
    engine = (Path(__file__).resolve().parents[1] /
        "ae_engine/receiving_bay_preview_source.py"
    ).read_text(encoding="utf-8")
    assert "from gui_modules" not in engine and "from phase6_" not in engine
