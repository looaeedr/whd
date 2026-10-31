# -*- coding: utf-8 -*-
"""#2517: Receiving Head/Tail highlighted candidate Apply is Engine-owned."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout, append_receiving_set
from ae_engine.receiving_shared_settings import setting_value, share_setting
from ae_engine.sheetmetal_feature_core import CircleFeature, RectFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from phase6_project_file import _encode, _decode


def _fixture():
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1200, depth=350),
    )
    adapter.set_bay_count(3)
    adapter.set_set_count(2)
    return adapter


def _head():
    return [CircleFeature(
        diameter=10.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(200.0, 150.0),
    )]


def _tail():
    return [RectFeature(
        width=12.0, height=8.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(220.0, 100.0), layer="MARKING",
    )]


def test_engine_highlighted_bay_apply_preserves_sharing_and_other_set():
    adapter = _fixture()
    original = adapter.layout
    linked = share_setting(
        original, set_index=0, bay_indices=(0, 1, 2),
        source_bay_index=0, kind="head_features",
    )
    frozen = deepcopy(linked)
    result, indices, ids = manufacturing_api.apply_receiving_endcap_candidate_to_bays(
        linked, "head", 0, (2, 1, 1), _head(), version_id="head-v1",
    )
    assert indices == (1, 2)
    assert ids == tuple(result["sets"][0]["bays"][i]["stable_id"] for i in indices)
    assert linked == frozen
    for i in (1, 2):
        assert setting_value(result["sets"][0], i, "head_features") == _head()
        assert setting_value(result["sets"][0], i, "head_version_id") == "head-v1"
    assert setting_value(result["sets"][0], 0, "head_features") == []
    assert result["sets"][1] == frozen["sets"][1]
    assert all(setting_value(result["sets"][0], i, "tail_features") == []
               for i in range(3))
    assert _decode(_encode({"receiving_layout": result}))["receiving_layout"] == result


def test_engine_rejects_bad_role_set_bool_and_unhashable_bay_atomically():
    adapter = _fixture()
    original = adapter.layout
    frozen = deepcopy(original)
    for role, si, bays in (
        ("door", 0, (0,)), ("head", True, (0,)), ("head", 9, (0,)),
        ("head", 0, (True,)), ("head", 0, (1, 5)),
        ("head", 0, ([1],)), ("head", 0, ()),
    ):
        with pytest.raises((ValueError, TypeError)):
            manufacturing_api.apply_receiving_endcap_candidate_to_bays(
                original, role, si, bays, _head(), version_id="head-v1",
            )
    assert original == frozen


def test_headless_tail_single_apply_and_gui_delegation(monkeypatch):
    adapter = _fixture()
    initial = deepcopy(adapter.layout)
    selected = adapter.selection
    real = manufacturing_api.apply_receiving_endcap_candidate_to_bays
    calls = []

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(
        manufacturing_api, "apply_receiving_endcap_candidate_to_bays", record,
    )
    indices = adapter.apply_candidate_to_bays(
        "tail", 1, (0,), _tail(), version_id="tail-v1",
    )
    assert indices == (0,) and len(calls) == 1
    assert calls[0][0][1] == "tail"
    assert adapter.selection == selected
    assert initial == _fixture().layout
    assert setting_value(adapter.layout["sets"][1], 0, "tail_features") == _tail()
    assert setting_value(adapter.layout["sets"][1], 0, "tail_version_id") == "tail-v1"
    assert adapter.layout["sets"][0] == initial["sets"][0]
