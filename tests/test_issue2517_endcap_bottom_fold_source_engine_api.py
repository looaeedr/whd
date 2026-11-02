# -*- coding: utf-8 -*-
"""#2517: Head/Tail lower-Fold manufacturing source is Engine-owned."""
from copy import deepcopy
from inspect import getsource

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.endcap_xy_readback import fold_material_segment_outside_length
import phase6_manufacturing_adapter as adapter


def _sources():
    return {
        "head": {"Y": [
            {"phase6_key": "ytop1", "len": 30},
            {"phase6_key": "ybottom1", "len": 18, "ui_len_add": 2},
            {"phase6_key": "ybottom1", "len": 999, "ui_len_add": 0},
        ]},
        "tail": {"Y": [
            {"phase6_key": "ybottom1", "len": 23, "ui_len_add": 4},
            {"phase6_key": "fw", "len": 25},
        ]},
    }


def test_both_endcaps_reuse_exact_existing_fold_outside_length_contract():
    sources = _sources()
    old = deepcopy(sources)
    expected = {
        "head_ybottom1": float(fold_material_segment_outside_length(
            sources["head"]["Y"][1],
        )),
        "tail_ybottom1": float(fold_material_segment_outside_length(
            sources["tail"]["Y"][0],
        )),
    }
    assert api.project_manufacturing_endcap_bottom_fold_inputs(sources) == expected
    assert expected == {"head_ybottom1": 20.0, "tail_ybottom1": 27.0}
    assert sources == old


def test_missing_endcap_or_fold_never_fabricates_manufacturing_dimensions():
    assert api.project_manufacturing_endcap_bottom_fold_inputs({}) == {}
    assert api.project_manufacturing_endcap_bottom_fold_inputs({
        "head": {"Y": [{"phase6_key": "fw", "len": 20}]},
        "tail": {"Y": [{"phase6_key": "ybottom1", "len": 19}]},
    }) == {"tail_ybottom1": 19.0}


def test_invalid_fold_numeric_source_fails_via_existing_engine_gate():
    with pytest.raises((ValueError, TypeError, OverflowError)):
        api.project_manufacturing_endcap_bottom_fold_inputs({
            "head": {"Y": [{"phase6_key": "ybottom1", "len": "invalid"}]},
        })


def test_gui_manufacturing_adapter_only_collects_profiles_not_physical_fold_roles():
    source = getsource(adapter.build_scene_payload_for_app)
    assert "manufacturing_api.project_manufacturing_endcap_bottom_fold_inputs(" in source
    assert 'if str(row.get("phase6_key") or "") == "ybottom1"' not in source
    assert "engine_segment_length_to_ui(" not in source
    assert "head_ybottom1" not in source
    assert "tail_ybottom1" not in source
