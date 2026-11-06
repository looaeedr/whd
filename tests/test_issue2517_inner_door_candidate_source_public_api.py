# -*- coding: utf-8 -*-
"""#2517: Receiving inner-door candidate Apply source checks belong to Engine.

This is model/source eligibility, not a manufacturing or DXF certification.
Both the native GUI and a headless client must use the same Engine owner.
"""
from copy import deepcopy
from inspect import getsource

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_inner_door_candidates import (
    create_inner_candidate,
    validate_receiving_inner_door_source_models as source_owner,
)
from ae_engine.receiving_inner_door_pairing import (
    validate_inner_door_allocation as allocation_owner,
)
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from gui_modules.application import fold_designer_composition_receiving as gui


LEGACY = "400_140X257_107.dxf"


def _config(model):
    return {"layers": 1, "models": [model, ""],
            "layer_heights_mm": [550, 830], "features": {}}


def test_public_engine_facades_share_exact_candidate_source_and_allocation_owners():
    assert api.validate_receiving_inner_door_source_models is source_owner
    assert ae_engine.validate_receiving_inner_door_source_models is source_owner
    assert "validate_receiving_inner_door_source_models" in ae_engine.__all__
    assert api.validate_receiving_inner_door_allocation is allocation_owner
    assert ae_engine.validate_receiving_inner_door_allocation is allocation_owner
    assert "validate_receiving_inner_door_allocation" in ae_engine.__all__


@pytest.mark.parametrize("legacy", [True, False])
def test_headless_candidate_models_use_same_real_parent_brand_sources(legacy):
    model = LEGACY if legacy else numeric_model_ref("士林", "2P400")
    config = _config(model)
    before = deepcopy(config)
    assert api.validate_receiving_inner_door_source_models(config, "士林") == config
    assert config == before
    # An existing source must not silently be remapped to a different parent.
    with pytest.raises(ValueError, match="內門版本型號已不在廠牌 CSV"):
        api.validate_receiving_inner_door_source_models(config, "東元")
    assert config == before


def test_removed_or_cross_brand_source_rejected_without_edited_candidate():
    for model in ("NO_SUCH_SOURCE.dxf", "nfbv5:東元:2P400"):
        config = _config(model)
        before = deepcopy(config)
        with pytest.raises(ValueError, match="內門版本型號已不在廠牌 CSV"):
            api.validate_receiving_inner_door_source_models(config, "士林")
        assert config == before


def test_two_physical_switch_occurrences_are_not_deduplicated_or_normalized_away():
    model = numeric_model_ref("士林", "2P400")
    config = _config([model, model])
    result = api.validate_receiving_inner_door_source_models(config, "士林")
    assert result["models"][0] == [model, model]
    assert result is not config
    with pytest.raises(ValueError, match="單層內門"):
        api.validate_receiving_inner_door_source_models(
            {"layers": 1, "models": [model, LEGACY]}, "士林",
        )


def test_read_only_engine_allocation_preserves_existing_set_bay_identity():
    model = numeric_model_ref("士林", "2P400")
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    library, vid = create_inner_candidate(None, _config(model))
    before = deepcopy((layout, library))
    result = api.validate_receiving_inner_door_allocation(
        layout, library, {vid: 1}, {(0, 0): vid}, expected_counts=(1,),
    )
    assert len(result) == 1
    assert result[0][:2] == (0, 0)
    assert api.validate_receiving_inner_door_source_models(result[0][2], "士林")
    assert (layout, library) == before
    with pytest.raises(ValueError, match="總連數已變動"):
        api.validate_receiving_inner_door_allocation(
            layout, library, {vid: 1}, {(0, 0): vid},
            expected_counts=(2,),
        )


def test_original_fold_designer_candidate_apply_is_public_api_only():
    src = getsource(gui)
    assert "manufacturing_api.validate_receiving_inner_door_source_models(" in src
    assert "manufacturing_api.validate_receiving_inner_door_allocation(" in src
    assert "manufacturing_api.receiving_candidate_version_label(" in src
    assert "from ae_engine.receiving_inner_door_pairing import validate_inner_door_allocation" not in src
    assert "from ae_engine.receiving_hole_candidates import version_label" not in src
    assert "set(model_filenames(selected_brand))" not in src
